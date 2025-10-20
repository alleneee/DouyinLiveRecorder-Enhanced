# 日志系统测试验证指南

## 测试目标

验证新的统一日志格式能够:
1. 提供完整的链路追踪能力
2. 方便通过业务键(platform、platform_room_id、session_id)快速定位问题
3. 清晰展示录制流程的各个阶段
4. 正确处理手动停止录制的情况

## 测试准备

### 1. 环境检查
```bash
# 检查配置文件
cat .env | grep -E "DB_|OSS_|VIDEO_"

# 确认数据库连接
python -c "from app.database_async import SessionLocal; db = SessionLocal(); print('数据库连接成功')"

# 检查日志目录
ls -la logs/
```

### 2. 清理旧日志(可选)
```bash
# 备份现有日志
mv logs/app.log logs/app_backup_$(date +%Y%m%d_%H%M%S).log

# 重启应用
./start_api.sh
```

## 测试用例

### 测试用例 1: 完整录制流程

**目标**: 验证从开播到下播的完整日志链路

**步骤**:
1. 添加一个直播间到监控列表
2. 等待主播开播
3. 让系统自动录制至少 3 个分片
4. 等待主播下播或手动停止录制
5. 等待所有分片上传完成

**验证点**:
```bash
# 1. 查看监听线程启动日志
grep "监听线程启动" logs/app.log
# 期望格式: [抖音 | 296728101980] 监听线程启动

# 2. 查看开播检测日志
grep "检测到开播" logs/app.log
# 期望格式: [抖音 | 296728101980] 检测到开播, url=...

# 3. 查看录制线程启动
grep "录制线程启动" logs/app.log
# 期望格式: [抖音 | 296728101980 | c840ef38] 录制线程启动

# 4. 查看分片创建日志
grep "切片记录创建" logs/app.log
# 期望格式: [抖音 | 296728101980 | c840ef38 | seg0] 切片记录创建, index=0

# 5. 查看分片处理完成日志
grep "✅ 分片处理完成" logs/app.log
# 期望格式: [抖音 | 296728101980 | c840ef38 | seg0] ✅ 分片处理完成

# 6. 统计总分片数
SESSION_ID=$(grep "录制线程启动" logs/app.log | tail -1 | grep -oP 'c[0-9a-f]{7}')
grep "$SESSION_ID | seg" logs/app.log | grep "切片记录创建" | wc -l
```

**预期结果**:
- 所有日志都包含正确的业务上下文前缀
- Session ID 在录制阶段保持一致
- 可以通过 grep 追踪完整流程
- 分片编号从 0 开始连续递增

---

### 测试用例 2: 手动停止录制

**目标**: 验证手动停止时的日志正确性,特别是 FFmpeg 返回码 255 的处理

**步骤**:
1. 启动录制(可以是自动开播或手动激活)
2. 等待至少录制 2 个分片
3. 通过 API 手动停止录制
4. 观察日志输出

**API 调用**:
```bash
# 停止录制
curl -X POST http://localhost:8000/api/v1/recording/stop \
  -H "Content-Type: application/json" \
  -d '{"url": "https://live.douyin.com/296728101980"}'
```

**验证点**:
```bash
# 1. 查看停止信号日志
grep "收到停止信号" logs/app.log | tail -1

# 2. 查看 FFmpeg 完成日志(不应该是 ERROR)
grep "FFmpeg录制完成" logs/app.log | tail -1
# 期望: [抖音 | 296728101980 | c840ef38] FFmpeg录制完成: return_code=255, manually_stopped=True

# 3. 确认没有错误日志
grep "FFmpeg执行失败" logs/app.log | tail -1
# 期望: 没有输出或者是旧的记录

# 4. 检查是否处理了部分录制的分片
grep "处理剩余的.*个分段文件" logs/app.log | tail -1
```

**预期结果**:
- FFmpeg 返回码 255 不再被记录为 ERROR
- 日志明确显示 `manually_stopped=True`
- 部分录制的分片也能正常处理
- 所有分片最终都上传成功

---

### 测试用例 3: 链路追踪

**目标**: 验证可以通过业务键快速定位和追踪问题

**场景**: 假设用户反馈"抖音房间 296728101980 的录制有问题"

**排查步骤**:
```bash
# 1. 查看该房间的所有日志
grep "296728101980" logs/app.log > /tmp/room_logs.txt

# 2. 找出所有会话
grep "296728101980" logs/app.log | grep "录制线程启动" | grep -oP 'c[0-9a-f]{7}' | sort -u

# 假设找到会话 c840ef38

# 3. 查看该会话的完整流程
grep "296728101980 | c840ef38" logs/app.log

# 4. 统计该会话的分片情况
echo "创建的分片数:"
grep "296728101980 | c840ef38 | seg" logs/app.log | grep "切片记录创建" | wc -l

echo "完成的分片数:"
grep "296728101980 | c840ef38 | seg" logs/app.log | grep "✅ 分片处理完成" | wc -l

echo "失败的分片数:"
grep "296728101980 | c840ef38 | seg" logs/app.log | grep "分片上传处理失败" | wc -l

# 5. 查看具体失败的分片
grep "296728101980 | c840ef38 | seg" logs/app.log | grep "ERROR"

# 6. 追踪某个特定分片(例如 seg5)
grep "296728101980 | c840ef38 | seg5\]" logs/app.log
```

**预期结果**:
- 在 30 秒内能定位到相关日志
- 可以清晰看到问题发生在哪个阶段
- 能够识别是监听、录制、上传还是其他问题
- 失败的分片能看到详细错误信息

---

### 测试用例 4: 并发录制

**目标**: 验证多个直播间同时录制时日志不会混乱

**步骤**:
1. 添加 3 个不同的直播间到监控列表
2. 等待它们开播(或手动激活录制)
3. 同时录制至少 5 分钟
4. 验证日志的正确性

**验证点**:
```bash
# 1. 查看所有活跃的会话
grep "录制线程启动" logs/app.log | tail -3

# 2. 分别提取每个会话的 session_id
SESSION1=$(grep "录制线程启动" logs/app.log | tail -3 | head -1 | grep -oP 'c[0-9a-f]{7}')
SESSION2=$(grep "录制线程启动" logs/app.log | tail -3 | head -2 | tail -1 | grep -oP 'c[0-9a-f]{7}')
SESSION3=$(grep "录制线程启动" logs/app.log | tail -3 | tail -1 | grep -oP 'c[0-9a-f]{7}')

# 3. 验证每个会话的日志都是独立的
echo "Session 1 分片数:"
grep "$SESSION1 | seg" logs/app.log | wc -l

echo "Session 2 分片数:"
grep "$SESSION2 | seg" logs/app.log | wc -l

echo "Session 3 分片数:"
grep "$SESSION3 | seg" logs/app.log | wc -l

# 4. 检查是否有日志串行
grep -E "($SESSION1|$SESSION2|$SESSION3)" logs/app.log | tail -50
```

**预期结果**:
- 每个会话的日志都有独立的 session_id
- 不同会话的日志不会互相干扰
- 可以通过 session_id 精确过滤特定会话
- 并发上传不会导致日志混乱

---

### 测试用例 5: 上传失败重试

**目标**: 验证上传失败时的错误日志格式

**模拟步骤**:
```bash
# 临时禁用 OSS 上传(修改 .env)
# OSS_ENABLED=false

# 或者设置错误的 OSS 配置触发上传失败
```

**验证点**:
```bash
# 1. 查看上传失败日志
grep "分片上传处理失败" logs/app.log

# 期望格式: [抖音 | 296728101980 | c840ef38 | seg3] 分片上传处理失败: Connection timeout

# 2. 检查错误日志是否包含完整上下文
grep "ERROR" logs/app.log | tail -10

# 3. 验证失败的分片状态
# (需要查询数据库或通过 API)
```

**预期结果**:
- 错误日志包含完整的业务上下文
- 可以快速定位是哪个房间、哪个会话、哪个分片失败
- 错误信息包含具体的失败原因

---

## 日志质量检查清单

### 格式一致性
- [ ] 所有日志都包含正确的上下文前缀
- [ ] 监听阶段: `[platform | platform_room_id]`
- [ ] 录制阶段: `[platform | platform_room_id | session_id]`
- [ ] 分片处理: `[platform | platform_room_id | session_id | segment_id]`
- [ ] Session ID 正确截断为前 8 位
- [ ] Segment ID 使用 `seg` 前缀

### 信息完整性
- [ ] 可以追踪完整的录制流程
- [ ] 关键节点都有日志记录
- [ ] 错误日志包含详细错误信息
- [ ] 进度日志使用 `[1/4]` 格式
- [ ] 成功完成使用 ✅ 标记

### 问题定位能力
- [ ] 可以通过 platform 过滤日志
- [ ] 可以通过 platform_room_id 过滤日志
- [ ] 可以通过 session_id 过滤日志
- [ ] 可以通过 segment_id 过滤日志
- [ ] 错误日志易于查找和分析

### FFmpeg 特殊处理
- [ ] 正常结束: return_code=0
- [ ] SIGTERM 结束: return_code=-15
- [ ] 手动停止: return_code=255, manually_stopped=True
- [ ] 手动停止不再显示 ERROR
- [ ] 异常终止正确记录 ERROR

## 性能验证

### 日志量评估
```bash
# 统计一个会话的日志数量
SESSION_ID="c840ef38"  # 替换为实际的 session_id
grep "$SESSION_ID" logs/app.log | wc -l

# 估算: 每个分片约 10 条日志
# 60 秒分片 + 1 小时直播 = 60 个分片 = 600 条日志
```

### 查询性能
```bash
# 测试 grep 查询速度
time grep "296728101980" logs/app.log > /dev/null

# 期望: < 1 秒 (对于 10MB 以下的日志文件)
```

## 常见问题

### Q1: 如何快速找到最近一次录制?
```bash
grep "录制线程启动" logs/app.log | tail -1
```

### Q2: 如何统计今天所有录制会话?
```bash
TODAY=$(date +"%Y-%m-%d")
grep "$TODAY.*录制线程启动" logs/app.log | wc -l
```

### Q3: 如何查看某个房间的历史会话?
```bash
ROOM_ID="296728101980"
grep "$ROOM_ID.*录制线程启动" logs/app.log
```

### Q4: 如何验证所有分片都上传成功?
```bash
SESSION_ID="c840ef38"
CREATED=$(grep "$SESSION_ID | seg" logs/app.log | grep "切片记录创建" | wc -l)
COMPLETED=$(grep "$SESSION_ID | seg" logs/app.log | grep "✅ 分片处理完成" | wc -l)
echo "创建: $CREATED, 完成: $COMPLETED"
# 期望: 两个数字相等
```

## 测试报告模板

```markdown
# 日志系统测试报告

## 测试信息
- 测试日期: YYYY-MM-DD
- 测试人: XXX
- 版本: v1.0

## 测试结果

### 测试用例 1: 完整录制流程
- 状态: ✅ 通过 / ❌ 失败
- 问题: (如有)

### 测试用例 2: 手动停止录制
- 状态: ✅ 通过 / ❌ 失败
- 问题: (如有)

### 测试用例 3: 链路追踪
- 状态: ✅ 通过 / ❌ 失败
- 问题: (如有)

### 测试用例 4: 并发录制
- 状态: ✅ 通过 / ❌ 失败
- 问题: (如有)

### 测试用例 5: 上传失败重试
- 状态: ✅ 通过 / ❌ 失败
- 问题: (如有)

## 总体评价
(总结测试结果和改进建议)
```

## 下一步

测试通过后:
1. 更新项目文档
2. 培训团队成员使用新日志系统
3. 考虑添加日志分析工具
4. 考虑集成日志监控告警系统
