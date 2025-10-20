# 数据库清理执行指南

## 📋 执行前检查清单

- [ ] 已阅读 `docs/DATABASE_CLEANUP_GUIDE.md`
- [ ] 已备份数据库
- [ ] 应用已停止运行
- [ ] 确认有回滚方案

## 🗄️ 备份数据库

```bash
# 备份当前数据库
mysqldump -u root -p live_recorder > backup_$(date +%Y%m%d_%H%M%S).sql

# 验证备份文件
ls -lh backup_*.sql
```

## 🚀 执行迁移

### 1. 停止应用

```bash
# 如果使用systemd
sudo systemctl stop douyinlive

# 或手动停止Python进程
pkill -f "python main.py"
```

### 2. 执行数据库迁移

```bash
# 查看当前迁移状态
alembic current

# 查看待执行的迁移
alembic heads

# 执行迁移(删除冗余字段)
alembic upgrade head

# 验证迁移结果
alembic current
```

### 3. 验证数据库变更

```bash
# 连接数据库
mysql -u root -p live_recorder

# 查看表结构
DESC live_rooms;

# 确认冗余字段已删除
SHOW COLUMNS FROM live_rooms LIKE 'total_session_count';
SHOW COLUMNS FROM live_rooms LIKE 'last_live_time';
```

### 4. 启动应用

```bash
# 使用systemd
sudo systemctl start douyinlive
sudo systemctl status douyinlive

# 或手动启动
python main.py
```

### 5. 测试验证

```bash
# 测试API是否正常
curl http://localhost:8000/api/live-rooms

# 查看日志
tail -f logs/app.log

# 测试录制功能
# (创建测试直播间,启动监听,检查是否正常)
```

## ⚠️ 常见问题

### 问题1: 迁移失败

**症状**: `alembic upgrade head` 报错

**解决**:
```bash
# 查看错误详情
alembic upgrade head --verbose

# 如果是字段不存在的错误,可能已经执行过迁移
alembic current

# 强制标记为已迁移(谨慎使用)
alembic stamp head
```

### 问题2: 应用启动报错

**症状**: 应用启动时报字段不存在

**排查**:
1. 检查是否有代码仍在使用已删除的字段
2. 确认 LiveRoom 模型已更新
3. 查看错误日志定位具体位置

**临时解决**: 回滚迁移
```bash
alembic downgrade -1
```

### 问题3: API查询变慢

**症状**: 统计查询响应时间增加

**解决**: 添加索引
```sql
-- 在 video_segments 表添加索引
CREATE INDEX idx_room_session ON video_segments(room_id, session_id);
CREATE INDEX idx_room_started ON video_segments(room_id, session_started_at DESC);
```

## 🔄 回滚方案

如果迁移后出现问题需要回滚:

### 方法1: 使用Alembic回滚

```bash
# 回滚上一次迁移
alembic downgrade -1

# 验证
alembic current
DESC live_rooms;
```

### 方法2: 恢复数据库备份

```bash
# 停止应用
sudo systemctl stop douyinlive

# 删除当前数据库
mysql -u root -p -e "DROP DATABASE live_recorder;"

# 重新创建数据库
mysql -u root -p -e "CREATE DATABASE live_recorder CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 恢复备份
mysql -u root -p live_recorder < backup_20250117_200000.sql

# 重置alembic到迁移前的版本
alembic downgrade 4a23d6964ef9

# 启动应用
sudo systemctl start douyinlive
```

## ✅ 验证清单

执行完成后,验证以下功能:

- [ ] 应用成功启动,无错误日志
- [ ] 直播间列表API正常响应
- [ ] 可以创建新的直播间
- [ ] 可以启动/停止监听
- [ ] 录制功能正常工作
- [ ] 分片上传正常
- [ ] 分片通知正常发送
- [ ] 数据库中 live_rooms 表只包含保留的字段

## 📊 性能对比

记录迁移前后的性能数据:

| 指标 | 迁移前 | 迁移后 | 说明 |
|------|--------|--------|------|
| live_rooms表大小 | ___MB | ___MB | 应该减少 |
| 列表查询时间 | ___ms | ___ms | 应该差不多或更快 |
| 内存占用 | ___MB | ___MB | 应该减少 |

## 📝 执行记录

执行人: ________________
执行时间: ________________
迁移版本: remove_redundant_2025
备份文件: ________________
执行结果: □ 成功  □ 失败  □ 已回滚
备注: ________________________________________

## 🆘 紧急联系

如果遇到无法解决的问题:

1. **保持冷静**: 不要慌张删除数据
2. **保留备份**: 确保备份文件完好
3. **记录错误**: 保存完整的错误日志
4. **及时回滚**: 使用上述回滚方案恢复服务

---

**重要提示**:
- ⚠️ 本操作会永久删除数据,请确保已备份
- ⚠️ 建议在测试环境先执行验证
- ⚠️ 生产环境操作建议在低峰期进行
