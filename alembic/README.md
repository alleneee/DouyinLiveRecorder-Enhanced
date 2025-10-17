# Alembic数据库迁移

## 简介

Alembic是SQLAlchemy的数据库迁移工具，用于管理数据库schema的版本控制。

## 常用命令

### 创建迁移脚本

```bash
# 自动生成迁移脚本（推荐）
alembic revision --autogenerate -m "迁移描述"

# 手动创建空白迁移脚本
alembic revision -m "迁移描述"
```

### 执行迁移

```bash
# 升级到最新版本
alembic upgrade head

# 升级一个版本
alembic upgrade +1

# 升级到指定版本
alembic upgrade <revision_id>

# 查看SQL但不执行
alembic upgrade head --sql
```

### 回滚迁移

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade <revision_id>

# 回滚所有
alembic downgrade base
```

### 查看信息

```bash
# 查看当前版本
alembic current

# 查看迁移历史
alembic history

# 查看详细历史
alembic history --verbose
```

## 工作流程

### 1. 修改模型

在 `app/models/` 中修改你的SQLAlchemy模型：

```python
# app/models/live_room.py
class LiveRoom(Base):
    __tablename__ = "live_rooms"
    
    id = Column(Integer, primary_key=True)
    new_field = Column(String(100))  # 新增字段
```

### 2. 生成迁移脚本

```bash
alembic revision --autogenerate -m "add new_field to live_rooms"
```

这会在 `alembic/versions/` 目录下生成迁移脚本。

### 3. 检查迁移脚本

打开生成的脚本，确认迁移内容正确：

```python
def upgrade() -> None:
    op.add_column('live_rooms', sa.Column('new_field', sa.String(100)))

def downgrade() -> None:
    op.drop_column('live_rooms', 'new_field')
```

### 4. 执行迁移

```bash
alembic upgrade head
```

## 初始化现有数据库

如果你已经有一个现有的数据库，需要让Alembic接管：

```bash
# 1. 生成初始迁移脚本
alembic revision --autogenerate -m "initial migration"

# 2. 标记当前数据库为最新版本（不执行迁移）
alembic stamp head
```

## 最佳实践

### 1. 每次修改模型后生成迁移

不要积累多个模型修改，每次修改后立即生成迁移脚本。

### 2. 审查自动生成的脚本

自动生成的脚本可能不完美，需要人工审查：
- 检查是否有遗漏的变更
- 确认外键关系正确
- 添加必要的数据迁移逻辑

### 3. 提供回滚方法

确保每个 `upgrade()` 都有对应的 `downgrade()`：

```python
def upgrade() -> None:
    op.add_column('table', sa.Column('new_col', sa.String(100)))

def downgrade() -> None:
    op.drop_column('table', 'new_col')
```

### 4. 数据迁移

如果需要迁移数据，使用 `op.execute()`：

```python
def upgrade() -> None:
    # 添加新列
    op.add_column('users', sa.Column('full_name', sa.String(200)))
    
    # 迁移数据
    op.execute("""
        UPDATE users 
        SET full_name = CONCAT(first_name, ' ', last_name)
    """)
    
    # 删除旧列
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'last_name')
```

### 5. 测试迁移

在开发环境测试完整的升级和回滚流程：

```bash
# 升级
alembic upgrade head

# 回滚
alembic downgrade -1

# 再次升级
alembic upgrade head
```

## 常见问题

### Q: 迁移脚本没有检测到模型变更？

**A:** 确保：
1. 模型已正确导入到 `alembic/env.py`
2. `target_metadata` 设置正确
3. 数据库连接正常

### Q: 多人协作时迁移冲突？

**A:** 
1. 及时同步代码
2. 如果出现分支，使用 `alembic merge` 合并
3. 遵循线性迁移历史

### Q: 生产环境如何执行迁移？

**A:**
1. 备份数据库
2. 在维护窗口执行
3. 先在预生产环境测试
4. 准备回滚方案

```bash
# 查看将要执行的SQL
alembic upgrade head --sql > migration.sql

# 人工审查SQL

# 执行迁移
alembic upgrade head
```

## 异步支持

本项目支持异步数据库迁移。Alembic会自动检测数据库URL：

- `mysql+aiomysql://` → 使用异步模式
- `mysql+pymysql://` → 使用同步模式

无需额外配置！

## 参考资料

- [Alembic官方文档](https://alembic.sqlalchemy.org/)
- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
