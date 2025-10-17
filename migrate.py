#!/usr/bin/env python3
"""数据库迁移辅助脚本

提供更友好的迁移命令接口。

Examples:
    # 创建迁移
    python migrate.py create "add new field"
    
    # 升级到最新
    python migrate.py upgrade
    
    # 回滚一个版本
    python migrate.py downgrade
    
    # 查看当前版本
    python migrate.py current
    
    # 查看历史
    python migrate.py history
"""
import sys
import subprocess
from pathlib import Path


def run_alembic(*args):
    """运行alembic命令"""
    cmd = ["alembic"] + list(args)
    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    command = sys.argv[1]
    
    if command == "create":
        # 创建迁移
        if len(sys.argv) < 3:
            print("错误: 请提供迁移描述")
            print("用法: python migrate.py create '迁移描述'")
            return 1
        message = sys.argv[2]
        return run_alembic("revision", "--autogenerate", "-m", message)
    
    elif command == "upgrade":
        # 升级
        target = sys.argv[2] if len(sys.argv) > 2 else "head"
        return run_alembic("upgrade", target)
    
    elif command == "downgrade":
        # 回滚
        target = sys.argv[2] if len(sys.argv) > 2 else "-1"
        return run_alembic("downgrade", target)
    
    elif command == "current":
        # 当前版本
        return run_alembic("current")
    
    elif command == "history":
        # 历史记录
        return run_alembic("history", "--verbose")
    
    elif command == "stamp":
        # 标记版本
        target = sys.argv[2] if len(sys.argv) > 2 else "head"
        return run_alembic("stamp", target)
    
    elif command == "sql":
        # 生成SQL
        target = sys.argv[2] if len(sys.argv) > 2 else "head"
        return run_alembic("upgrade", target, "--sql")
    
    elif command == "help":
        print(__doc__)
        print("\n可用命令:")
        print("  create <message>  - 创建新迁移")
        print("  upgrade [target]  - 升级数据库 (默认: head)")
        print("  downgrade [target] - 回滚数据库 (默认: -1)")
        print("  current          - 显示当前版本")
        print("  history          - 显示迁移历史")
        print("  stamp [target]   - 标记数据库版本")
        print("  sql [target]     - 生成SQL脚本")
        print("  help             - 显示此帮助")
        return 0
    
    else:
        print(f"未知命令: {command}")
        print("运行 'python migrate.py help' 查看帮助")
        return 1


if __name__ == "__main__":
    sys.exit(main())
