# 项目结构说明

## 📁 FastAPI 服务架构

本项目使用 **FastAPI** 框架提供 RESTful API 服务，所有功能通过 Web API 进行管理。

### `/app/main.py` - FastAPI 主入口

**用途**: RESTful API 服务

**功能**:
- Web API 接口
- 数据库管理直播间
- 后台监听和自动录制
- 支持多用户、远程管理
- 现代化架构（策略模式、异步）

**启动方式**:
```bash
cd /Users/niko/DouyinLiveRecorder

# 方式1：使用启动脚本（推荐）
./start_api.sh

# 方式2：使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 方式3：使用 python -m
python -m app.main
```

---

## 🚀 快速启动指南

### 启动 API 服务

```bash
# 确保在项目根目录
cd /Users/niko/DouyinLiveRecorder

# 使用启动脚本
./start_api.sh
```

**访问**:
- API 文档: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health

---

## 📂 项目目录结构

```
DouyinLiveRecorder/
├── start_api.sh               # API 服务启动脚本 ⭐
├── app/                       # FastAPI 应用
│   ├── main.py               # FastAPI 主入口 ⭐
│   ├── config.py             # 配置管理
│   ├── database_async.py     # 异步数据库
│   ├── routes/               # API 路由
│   │   └── live_rooms.py    # 直播间 API
│   ├── services/             # 业务服务
│   │   ├── live_recorder.py # 录制器（策略模式）⭐
│   │   └── recording_manager.py
│   ├── schemas/              # 数据模型
│   └── models/               # 数据库模型
├── src/                      # 核心录制逻辑
│   ├── spider.py            # 平台数据抓取
│   └── stream.py            # 流地址解析
├── docs/                     # 文档
│   ├── API_CURL_EXAMPLES_COMPLETE.md
│   └── API_ROUTE_CHANGE_NOTICE.md
└── tests/                    # 测试
    └── test_strategy_pattern.py
```

---

## 🔧 常见问题

### Q1: 为什么从 app/ 目录运行会报错？

**A**: Python 模块导入需要从项目根目录运行。正确方式：

```bash
# ❌ 错误
cd app
python main.py

# ✅ 正确
cd /Users/niko/DouyinLiveRecorder
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Q2: 如何使用 Docker 部署？

**A**: Docker 已配置为使用 FastAPI 启动方式：

```bash
# 构建镜像
docker build -t douyinliverecorder .

# 运行容器
docker run -d -p 8000:8000 douyinliverecorder
```

### Q3: 备份的 CLI 工具在哪里？

**A**: 如果需要使用旧的 CLI 工具，备份文件位于：

```bash
# 查看备份
cat main_cli_backup.py

# 如需恢复（不推荐）
cp main_cli_backup.py main.py
```

---

## 📊 架构特性

| 特性 | 说明 |
|-----|------|
| **界面** | Web API + Swagger UI |
| **配置** | 环境变量 + 数据库 |
| **管理方式** | RESTful API 接口 |
| **并发录制** | 异步 + 后台线程 |
| **监控** | API 状态查询 + 健康检查 |
| **适用场景** | 生产环境、团队协作、远程管理 |
| **代码架构** | 面向对象（策略模式）|

---

## 🎯 Docker 部署

### Dockerfile 配置

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg tzdata && \
    ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# 启动 FastAPI 服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose 配置

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./downloads:/app/downloads
    environment:
      - DATABASE_URL=sqlite:///./douyinlive.db
      - API_HOST=0.0.0.0
      - API_PORT=8000
```

---

## 📝 总结

✅ **使用 FastAPI** - 现代化架构，功能完整
✅ **使用启动脚本** - 简化操作，避免混淆
✅ **Docker 支持** - 容器化部署，环境隔离

**推荐启动命令**:
```bash
./start_api.sh
```

**访问 API 文档**:
```
http://localhost:8000/docs
```

---

**最后更新**: 2025-10-17
**项目**: DouyinLiveRecorder
**版本**: 2.0.0
