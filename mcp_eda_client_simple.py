#!/usr/bin/env python3
"""
MCP EDA Client - 智能交互版
- 保持官方推荐的MCP连接方式
- 支持自然语言命令、参数自动补全、智能推断
- 参考mcp_agent_client.py的参数提取与友好交互
"""
import asyncio
import json
import re
from pathlib import Path
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

# 智能参数提取（支持中英文、结构化和自然语言）
def extract_params(user_input: str) -> dict:
    params = {}
    # 设计名
    m = re.search(r"设计\s*([\w\d_]+)|design\s*([\w\d_]+)", user_input, re.IGNORECASE)
    if m:
        params["design"] = m.group(1) or m.group(2)
    # 顶层模块
    m = re.search(r"top[_ ]?module\s*([\w\d_]+)|顶层模块\s*([\w\d_]+)", user_input, re.IGNORECASE)
    if m:
        params["top_module"] = m.group(1) or m.group(2)
    # 工艺库
    m = re.search(r"tech\s*([\w\d_]+)|工艺库\s*([\w\d_]+)", user_input, re.IGNORECASE)
    if m:
        params["tech"] = m.group(1) or m.group(2)
    # 版本索引
    m = re.search(r"version[_ ]?idx\s*(\d+)|版本索引\s*(\d+)", user_input, re.IGNORECASE)
    if m:
        params["version_idx"] = int(m.group(1) or m.group(2))
    # g_idx, p_idx, c_idx
    for key in ["g_idx", "p_idx", "c_idx"]:
        m = re.search(rf"{key}\s*(\d+)", user_input)
        if m:
            params[key] = int(m.group(1))
    # syn_ver, impl_ver, restore_enc
    for key in ["syn_ver", "impl_ver", "restore_enc"]:
        m = re.search(rf"{key}\s*([\w\d_\-]+)", user_input)
        if m:
            params[key] = m.group(1)
    # force
    if re.search(r"force|强制", user_input, re.IGNORECASE):
        params["force"] = True
    return params

# 智能推断（如自动检测top_module、syn_ver等）
def smart_complete(tool: str, params: dict) -> dict:
    # 自动补全tech
    if "tech" not in params:
        params["tech"] = "FreePDK45"
    # 自动补全version_idx
    if "version_idx" not in params:
        params["version_idx"] = 0
    # 自动补全force
    if "force" not in params:
        params["force"] = False
    # 自动推断top_module
    if tool in ["floor_planning", "power_planning", "placement", "clock_tree_synthesis", "routing", "save_design", "run_complete_flow"]:
        if "top_module" not in params and "design" in params:
            # 尝试从designs/<design>/config.tcl中读取TOP_MODULE或TOP_NAME
            config_path = Path("designs") / params["design"] / "config.tcl"
            if config_path.exists():
                content = config_path.read_text(errors="ignore")
                m = re.search(r'(TOP_MODULE|TOP_NAME)\s*=\s*"([^"]+)"', content)
                if m:
                    params["top_module"] = m.group(2)
    # 自动推断syn_ver
    if tool == "floor_planning" and "syn_ver" not in params and "design" in params:
        synth_dir = Path("designs") / params["design"] / "FreePDK45" / "synthesis"
        if synth_dir.exists():
            subdirs = [d for d in synth_dir.iterdir() if d.is_dir()]
            if subdirs:
                params["syn_ver"] = max(subdirs, key=lambda p: p.stat().st_mtime).name
    return params

# 工具别名映射
TOOL_ALIASES = {
    "综合设置": "synthesis_setup",
    "setup": "synthesis_setup",
    "compile": "synthesis_compile",
    "综合编译": "synthesis_compile",
    "布局": "floor_planning",
    "floorplan": "floor_planning",
    "电源": "power_planning",
    "power": "power_planning",
    "placement": "placement",
    "布局放置": "placement",
    "cts": "clock_tree_synthesis",
    "时钟树": "clock_tree_synthesis",
    "route": "routing",
    "布线": "routing",
    "保存": "save_design",
    "save": "save_design",
    "完整流程": "run_complete_flow",
    "flow": "run_complete_flow"
}

def match_tool(user_input: str, tool_list: list) -> str:
    # 先查别名
    for k, v in TOOL_ALIASES.items():
        if k in user_input.lower():
            return v
    # 再查工具名
    for tool in tool_list:
        if tool in user_input.lower():
            return tool
    return ""

async def interactive_client():
    server_path = Path(__file__).parent / "server" / "mcp" / "mcp_eda_server.py"
    server_params = StdioServerParameters(
        command="python3",
        args=[str(server_path)],
        env={"PYTHONPATH": str(Path(__file__).parent)}
    )
    print("=== 智能交互式 MCP EDA 客户端 ===")
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("✅ 已连接到MCP服务器。输入 help 查看命令，exit 退出。\n")
            # 获取工具列表
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            # 交互主循环
            while True:
                user_input = input("MCP> ").strip()
                if user_input.lower() in ["exit", "quit", "q"]:
                    print("再见！")
                    break
                if user_input.lower() in ["help", "h", "?", "帮助"]:
                    print("""
可用命令：
  list                列出所有工具
  call <工具名> <参数>  调用指定工具（支持自然语言）
  直接输入自然语言    智能识别并调用合适工具
  exit                退出客户端
示例：
  call 综合设置 设计 b14
  call floorplan design b14 top_module b14
  请为b14设计做综合设置
  布局 b14 顶层模块 b14
                    """)
                    continue
                if user_input.lower() == "list":
                    print("可用工具：")
                    for t in tools_result.tools:
                        print(f"  - {t.name}: {t.description}")
                    continue
                # 解析命令
                if user_input.startswith("call "):
                    parts = user_input[5:].strip().split()
                    if not parts:
                        print("请指定工具名！")
                        continue
                    tool = match_tool(parts[0], tool_names)
                    if not tool:
                        print(f"未知工具: {parts[0]}")
                        continue
                    param_str = " ".join(parts[1:])
                    params = extract_params(param_str)
                    params = smart_complete(tool, params)
                else:
                    # 智能识别工具
                    tool = match_tool(user_input, tool_names)
                    if not tool:
                        print("无法识别要调用的工具，请输入 help 查看用法。")
                        continue
                    params = extract_params(user_input)
                    params = smart_complete(tool, params)
                # 检查必需参数
                tool_obj = next((t for t in tools_result.tools if t.name == tool), None)
                missing = []
                param_keys = []
                if tool_obj is not None:
                    # 兼容新版MCP Tool对象参数字段
                    if hasattr(tool_obj, 'parameters') and tool_obj.parameters:
                        # 老版本MCP
                        param_keys = [p for p in tool_obj.parameters if getattr(tool_obj.parameters[p], 'required', False)]
                    elif hasattr(tool_obj, 'signature') and tool_obj.signature:
                        # 新版MCP: signature是inspect.Signature对象
                        for pname, param in tool_obj.signature.parameters.items():
                            if param.default is param.empty:
                                param_keys.append(pname)
                    else:
                        # 打印所有属性，提示用户补全
                        print(f"无法自动获取参数定义，tool对象属性如下：{dir(tool_obj)}")
                    for p in param_keys:
                        if p not in params:
                            missing.append(p)
                    if missing:
                        print(f"缺少参数: {missing}，请补充后重试。")
                        continue
                else:
                    print(f"未知工具: {tool}，请检查工具名。")
                    continue
                print(f"调用工具: {tool}，参数: {params}")
                try:
                    result = await session.call_tool(tool, arguments=params)
                    if result.content and len(result.content) > 0:
                        print("结果：")
                        print(result.content[0].text)
                    else:
                        print("工具返回空结果")
                except Exception as e:
                    print(f"❌ 工具调用失败: {e}")

if __name__ == "__main__":
    asyncio.run(interactive_client()) 