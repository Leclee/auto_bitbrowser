"""
@file __init__.py
@brief 谷歌业务前端模块
@details 包含谷歌账号自动化的PyQt6 GUI界面

已迁移模块:
- sheerid_gui: SheerID验证GUI
- bind_card_gui: 绑卡订阅GUI

注意: 基础窗口类已移到 gui/ 公共模块
"""

import sys
import os

# 添加_legacy目录到路径（兼容未迁移模块）
_src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_legacy_dir = os.path.join(_src_dir, '_legacy')
if _legacy_dir not in sys.path:
    sys.path.insert(0, _legacy_dir)

# 从公共gui模块导入基础类（为了向后兼容）
from gui.base_window import BaseWindow, BaseDialog, resource_path, get_data_path

# 导入已迁移的模块
from .sheerid_gui import SheerIDWindow, VerifyWorker
from .bind_card_gui import BindCardWindow, BindCardWorker

# 导入尚未迁移的模块（从_legacy）
try:
    from auto_all_in_one_gui import AutoAllInOneWindow
except ImportError as e:
    print(f"[google.frontend] 部分GUI模块导入失败: {e}")
    AutoAllInOneWindow = None

__all__ = [
    # 基础类（从gui公共模块重新导出，向后兼容）
    'BaseWindow',
    'BaseDialog',
    'resource_path',
    'get_data_path',
    # Google专属GUI
    'SheerIDWindow',
    'VerifyWorker',
    'BindCardWindow',
    'BindCardWorker',
    # 待迁移GUI
    'AutoAllInOneWindow',
]
