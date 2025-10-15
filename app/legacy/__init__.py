"""旧版兼容模块。

从 src/ 移入，保持向后兼容。
"""

import os
from pathlib import Path

# JavaScript 脚本路径
JS_SCRIPT_PATH = str(Path(__file__).parent / "javascript")

# 导出常用模块
__all__ = ["JS_SCRIPT_PATH"]
