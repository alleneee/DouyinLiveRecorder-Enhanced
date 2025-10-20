# Supervisor 部署指南

## 日志系统架构

### Supervisor环境下的日志分层

```
┌─────────────────────────────────────────────┐
│           Supervisor 进程管理器              │
├─────────────────────────────────────────────┤
│  捕获 stdout/stderr                         │
│  → logs/supervisor_stdout.log               │
│  → logs/supervisor_stderr.log               │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          Uvicorn ASGI 服务器                │
├─────────────────────────────────────────────┤
│  访问日志 (HTTP请求)                        │
│  启动/关闭日志                              │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          应用业务日志 (Loguru)              │
├─────────────────────────────────────────────┤
│  → logs/recorder.log (完整链路)            │
│  → logs/error.log (错误独立)               │
└─────────────────────────────────────────────┘
```

### 日志配置说明

**1. Supervisor日志** (进程级别)
- `supervisor_stdout.log` - uvicorn的标准输出
- `supervisor_stderr.log` - uvicorn的错误输出
- 包含:uvicorn启动信息、HTTP访问日志、进程异常

**2. 应用业务日志** (业务级别)
- `recorder.log` - 业务流程日志(监听、录制、上传)
- `error.log` - 错误和异常详情
- 包含:录制流程、OSS上传、FFmpeg操作

**3. 环境变量控制**
- `SUPERVISOR_ENABLED=true` - 禁用控制台日志输出
- 避免日志重复记录到supervisor和recorder.log

## 安装配置

### 1. 安装Supervisor

**macOS:**
```bash
brew install supervisor
```

**Ubuntu/Debian:**
```bash
sudo apt-get install supervisor
```

**CentOS/RHEL:**
```bash
sudo yum install supervisor
```

### 2. 配置文件部署

**方式一:包含式配置(推荐)**
```bash
# 复制配置文件到supervisor配置目录
sudo cp supervisor.conf /etc/supervisor/conf.d/douyin-live-recorder.conf

# 或者创建软链接
sudo ln -s /Users/niko/DouyinLiveRecorder/supervisor.conf \
            /etc/supervisor/conf.d/douyin-live-recorder.conf
```

**方式二:主配置文件引入**
```bash
# 编辑 /etc/supervisor/supervisord.conf
sudo vim /etc/supervisor/supervisord.conf

# 在文件末尾添加:
[include]
files = /Users/niko/DouyinLiveRecorder/supervisor.conf
```

### 3. 调整配置路径

编辑 `supervisor.conf`,根据实际情况修改:

```ini
# 工作目录(项目根目录)
directory=/path/to/DouyinLiveRecorder

# 日志目录(确保有写权限)
stdout_logfile=/path/to/DouyinLiveRecorder/logs/supervisor_stdout.log
stderr_logfile=/path/to/DouyinLiveRecorder/logs/supervisor_stderr.log

# 运行用户(实际系统用户)
user=your_username
```

## 使用命令

### 重载配置
```bash
# 读取新配置
sudo supervisorctl reread

# 更新并启动新程序
sudo supervisorctl update
```

### 进程管理
```bash
# 启动服务
sudo supervisorctl start douyin-live-recorder

# 停止服务
sudo supervisorctl stop douyin-live-recorder

# 重启服务
sudo supervisorctl restart douyin-live-recorder

# 查看状态
sudo supervisorctl status douyin-live-recorder

# 查看所有进程
sudo supervisorctl status
```

### 日志查看
```bash
# 查看supervisor捕获的输出
tail -f logs/supervisor_stdout.log

# 查看supervisor捕获的错误
tail -f logs/supervisor_stderr.log

# 查看应用业务日志
tail -f logs/recorder.log

# 查看应用错误日志
tail -f logs/error.log

# 通过supervisor命令查看日志
sudo supervisorctl tail douyin-live-recorder
sudo supervisorctl tail -f douyin-live-recorder stderr
```

### Web界面(可选)

在 `/etc/supervisor/supervisord.conf` 中启用:

```ini
[inet_http_server]
port=127.0.0.1:9001
username=admin
password=your_password
```

然后访问: http://127.0.0.1:9001

## 日志文件说明

### 日志目录结构
```
logs/
├── supervisor_stdout.log     # Supervisor捕获的标准输出
│   └── 包含:uvicorn启动信息、HTTP访问日志
├── supervisor_stderr.log     # Supervisor捕获的错误输出
│   └── 包含:uvicorn错误、进程异常
├── recorder.log              # 应用业务日志
│   └── 包含:监听、录制、上传流程
└── error.log                 # 应用错误日志
    └── 包含:异常堆栈、错误详情
```

### 查看不同类型的日志

**1. HTTP访问日志**
```bash
grep "GET\|POST\|PUT\|DELETE" logs/supervisor_stdout.log
```

**2. 录制流程日志**
```bash
grep "检测到开播\|启动FFmpeg\|上传成功" logs/recorder.log
```

**3. 错误日志**
```bash
# 应用错误
tail -f logs/error.log

# 进程错误
tail -f logs/supervisor_stderr.log
```

**4. 特定房间追踪**
```bash
# 完整链路
grep "296728101980" logs/recorder.log

# 包括HTTP请求
grep "296728101980" logs/supervisor_stdout.log logs/recorder.log
```

## 开机自启动

### macOS (launchd)

创建 `~/Library/LaunchAgents/com.supervisor.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.supervisor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/supervisord</string>
        <string>-c</string>
        <string>/etc/supervisor/supervisord.conf</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

启用:
```bash
launchctl load ~/Library/LaunchAgents/com.supervisor.plist
```

### Linux (systemd)

Supervisor通常已经配置为系统服务:

```bash
# 启用开机自启
sudo systemctl enable supervisor

# 启动服务
sudo systemctl start supervisor

# 查看状态
sudo systemctl status supervisor
```

## 故障排查

### 1. 服务无法启动

**查看supervisor日志:**
```bash
sudo supervisorctl tail douyin-live-recorder stderr
```

**检查配置:**
```bash
# 验证配置文件语法
sudo supervisord -c /etc/supervisor/supervisord.conf -n
```

**检查权限:**
```bash
# 确保日志目录有写权限
ls -la logs/

# 修改权限
chmod 755 logs/
```

### 2. 日志没有输出

**检查环境变量:**
```bash
# 确认SUPERVISOR_ENABLED已设置
sudo supervisorctl status douyin-live-recorder
```

**手动测试:**
```bash
# 不通过supervisor运行,查看日志
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. 进程频繁重启

**查看错误日志:**
```bash
tail -n 100 logs/supervisor_stderr.log
tail -n 100 logs/error.log
```

**调整重试策略:**
```ini
# 在supervisor.conf中
startsecs=10        # 增加启动检测时间
startretries=5      # 增加重试次数
```

## 性能优化

### 1. 日志轮转优化

**Supervisor日志:**
```ini
stdout_logfile_maxbytes=10MB   # 根据访问量调整
stdout_logfile_backups=5       # 保留更多历史
```

**应用日志:**
- recorder.log: 10MB轮转,7天保留
- error.log: 5MB轮转,30天保留

### 2. Worker数量

**单worker(默认):**
```bash
command=uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**多worker(高并发):**
```bash
command=uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

注意:多worker时录制管理器需要使用共享状态(Redis等)

### 3. 优雅重启

```bash
# 不中断服务的重启(需要多worker)
sudo supervisorctl signal HUP douyin-live-recorder
```

## 监控告警

### 1. 日志监控脚本

创建 `scripts/monitor_errors.sh`:

```bash
#!/bin/bash
ERROR_LOG="/Users/niko/DouyinLiveRecorder/logs/error.log"
LAST_CHECK="/tmp/error_log_last_check"

# 只检查新增的错误
if [ -f "$LAST_CHECK" ]; then
    NEW_ERRORS=$(find "$ERROR_LOG" -newer "$LAST_CHECK" -exec grep "ERROR" {} \;)
    if [ ! -z "$NEW_ERRORS" ]; then
        echo "发现新错误:"
        echo "$NEW_ERRORS"
        # 发送告警(邮件/钉钉/企业微信等)
    fi
fi

touch "$LAST_CHECK"
```

### 2. 定时任务

```bash
# 编辑crontab
crontab -e

# 每5分钟检查一次
*/5 * * * * /Users/niko/DouyinLiveRecorder/scripts/monitor_errors.sh
```

## 总结

使用Supervisor管理FastAPI应用的优势:

✅ **进程守护** - 自动重启,保证服务稳定
✅ **日志管理** - 分层日志,便于追踪和排查
✅ **集中控制** - 统一管理多个服务进程
✅ **开机自启** - 系统重启后自动恢复服务
✅ **优雅重启** - 支持零停机更新

推荐配置:
- 开发环境:直接运行uvicorn,查看实时日志
- 生产环境:使用supervisor管理,自动重启和日志轮转
