#!/usr/bin/env bash
pkill -f floorplan_server.py    2>/dev/null
pkill -f powerplan_server.py    2>/dev/null
pkill -f placement_server.py    2>/dev/null
pkill -f cts_server.py          2>/dev/null
pkill -f route_server.py        2>/dev/null
pkill -f save_server.py         2>/dev/null
pkill -f synth_setup_server.py  2>/dev/null
pkill -f synth_compile_server.py 2>/dev/null

# 用自己的虚拟环境路径 / python 路径替换
nohup python3 server/synth_setup_server.py   >/dev/null 2>&1 &
nohup python3 server/synth_compile_server.py >/dev/null 2>&1 &
nohup python3 server/floorplan_server.py     >/dev/null 2>&1 &
nohup python3 server/powerplan_server.py     >/dev/null 2>&1 &
nohup python3 server/placement_server.py     >/dev/null 2>&1 &
nohup python3 server/cts_server.py           >/dev/null 2>&1 &
nohup python3 server/route_server.py         >/dev/null 2>&1 &
nohup python3 server/save_server.py          >/dev/null 2>&1 &
echo "✅  All servers restarted"