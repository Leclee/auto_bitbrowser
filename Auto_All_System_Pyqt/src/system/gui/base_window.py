"""
@file base_window.py
@brief GUI基础窗口类
@details 提供所有GUI窗口的公共功能和统一风格
"""

import sys
import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon


def resource_path(relative_path: str) -> str:
    """
    @brief 获取资源文件的绝对路径
    @param relative_path 相对路径（如 "beta-1.svg" 或 "resources/beta-1.svg"）
    @return 绝对路径
    @details 支持开发环境和PyInstaller打包后的环境
    """
    try:
        # PyInstaller创建的临时目录
        base_path = sys._MEIPASS
    except AttributeError:
        # 开发环境
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 尝试直接路径
    full_path = os.path.join(base_path, relative_path)
    if os.path.exists(full_path):
        return full_path
    
    # 尝试 resources 目录下
    resource_full_path = os.path.join(base_path, 'resources', relative_path)
    if os.path.exists(resource_full_path):
        return resource_full_path
    
    # 返回原始路径（可能不存在）
    return full_path


def get_data_path() -> str:
    """
    @brief 获取数据目录路径
    @return 数据目录的绝对路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后的exe
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(os.path.dirname(src_dir), 'data')


class BaseWindow(QMainWindow):
    """
    @brief 基础窗口类
    @details 提供所有GUI窗口的公共功能
    """
    
    def __init__(self, title: str = "Auto System", size: tuple = (800, 600)):
        """
        @brief 初始化基础窗口
        @param title 窗口标题
        @param size 窗口大小 (width, height)
        """
        super().__init__()
        self.setWindowTitle(title)
        self.resize(size[0], size[1])
        
        # 设置窗口图标
        self._set_icon()
        
        # 初始化数据库
        self._init_database()
    
    def _set_icon(self):
        """设置窗口图标"""
        try:
            icon_path = resource_path("beta-1.svg")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
    
    def _init_database(self):
        """初始化数据库"""
        try:
            from core.database import DBManager
            DBManager.init_db()
        except ImportError:
            try:
                # 尝试从_legacy导入
                legacy_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_legacy')
                if legacy_dir not in sys.path:
                    sys.path.insert(0, legacy_dir)
                from database import DBManager
                DBManager.init_db()
            except Exception as e:
                print(f"[警告] 数据库初始化失败: {e}")
    
    def show_info(self, title: str, message: str):
        """显示信息对话框"""
        QMessageBox.information(self, title, message)
    
    def show_warning(self, title: str, message: str):
        """显示警告对话框"""
        QMessageBox.warning(self, title, message)
    
    def show_error(self, title: str, message: str):
        """显示错误对话框"""
        QMessageBox.critical(self, title, message)
    
    def show_confirm(self, title: str, message: str) -> bool:
        """显示确认对话框"""
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes


class BaseDialog(QMainWindow):
    """
    @brief 基础对话框类（作为独立窗口而非模态对话框）
    """
    
    def __init__(self, parent=None, title: str = "Dialog", size: tuple = (600, 400)):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(size[0], size[1])
        
        # 设置窗口图标
        try:
            icon_path = resource_path("beta-1.svg")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
