"""
@file google_auth.py
@brief Google账号认证和登录状态检测模块
@details 提供Google账号登录状态检测、自动登录等功能
@author Auto System
@date 2026-01-21
"""

import asyncio
import pyotp
from typing import Tuple, Optional, Dict, Any
from playwright.async_api import Page


# ==================== 登录状态枚举 ====================
class GoogleLoginStatus:
    """Google登录状态枚举"""
    LOGGED_IN = "logged_in"           # 已登录
    NOT_LOGGED_IN = "not_logged_in"   # 未登录（在登录页面）
    NEED_PASSWORD = "need_password"   # 需要输入密码
    NEED_2FA = "need_2fa"             # 需要2FA验证
    NEED_RECOVERY = "need_recovery"   # 需要辅助邮箱验证
    SESSION_EXPIRED = "session_expired"  # 会话过期
    SECURITY_CHECK = "security_check" # 安全检查（异常登录）
    UNKNOWN = "unknown"               # 未知状态


# ==================== 页面URL特征 ====================
# 已登录状态的URL特征
LOGGED_IN_URL_PATTERNS = [
    "myaccount.google.com",
    "one.google.com",
    "mail.google.com",
    "drive.google.com",
    "docs.google.com",
    "photos.google.com",
]

# 登录页面URL特征
LOGIN_URL_PATTERNS = [
    "accounts.google.com/signin",
    "accounts.google.com/v3/signin",
    "accounts.google.com/AccountChooser",
]


# ==================== 核心函数 ====================

async def check_google_login_status(page: Page, timeout: float = 5.0) -> Tuple[str, Dict[str, Any]]:
    """
    @brief 检测当前页面的Google登录状态
    @param page Playwright页面对象
    @param timeout 超时时间（秒）
    @return (status, extra_info) 状态和额外信息
    @details 通过检查URL和页面元素来判断当前登录状态
    
    使用示例:
        status, info = await check_google_login_status(page)
        if status == GoogleLoginStatus.LOGGED_IN:
            print(f"已登录: {info.get('email')}")
        elif status == GoogleLoginStatus.NEED_2FA:
            print("需要2FA验证")
    """
    extra_info = {}
    current_url = page.url
    
    # 1. 首先通过URL快速判断
    for pattern in LOGGED_IN_URL_PATTERNS:
        if pattern in current_url:
            # 尝试获取登录的邮箱
            email = await _extract_logged_in_email(page)
            if email:
                extra_info['email'] = email
            return GoogleLoginStatus.LOGGED_IN, extra_info
    
    # 2. 检查是否在登录页面
    for pattern in LOGIN_URL_PATTERNS:
        if pattern in current_url:
            return GoogleLoginStatus.NOT_LOGGED_IN, extra_info
    
    # 3. 检查页面元素来判断详细状态
    try:
        # 检查是否有邮箱输入框
        email_input = page.locator('input[type="email"]')
        if await email_input.count() > 0 and await email_input.is_visible():
            return GoogleLoginStatus.NOT_LOGGED_IN, extra_info
        
        # 检查是否有密码输入框
        password_input = page.locator('input[type="password"]')
        if await password_input.count() > 0 and await password_input.is_visible():
            return GoogleLoginStatus.NEED_PASSWORD, extra_info
        
        # 检查是否有2FA输入框
        totp_selectors = [
            'input[name="totpPin"]',
            'input[id="totpPin"]', 
            'input[type="tel"][autocomplete="one-time-code"]'
        ]
        for selector in totp_selectors:
            totp_input = page.locator(selector)
            if await totp_input.count() > 0 and await totp_input.is_visible():
                return GoogleLoginStatus.NEED_2FA, extra_info
        
        # 检查是否有辅助邮箱验证
        recovery_selectors = [
            'input[name="knowledgePreregisteredEmailResponse"]',
            'input[id="knowledge-preregistered-email-response"]'
        ]
        for selector in recovery_selectors:
            recovery_input = page.locator(selector)
            if await recovery_input.count() > 0 and await recovery_input.is_visible():
                return GoogleLoginStatus.NEED_RECOVERY, extra_info
        
        # 检查是否有"重新登录"或"会话过期"提示
        session_expired_texts = [
            "Your session has expired",
            "会话已过期",
            "Please sign in again",
            "请重新登录"
        ]
        for text in session_expired_texts:
            if await page.locator(f'text="{text}"').count() > 0:
                return GoogleLoginStatus.SESSION_EXPIRED, extra_info
        
        # 检查是否有安全检查页面
        security_texts = [
            "Verify it's you",
            "确认您的身份",
            "Unusual sign-in",
            "异常登录"
        ]
        for text in security_texts:
            if await page.locator(f'text="{text}"').count() > 0:
                return GoogleLoginStatus.SECURITY_CHECK, extra_info
        
        # 最后检查是否有用户头像（已登录标志）
        avatar = page.locator('img[data-user-email], a[href*="SignOutOptions"]')
        if await avatar.count() > 0:
            email = await _extract_logged_in_email(page)
            if email:
                extra_info['email'] = email
            return GoogleLoginStatus.LOGGED_IN, extra_info
            
    except Exception as e:
        extra_info['error'] = str(e)
    
    return GoogleLoginStatus.UNKNOWN, extra_info


async def _extract_logged_in_email(page: Page) -> Optional[str]:
    """
    @brief 从页面提取已登录的邮箱地址
    @param page Playwright页面对象
    @return 邮箱地址或None
    """
    try:
        # 方法1: 从用户头像的data属性获取
        avatar = page.locator('img[data-user-email]')
        if await avatar.count() > 0:
            email = await avatar.get_attribute('data-user-email')
            if email:
                return email
        
        # 方法2: 从账号信息链接获取
        account_link = page.locator('a[aria-label*="@"]')
        if await account_link.count() > 0:
            label = await account_link.get_attribute('aria-label')
            if label and '@' in label:
                # 提取邮箱
                import re
                match = re.search(r'[\w\.-]+@[\w\.-]+', label)
                if match:
                    return match.group(0)
        
        # 方法3: 从myaccount页面获取
        if "myaccount.google.com" in page.url:
            email_element = page.locator('text=@gmail.com, text=@googlemail.com').first
            if await email_element.count() > 0:
                text = await email_element.inner_text()
                import re
                match = re.search(r'[\w\.-]+@[\w\.-]+', text)
                if match:
                    return match.group(0)
                    
    except Exception:
        pass
    
    return None


async def is_logged_in(page: Page) -> bool:
    """
    @brief 快速检查是否已登录Google
    @param page Playwright页面对象
    @return True表示已登录，False表示未登录
    """
    status, _ = await check_google_login_status(page)
    return status == GoogleLoginStatus.LOGGED_IN


async def navigate_and_check_login(page: Page, target_url: str = "https://myaccount.google.com") -> Tuple[bool, str]:
    """
    @brief 导航到目标URL并检查登录状态
    @param page Playwright页面对象
    @param target_url 目标URL
    @return (is_logged_in, current_url)
    """
    try:
        await page.goto(target_url, timeout=30000, wait_until='domcontentloaded')
        await asyncio.sleep(2)
        
        status, _ = await check_google_login_status(page)
        return status == GoogleLoginStatus.LOGGED_IN, page.url
    except Exception as e:
        return False, str(e)


async def google_login(page: Page, account_info: dict) -> Tuple[bool, str]:
    """
    @brief 执行Google登录流程
    @param page Playwright页面对象
    @param account_info 账号信息字典，包含email, password, backup_email/backup, secret/2fa_secret
    @return (success, message)
    @details 支持: 账号密码登录, 2FA(TOTP), 辅助邮箱验证
             并处理登录后的安全提醒弹窗
    """
    import time
    email = account_info.get('email', '')
    print(f"[GoogleLogin] 开始登录流程: {email}")
    
    # 0. 首先检查是否已登录
    status, info = await check_google_login_status(page)
    if status == GoogleLoginStatus.LOGGED_IN:
        logged_email = info.get('email', '')
        if logged_email and logged_email.lower() == email.lower():
            print(f"[GoogleLogin] ✅ 已登录正确账号")
            return True, "已登录（正确账号）"
        elif logged_email:
            print(f"[GoogleLogin] 当前登录账号 {logged_email} 与目标账号 {email} 不符")
    
    # 1. 导航到登录页
    print("[GoogleLogin] 步骤1: 导航到登录页...")
    try:
        current_url = page.url
        if "accounts.google.com" not in current_url:
            await page.goto('https://accounts.google.com', timeout=60000)
            await asyncio.sleep(2)
    except Exception as e:
        print(f"[GoogleLogin] ❌ 导航失败: {e}")
        return False, f"导航失败: {e}"
    
    # 2. 等待并输入邮箱
    print("[GoogleLogin] 步骤2: 等待邮箱输入框...")
    email_timeout = 10
    start_time = time.time()
    email_input = None
    
    while time.time() - start_time < email_timeout:
        try:
            email_input = page.locator('input[type="email"]')
            if await email_input.count() > 0 and await email_input.is_visible():
                print(f"[GoogleLogin] 步骤2: 输入邮箱 {email}")
                await email_input.fill(email)
                await page.click('#identifierNext >> button')
                break
        except:
            pass
        await asyncio.sleep(0.5)
    else:
        print("[GoogleLogin] ❌ 超时: 邮箱输入框未出现")
        return False, "超时: 邮箱输入框未出现"
    
    # 3. 等待并输入密码
    print("[GoogleLogin] 步骤3: 等待密码输入框...")
    password_timeout = 10
    start_time = time.time()
    password_entered = False
    
    while time.time() - start_time < password_timeout:
        try:
            password_input = page.locator('input[type="password"]')
            if await password_input.count() > 0 and await password_input.is_visible():
                password = account_info.get('password', '')
                if not password:
                    print("[GoogleLogin] ❌ 未提供密码")
                    return False, "未提供密码"
                
                print("[GoogleLogin] 步骤3: 输入密码...")
                await password_input.fill(password)
                await page.click('#passwordNext >> button')
                password_entered = True
                break
        except:
            pass
        await asyncio.sleep(0.5)
    
    if not password_entered:
        print("[GoogleLogin] ❌ 超时: 密码输入框未出现")
        return False, "超时: 密码输入框未出现"
    
    # 等待密码验证
    print("[GoogleLogin] 步骤4: 等待密码验证...")
    await asyncio.sleep(3)
    
    # 5. 处理验证步骤循环
    max_attempts = 10
    for attempt in range(max_attempts):
        # 检查是否已登录
        current_url = page.url
        for pattern in LOGGED_IN_URL_PATTERNS:
            if pattern in current_url:
                print("[GoogleLogin] ✅ 登录成功")
                return True, "登录成功"
        
        # A. 检测2FA输入框
        try:
            totp_input = page.locator('input[name="totpPin"], input[id="totpPin"], input[type="tel"]').first
            if await totp_input.count() > 0 and await totp_input.is_visible():
                print("[GoogleLogin] 步骤5-2FA: 检测到2FA验证码输入框")
                secret = account_info.get('secret') or account_info.get('2fa_secret') or account_info.get('secret_key')
                if secret:
                    try:
                        s = secret.replace(" ", "").strip()
                        totp = pyotp.TOTP(s)
                        code = totp.now()
                        print(f"[GoogleLogin] 步骤5-2FA: 输入验证码 {code}")
                        await totp_input.fill(code)
                        await page.click('#totpNext >> button')
                        await asyncio.sleep(3)
                        continue
                    except Exception as e:
                        print(f"[GoogleLogin] ❌ 2FA生成失败: {e}")
                        return False, f"2FA生成失败: {e}"
                else:
                    print("[GoogleLogin] ❌ 需要2FA但未提供密钥")
                    return False, "需要2FA但未提供密钥"
        except:
            pass
        
        # B. 检测"Confirm your recovery email"选择页面
        try:
            recovery_option = page.locator('div[role="link"]:has-text("Confirm your recovery email")').first
            if await recovery_option.count() > 0 and await recovery_option.is_visible():
                print("[GoogleLogin] 步骤5-选择: 点击'确认辅助邮箱'选项")
                await recovery_option.click(force=True)
                await asyncio.sleep(3)
                continue
        except:
            pass
        
        # C. 检测辅助邮箱输入框
        try:
            recovery_input = page.locator('input[name="knowledgePreregisteredEmailResponse"], input[id="knowledge-preregistered-email-response"]').first
            if await recovery_input.count() > 0 and await recovery_input.is_visible():
                print("[GoogleLogin] 步骤5-辅助邮箱: 检测到辅助邮箱输入框")
                backup_email = account_info.get('backup') or account_info.get('backup_email') or account_info.get('recovery_email')
                if backup_email:
                    print(f"[GoogleLogin] 步骤5-辅助邮箱: 输入 {backup_email}")
                    await recovery_input.fill(backup_email)
                    next_btn = page.locator('button:has-text("Next"), button:has-text("下一步")').first
                    if await next_btn.count() > 0:
                        await next_btn.click()
                    else:
                        await page.keyboard.press('Enter')
                    await asyncio.sleep(3)
                    continue
                else:
                    print("[GoogleLogin] ❌ 需要辅助邮箱但未提供")
                    return False, "需要辅助邮箱但未提供"
        except:
            pass
        
        # D. 检测密码错误提示
        try:
            error_texts = ['Wrong password', '密码错误', 'Couldn\'t sign you in', '无法登录']
            for err in error_texts:
                if await page.locator(f'text="{err}"').count() > 0:
                    print(f"[GoogleLogin] ❌ 密码错误或登录失败")
                    return False, "密码错误或登录失败"
        except:
            pass
        
        # 等待并继续检测
        await asyncio.sleep(2)
    
    # 6. 处理登录后的安全弹窗
    print("[GoogleLogin] 步骤6: 检查安全弹窗...")
    try:
        dismiss_buttons = [
            'button:has-text("Not now")',
            'button:has-text("Cancel")',
            'button:has-text("No thanks")',
            'button:has-text("暂不")',
            'button:has-text("取消")'
        ]
        for selector in dismiss_buttons:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                print("[GoogleLogin] 步骤6: 关闭安全弹窗")
                await btn.click()
                await asyncio.sleep(1)
                break
    except Exception:
        pass
    
    # 最终检查
    print("[GoogleLogin] 步骤7: 最终登录状态检查...")
    final_status, _ = await check_google_login_status(page)
    if final_status == GoogleLoginStatus.LOGGED_IN:
        print("[GoogleLogin] ✅ 登录成功")
        return True, "登录成功"
    
    print(f"[GoogleLogin] ❌ 登录失败，最终状态: {final_status}")
    return False, f"登录失败，最终状态: {final_status}"


# ==================== Google One状态检测 ====================

# 状态检测用的多语言短语
NOT_AVAILABLE_PHRASES = [
    "This offer is not available",
    "Ưu đãi này hiện không dùng được",
    "Esta oferta no está disponible",
    "Cette offre n'est pas disponible",
    "此优惠目前不可用",
    "這項優惠目前無法使用",
]

SUBSCRIBED_PHRASES = [
    "You're already subscribed",
    "Bạn đã đăng ký",
    "已订阅", 
    "Ya estás suscrito"
]

VERIFIED_UNBOUND_PHRASES = [
    "Get student offer",
    "Nhận ưu đãi dành cho sinh viên",
    "Obtener oferta para estudiantes",
    "获取学生优惠",
    "獲取學生優惠",
]


async def check_google_one_status(page: Page, timeout: float = 10.0) -> Tuple[str, Optional[str]]:
    """
    @brief 检测Google One AI学生优惠页面的状态
    @param page Playwright页面对象
    @param timeout 超时时间（秒）
    @return (status, extra_data)
           status: 'subscribed' | 'verified' | 'link_ready' | 'ineligible' | 'timeout'
           extra_data: SheerID链接或其他信息
    """
    import time
    start_time = time.time()
    print(f"[GoogleOne] 开始检测状态 (超时: {timeout}秒)...")
    
    while time.time() - start_time < timeout:
        try:
            # 1. 首先检查"已订阅" - 优先级最高
            for phrase in SUBSCRIBED_PHRASES:
                try:
                    locator = page.locator(f'text="{phrase}"')
                    if await locator.count() > 0 and await locator.first.is_visible():
                        print(f"[GoogleOne] 检测到: {phrase} -> subscribed")
                        return "subscribed", None
                except:
                    pass
            
            # 2. 检查"已验证未绑卡" (Get student offer)
            for phrase in VERIFIED_UNBOUND_PHRASES:
                try:
                    locator = page.locator(f'text="{phrase}"')
                    if await locator.count() > 0 and await locator.first.is_visible():
                        print(f"[GoogleOne] 检测到: {phrase} -> verified")
                        return "verified", None
                except:
                    pass
            
            # 3. 检查SheerID链接 (有资格待验证)
            try:
                link_element = page.locator('a[href*="sheerid.com"]').first
                if await link_element.count() > 0:
                    href = await link_element.get_attribute("href")
                    print(f"[GoogleOne] 检测到SheerID链接 -> link_ready")
                    return "link_ready", href
            except:
                pass
            
            # 4. 检查"Verify eligibility"按钮
            try:
                verify_btn = page.locator('text="Verify eligibility"')
                if await verify_btn.count() > 0 and await verify_btn.first.is_visible():
                    print(f"[GoogleOne] 检测到Verify eligibility -> link_ready")
                    return "link_ready", None
            except:
                pass
            
            # 5. 检查"无资格" - 放在最后检测
            for phrase in NOT_AVAILABLE_PHRASES:
                try:
                    locator = page.locator(f'text="{phrase}"')
                    if await locator.count() > 0 and await locator.first.is_visible():
                        print(f"[GoogleOne] 检测到: {phrase} -> ineligible")
                        return "ineligible", None
                except:
                    pass
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"[GoogleOne] 检测异常: {e}")
            await asyncio.sleep(1)
    
    print(f"[GoogleOne] 检测超时")
    return "timeout", None


# ==================== 完整登录流程封装 ====================

async def ensure_google_login(page: Page, account_info: dict) -> Tuple[bool, str]:
    """
    @brief 确保Google已登录（先检查状态，未登录才执行登录）
    @param page Playwright页面对象
    @param account_info 账号信息字典
    @return (success, message)
    
    使用示例:
        success, msg = await ensure_google_login(page, account_info)
        if success:
            # 继续后续操作
    """
    email = account_info.get('email', '')
    print(f"[EnsureLogin] 检查登录状态: {email}")
    
    # 1. 先检查当前状态
    status, info = await check_google_login_status(page)
    
    if status == GoogleLoginStatus.LOGGED_IN:
        logged_email = info.get('email', '')
        if logged_email:
            if logged_email.lower() == email.lower():
                print(f"[EnsureLogin] 已登录正确账号: {logged_email}")
                return True, f"已登录: {logged_email}"
            else:
                print(f"[EnsureLogin] 当前账号 {logged_email} 与目标 {email} 不符，需重新登录")
        else:
            print(f"[EnsureLogin] 已登录（账号未知），继续使用")
            return True, "已登录"
    
    # 2. 未登录，执行登录流程
    print(f"[EnsureLogin] 未登录，开始登录流程...")
    success, message = await google_login(page, account_info)
    
    if success:
        print(f"[EnsureLogin] 登录成功: {message}")
    else:
        print(f"[EnsureLogin] 登录失败: {message}")
    
    return success, message

