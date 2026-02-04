"""
@file __init__.py
@brief 核心模块包
@details 包含数据库管理、比特浏览器API、Playwright封装等公共模块
"""

# 延迟导入以避免循环依赖
from .config import Config
from .database import DBManager

# 可选导入（需要playwright等依赖）
try:
    from .bit_api import (
        BitBrowserAPI, 
        get_api,
        openBrowser, 
        closeBrowser, 
        createBrowser, 
        deleteBrowser,
        # GUI便捷函数
        get_browser_list_simple,
        open_browsers_batch,
        delete_browsers_batch,
        get_browser_info,
        get_next_window_name,
        # 创建窗口函数
        create_browser_from_account,
        create_browsers_batch,
        DEFAULT_BROWSER_TEMPLATE,
    )
    from .bit_playwright import google_login
except ImportError as e:
    print(f"[core] 部分模块导入失败: {e}")
    BitBrowserAPI = None
    get_api = openBrowser = closeBrowser = createBrowser = deleteBrowser = None
    get_browser_list_simple = open_browsers_batch = delete_browsers_batch = None
    get_browser_info = get_next_window_name = None
    create_browser_from_account = create_browsers_batch = DEFAULT_BROWSER_TEMPLATE = None
    google_login = None

__all__ = [
    'Config',
    'DBManager',
    'BitBrowserAPI',
    'get_api',
    'openBrowser', 
    'closeBrowser', 
    'createBrowser',
    'deleteBrowser',
    'get_browser_list_simple',
    'open_browsers_batch',
    'delete_browsers_batch',
    'get_browser_info',
    'get_next_window_name',
    'create_browser_from_account',
    'create_browsers_batch',
    'DEFAULT_BROWSER_TEMPLATE',
    'google_login',
]

