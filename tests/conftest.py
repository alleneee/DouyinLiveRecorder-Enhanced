"""Pytest配置文件 - 设置Python路径和共享fixtures"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 现在可以导入app模块了
