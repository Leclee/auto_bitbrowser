"""
@file __init__.py
@brief 谷歌业务后端模块 (V3)
@details 包含谷歌账号自动化的核心业务逻辑

已迁移模块:
- account_manager: 账号状态管理
- sheerid_verifier: SheerID链接验证
- google_auth: Google登录与资格检测 (V3 - 使用 .or() 智能等待)
- google_login_service: Google登录服务
- sheerlink_service: SheerLink提取服务
- bind_card_service: 绑卡订阅服务
- all_in_one_service: 全自动处理服务
"""

from .sheerid_verifier import SheerIDVerifier
from .account_manager import AccountManager
from .google_auth import (
    # 状态类
    GoogleLoginStatus,
    # V3 核心函数
    get_login_state,         # 检测登录状态
    google_login,            # 执行登录
    check_google_one_status, # 完整流程: 导航 + 登录 + 资格检测
    detect_eligibility_status,  # 仅资格检测
    # 状态常量
    STATUS_DISPLAY,
    STATUS_NOT_LOGGED_IN,
    STATUS_SUBSCRIBED_ANTIGRAVITY,
    STATUS_SUBSCRIBED,
    STATUS_VERIFIED,
    STATUS_LINK_READY,
    STATUS_INELIGIBLE,
    STATUS_ERROR,
    STATUS_PENDING,
)
from .google_login_service import (
    GoogleLoginService,
    login_google_account,
    check_browser_login_status,
    quick_login_check,
)
from .sheerlink_service import (
    SheerLinkService,
    process_browser,
    extract_sheerlink_batch,
)
from .bind_card_service import (
    auto_bind_card,
    process_bind_card,
    process_bind_card_batch,
)
from .all_in_one_service import (
    process_all_in_one,
    process_all_in_one_batch,
)
from .change_2fa_service import (
    change_2fa_for_account,
    process_change_2fa_batch,
    Change2FAStatus,
)

__all__ = [
    # 核心类
    'SheerIDVerifier',
    'AccountManager',
    'GoogleLoginService',
    'SheerLinkService',
    # V3 登录 & 检测函数
    'GoogleLoginStatus',
    'get_login_state',
    'google_login',
    'check_google_one_status',
    'detect_eligibility_status',
    # 状态常量
    'STATUS_DISPLAY',
    'STATUS_NOT_LOGGED_IN',
    'STATUS_SUBSCRIBED_ANTIGRAVITY',
    'STATUS_SUBSCRIBED',
    'STATUS_VERIFIED',
    'STATUS_LINK_READY',
    'STATUS_INELIGIBLE',
    'STATUS_ERROR',
    'STATUS_PENDING',
    # 登录服务便捷函数
    'login_google_account',
    'check_browser_login_status',
    'quick_login_check',
    # SheerLink服务
    'process_browser',
    'extract_sheerlink_batch',
    # 绑卡服务
    'auto_bind_card',
    'process_bind_card',
    'process_bind_card_batch',
    # 全自动服务
    'process_all_in_one',
    'process_all_in_one_batch',
    # 更改2FA服务
    'change_2fa_for_account',
    'process_change_2fa_batch',
    'Change2FAStatus',
]



