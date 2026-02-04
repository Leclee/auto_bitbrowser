"""
@file config.py
@brief 统一配置管理模块
@details 管理项目的所有配置项，包括路径、API密钥等
"""

import os
import sys
from typing import Optional


class Config:
    """
    @class Config
    @brief 项目配置管理类
    @details 提供项目路径、数据库配置等统一管理
    """
    
    # 项目根目录
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的路径
        PROJECT_ROOT = os.path.dirname(sys.executable)
    else:
        # 开发环境路径
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 源代码目录
    SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
    
    # 数据目录
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
    
    # 数据库路径
    DB_PATH = os.path.join(DATA_DIR, 'accounts.db')
    
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Web服务器配置
    WEB_SERVER_PORT = 8080
    
    # SheerID配置
    SHEERID_BASE_URL = "https://batch.1key.me"
    SHEERID_DEFAULT_API_KEY = ""
    
    # 比特浏览器API配置
    BITBROWSER_API_URL = "http://127.0.0.1:54345"
    
    @classmethod
    def get_google_module_path(cls) -> str:
        """
        @brief 获取谷歌业务模块路径
        @return 谷歌模块的绝对路径
        """
        return os.path.join(cls.SRC_DIR, 'google')
    
    @classmethod
    def get_web_static_path(cls, module: str = 'google') -> str:
        """
        @brief 获取Web静态资源路径
        @param module 业务模块名称
        @return 静态资源目录的绝对路径
        """
        return os.path.join(cls.SRC_DIR, module, 'web', 'static')
    
    @classmethod
    def get_web_template_path(cls, module: str = 'google') -> str:
        """
        @brief 获取Web模板路径
        @param module 业务模块名称
        @return 模板目录的绝对路径
        """
        return os.path.join(cls.SRC_DIR, module, 'web', 'templates')
    
    @classmethod
    def get_data_file_path(cls, filename: str) -> str:
        """
        @brief 获取数据文件路径
        @param filename 文件名
        @return 数据文件的绝对路径
        """
        return os.path.join(cls.DATA_DIR, filename)
    
    @classmethod
    def ensure_directories(cls):
        """
        @brief 确保所有必要的目录存在
        """
        dirs_to_create = [
            cls.DATA_DIR,
            os.path.join(cls.SRC_DIR, 'google', 'web', 'static'),
            os.path.join(cls.SRC_DIR, 'google', 'web', 'templates'),
        ]
        for dir_path in dirs_to_create:
            os.makedirs(dir_path, exist_ok=True)
