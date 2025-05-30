#!/usr/bin/env python3
"""
MCP · Placement Service (global + detail placement & pre-CTS optimization)

启动：
    cd ~/proj/mcp-eda-example
    python3 server/placement_server.py      # 监听 0.0.0.0:3337

示例：
    curl -X POST http://localhost:3337/place/run \
         -H "Content-Type: application/json" \
         -d '{"design":"des","tech":"FreePDK45","impl_ver":"cpV1_clkP1_drcV1__g0_p0","g_idx":0,"p_idx":0,"force":true,"top_module":"des3"}'
"""
from typing import Optional
import subprocess, pathlib, datetime, os, logging, sys, csv
from fastapi import FastAPI
from pydantic import BaseModel

# ────────────────── 环境配置 & PATH ──────────────────
os.environ["PATH"] = (
    "/opt/cadence/innovus221/tools/bin:"
    "/opt/cadence/genus172/bin:" + os.environ.get("PATH", "")
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/home/yl996/pl_api.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

# ────────────────── 常量定义 ──────────────────
ROOT     = pathlib.Path(__file__).resolve().parent.parent
BACKEND  = ROOT / "scripts" / "FreePDK45" / "backend"
LOG_DIR  = ROOT / "logs" / "placement"; LOG_DIR.mkdir(parents=True, exist_ok=True)
IMP_CSV  = ROOT / "config" / "imp_global.csv"
PLC_CSV  = ROOT / "config" / "placement.csv"

# ────────────────── 请求/响应模型 ──────────────────
class PlReq(BaseModel):
    design:      str                 # 设计名
    tech:        str = "FreePDK45"    # 工艺库
    impl_ver:    str                 # 实现版本目录
    g_idx:       int = 0             # imp_global.csv 行号
    p_idx:       int = 0             # placement.csv 行号
    force:       bool = False        # 是否覆盖旧报告
    top_module:  Optional[str] = None  # 可选：顶层模块覆盖

class PlResp(BaseModel):
    status:     str                  # ok / error
    log_path:   str                  # 日志路径
    report:     str                  # check_place.out 或其他报告内容

# ────────────────── 工具函数 ──────────────────
def read_csv_row(path: pathlib.Path, idx: int) -> dict:
    rows = list(csv.DictReader(path.open()))
    if idx >= len(rows):
        raise IndexError(f"{path.name}: row {idx} out of range (total {len(rows)})")
    return rows[idx]

def parse_top_from_config(cfg: pathlib.Path) -> str:
    for line in cfg.read_text().splitlines():
        if line.startswith("set TOP_NAME"):
            return line.split('"')[1]
    return ""

def run(cmd: str, log_file: pathlib.Path, cwd: pathlib.Path, env_extra: dict):
    env = os.environ.copy()
    env.update(env_extra)
    with log_file.open("w") as lf, subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        executable="/bin/bash",
        env=env,
    ) as p:
        for line in p.stdout:
            lf.write(line)
        p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"command exited {p.returncode}")

# ────────────────── FastAPI App ──────────────────
app = FastAPI(title="MCP · Placement Service")

@app.post("/place/run", response_model=PlResp)
def place_run(req: PlReq):
    des_root = ROOT / "designs" / req.design / req.tech
    impl_dir = des_root / "implementation" / req.impl_ver
    if not impl_dir.exists():
        return PlResp(status="error: implementation dir not found", log_path="", report="")

    # floorplan 快照路径
    enc_dat = impl_dir / "pnr_save" / "floorplan.enc.dat"
    if not enc_dat.exists():
        return PlResp(status="error: floorplan.enc.dat not found", log_path="", report="")

    # 清理旧报告
    rpt_dir = impl_dir / "pnr_reports"
    if req.force:
        for rpt in ("check_place.out",):
            p = rpt_dir / rpt
            if p.exists():
                p.unlink()

    # 顶层模块
    cfg_path = ROOT / "designs" / req.design / "config.tcl"
    if req.top_module:
        top = req.top_module
    else:
        parsed = parse_top_from_config(cfg_path)
        top = parsed if parsed else req.design

    # 环境变量（务必包含 BASE_DIR）
    env = {"BASE_DIR": str(ROOT)}
    env.update(read_csv_row(IMP_CSV, req.g_idx))
    env.update(read_csv_row(PLC_CSV, req.p_idx))
    env.setdefault("TOP_NAME",    top)
    env.setdefault("FILE_FORMAT", "verilog")

    # ─── 构造 Innovus 批处理命令 ─────────────────────────
    scripts = [
        str(ROOT / "config.tcl"),
        str(ROOT / "scripts" / req.tech / "tech.tcl"),
        str(BACKEND / "4_place.tcl"),
    ]
    files_arg = " ".join(scripts)
    exec_cmd = (
        f'restoreDesign "{enc_dat}" {top}; '
        f'source "{scripts[2]}"; '
        'report_placement > pnr_reports/check_place.out'
    )
    innovus_cmd = (
        "innovus -no_gui -batch "
        f'-execute "{exec_cmd}" '
        f'-files "{files_arg}"'
    )

    # 日志文件
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{req.design}_pl_{ts}.log"

    # 执行并捕获错误
    try:
        run(innovus_cmd, log_file, impl_dir, env)
    except Exception as e:
        return PlResp(status=f"error: {e}", log_path=str(log_file), report="")

    # 读取报告: check_place.out
    report_file = rpt_dir / "check_place.out"
    if report_file.exists():
        report_text = report_file.read_text()
    else:
        report_text = "check_place.out not found"

    return PlResp(status="ok", log_path=str(log_file), report=report_text)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("placement_server:app", host="0.0.0.0", port=3337, reload=False)