# 日志路径问题修复说明

## 问题描述

当服务器在别人的机器上运行时，日志仍然会写入到你电脑上的 `/home/yl996/proj/mcp-eda-example/logs` 目录，这是因为所有服务器都使用了硬编码的路径配置。

## 问题原因

所有服务器文件都使用了以下代码来设置日志路径：

```python
ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_ROOT = ROOT / "logs"
```

这意味着：
1. `ROOT` 路径是基于服务器文件的位置计算的
2. `LOG_ROOT` 总是指向项目根目录下的 `logs` 文件夹
3. 无论服务器在哪里运行，日志都会写入到固定的路径

## 解决方案

### 1. 使用环境变量配置日志路径

修改后的代码：

```python
ROOT = pathlib.Path(__file__).resolve().parent.parent
# Use environment variable for log path, fallback to local logs directory
LOG_ROOT = pathlib.Path(os.getenv("LOG_ROOT", str(ROOT / "logs")))
```

### 2. 已修复的文件

以下服务器文件已经修复：

- `server/floorplan_server.py`
- `server/powerplan_server.py`
- `server/placement_server.py`
- `server/cts_server.py`
- `server/route_server.py`
- `server/save_server.py`

### 3. 使用方法

#### 方法1：使用默认日志目录
```bash
python server/floorplan_server.py
# 日志会写入到项目根目录的 logs/ 文件夹
```

#### 方法2：使用自定义日志目录
```bash
LOG_ROOT=/tmp/my_logs python server/floorplan_server.py
# 日志会写入到 /tmp/my_logs/ 文件夹
```

#### 方法3：在 Docker 中使用
```yaml
# docker-compose.yml
environment:
  - LOG_ROOT=/app/logs
```

#### 方法4：在系统环境中设置
```bash
export LOG_ROOT=/var/log/eda_servers
python server/floorplan_server.py
```

## 验证修复

### 1. 检查环境变量是否生效
```bash
# 设置环境变量
export LOG_ROOT=/tmp/test_logs

# 运行服务器
python server/floorplan_server.py &

# 检查日志是否写入到正确位置
ls -la /tmp/test_logs/
```

### 2. 检查日志文件路径
服务器启动后，日志文件应该出现在 `LOG_ROOT` 指定的目录中：

```
LOG_ROOT/
├── floorplan/
│   └── design_fp_20241219_123456.log
├── placement/
│   └── design_pl_20241219_123456.log
├── cts/
│   └── design_cts_20241219_123456.log
├── route/
│   └── design_route_20241219_123456.log
├── fp_api.log
├── pl_api.log
├── cts_api.log
└── route_api.log
```

## 注意事项

1. **权限问题**：确保 `LOG_ROOT` 指定的目录有写入权限
2. **磁盘空间**：确保目标目录有足够的磁盘空间
3. **路径存在性**：如果目录不存在，服务器会自动创建
4. **相对路径**：可以使用相对路径，但建议使用绝对路径

## 故障排除

### 问题1：权限被拒绝
```bash
# 解决方案：修改目录权限
sudo chown -R $USER:$USER /path/to/logs
chmod 755 /path/to/logs
```

### 问题2：磁盘空间不足
```bash
# 检查磁盘空间
df -h /path/to/logs

# 清理旧日志
find /path/to/logs -name "*.log" -mtime +7 -delete
```

### 问题3：环境变量未生效
```bash
# 检查环境变量
echo $LOG_ROOT

# 重新设置环境变量
export LOG_ROOT=/path/to/logs
```

## 总结

通过使用环境变量 `LOG_ROOT`，现在可以灵活配置日志文件的存储位置，解决了跨机器运行时日志路径硬编码的问题。这个修复确保了：

1. **灵活性**：可以根据需要指定任意日志目录
2. **兼容性**：保持向后兼容，默认行为不变
3. **可维护性**：统一的配置方式，易于管理
4. **安全性**：避免权限和路径冲突问题 