"""
@file google_auth.py
@brief Google 登录与资格检测模块 (V3 - 简化版)
@details 使用 Playwright .or() 智能等待实现登录和资格检测
"""
import asyncio
import re
from typing import Tuple, Optional, Dict, Any

import pyotp
from playwright.async_api import Page, expect


# ==================== 超时配置 ====================
DEFAULT_TIMEOUT = 30000  # 30秒


# ==================== 状态常量 ====================
class GoogleLoginStatus:
    LOGGED_IN = 'logged_in'
    NOT_LOGGED_IN = 'not_logged_in'
    UNKNOWN = 'unknown'


STATUS_NOT_LOGGED_IN = 'not_logged_in'
STATUS_SUBSCRIBED_ANTIGRAVITY = 'subscribed_antigravity'
STATUS_SUBSCRIBED = 'subscribed'
STATUS_VERIFIED = 'verified'
STATUS_LINK_READY = 'link_ready'
STATUS_INELIGIBLE = 'ineligible'
STATUS_ERROR = 'error'
STATUS_PENDING = 'pending_check'

STATUS_DISPLAY = {
    STATUS_PENDING: '❔待检测',
    STATUS_NOT_LOGGED_IN: '🔒未登录',
    STATUS_INELIGIBLE: '❌无资格',
    STATUS_LINK_READY: '🔗待验证',
    STATUS_VERIFIED: '✅已验证',
    STATUS_SUBSCRIBED: '👑已订阅',
    STATUS_SUBSCRIBED_ANTIGRAVITY: '🌟已解锁',
    STATUS_ERROR: '⚠️错误',
}


# ==================== 核心登录函数 ====================


async def _handle_post_password_verification(page: Page, account_info: dict) -> Tuple[Optional[bool], str]:
    """
    @brief 智能处理密码后的各种验证场景 (使用 .or() 竞争判断)
    @details 同时检测以下情况，哪个先出现就处理哪个：
             1. 登录成功 (头像出现)
             2. 2FA验证码输入
             3. 选择验证方式 (确认辅助邮箱选项)
             4. 直接输入辅助邮箱
             5. 弹窗 (Not now / Skip / Done 等)
             6. 错误信息 (密码错误等)
    @param page Playwright 页面对象
    @param account_info 账号信息
    @return (success, message) - success为None表示需要继续重试
    """
    max_iterations = 30
    last_2fa_code = None  # 记录上次输入的2FA验证码，防止重复输入
    
    for iteration in range(max_iterations):
        print(f"[GoogleAuth] 验证循环 {iteration + 1}/{max_iterations}...")
        
        # ==================== 最优先: 通过URL判断登录成功 ====================
        # (必须放在等待元素之前，因为 myaccount 页面没有那些定位器)
        try:
            current_url = page.url
            current_title = await page.title()
            
            # 调试：每5次循环打印当前页面URL和标题
            if iteration % 5 == 0:
                print(f"[GoogleAuth] 📍 当前页面: {current_title[:50]}... | URL: {current_url[:80]}...")
            
            # ========== URL 登录成功检测 (最可靠) ==========
            if 'myaccount.google.com' in current_url:
                print(f"[GoogleAuth] ✅ 检测到登录成功! (URL: myaccount.google.com)")
                return True, "登录成功"

            
        except Exception as e:
            print(f"[GoogleAuth] URL检测异常: {e}")
        
        # ==================== 定义所有可能的定位器 ====================
        
        # 1. 登录成功标志 - 头像按钮 (多种匹配模式)
        # 实际元素: <a class="gb_B" role="button" aria-label="Google Account: xxx (email@gmail.com)" href="...SignOutOptions...">
        
        # 模式1: role="button" 的 <a> 标签，aria-label 包含 "Google Account"
        avatar_button_1 = page.get_by_role("button", name=re.compile(r"Google (Account|帐号|账号)", re.IGNORECASE))
        
        # 模式2: 直接通过 href 包含 SignOutOptions (登出选项页面链接，只有登录后才有)
        avatar_signout_link = page.locator('a[href*="accounts.google.com/SignOutOptions"]')
        
        # 模式3: 通过 aria-label 包含邮箱格式 @ 且链接到 google account
        avatar_with_email = page.locator('a[aria-label*="@"][href*="accounts.google.com"]')
        
        # 模式4: 通过类名 gb_B (Google 头像按钮的常用类)
        avatar_gb_class = page.locator('a.gb_B[role="button"][aria-label*="Google"]')
        
        # 模式5: 头像容器 (data-ogsr-up 是 Google 账号按钮的标记)
        avatar_data = page.locator('[data-ogsr-up], [data-ogpc]')
        
        # 组合所有头像检测模式
        login_success = avatar_button_1.or_(avatar_signout_link).or_(avatar_with_email).or_(avatar_gb_class).or_(avatar_data.first)
        
        # 2. 2FA验证码输入框
        totp_input = page.locator('input[id="totpPin"]')
        
        # 3. 选择验证方式 - 确认辅助邮箱选项 (需要先点击)
        # "Verify it's you" 页面上的选项
        # 最精确: data-challengeid="5" 是辅助邮箱的唯一ID
        recovery_option_by_id = page.locator('[data-challengeid="5"]')
        # 备用: data-challengetype="12" (辅助邮箱验证类型)
        recovery_option_by_type = page.locator('[data-challengetype="12"]')
        # 备用: 通过文本匹配
        recovery_option_text_en = page.locator('div:has-text("Confirm your recovery email")[role="link"]')
        recovery_option_text_cn = page.locator('div:has-text("确认辅助邮箱")[role="link"]')
        # 组合所有可能的选择器 (优先使用 data-challengeid)
        recovery_option = recovery_option_by_id.or_(recovery_option_by_type).or_(recovery_option_text_en).or_(recovery_option_text_cn)
        
        # 4. 直接输入辅助邮箱的输入框
        recovery_input = page.locator('input[name="knowledgePreregisteredEmailResponse"]')
        
        # 5. 弹窗按钮 (Not now / Skip / Done / 以后再说 等)
        popup_buttons = page.locator(
            'button:has-text("Not now"), '
            'button:has-text("Skip"), '
            'button:has-text("Done"), '
            'button:has-text("以后再说"), '
            'button:has-text("暂时跳过"), '
            'button:has-text("完成"), '
            'button:has-text("Cancel"), '
            'button:has-text("取消")'
        )
        
        # 6. 错误信息
        error_wrong_password = page.locator('text="Wrong password"')
        error_wrong_password_cn = page.locator('text="密码错误"')
        error_locator = error_wrong_password.or_(error_wrong_password_cn)
        
        # ==================== 使用 .or() 组合所有定位器进行竞争等待 ====================
        
        combined = (
            login_success
            .or_(totp_input)
            .or_(recovery_option)
            .or_(recovery_input)
            .or_(popup_buttons)
            .or_(error_locator)
        )
        
        try:
            # 智能等待：任意一个元素出现
            await expect(combined).to_be_visible(timeout=30000)
        except:
            # 超时，继续下一次循环
            await asyncio.sleep(0.5)
            continue
        
        # ==================== 判断具体是哪个元素出现，执行对应处理 ====================
        
        # 优先级1: 检查登录成功 - 头像检测 (详细调试)
        try:
            avatar_checks = [
                (avatar_button_1, "avatar_button_1: role=button with Google Account"),
                (avatar_signout_link, "avatar_signout_link: SignOutOptions link"),
                (avatar_with_email, "avatar_with_email: aria-label contains @"),
                (avatar_gb_class, "avatar_gb_class: a.gb_B"),
                (avatar_data, "avatar_data: data-ogsr-up"),
            ]
            for avatar_locator, desc in avatar_checks:
                try:
                    count = await avatar_locator.count()
                    if count > 0:
                        if await avatar_locator.first.is_visible():
                            print(f"[GoogleAuth] ✅ 检测到登录成功! ({desc})")
                            return True, "登录成功"
                except Exception as e:
                    pass  # 单个检测失败不影响其他
        except Exception as e:
            print(f"[GoogleAuth] 头像检测异常: {e}")
        
        # 优先级2: 检查错误信息
        if await error_locator.count() > 0:
            try:
                if await error_locator.first.is_visible():
                    print(f"[GoogleAuth] ❌ 检测到密码错误")
                    return False, "密码错误"
            except:
                pass
        
        # 优先级3: 处理2FA验证码
        if await totp_input.count() > 0:
            try:
                if await totp_input.first.is_visible():
                    secret = account_info.get('secret') or account_info.get('2fa_secret') or account_info.get('secret_key') or account_info.get('twofa_key')
                    if secret:
                        code = pyotp.TOTP(secret.replace(" ", "")).now()
                        
                        # 检查是否与上次输入的验证码相同（防止重复输入）
                        if code == last_2fa_code:
                            print(f"[GoogleAuth] ⏳ 2FA验证码未变化，等待页面响应...")
                            await asyncio.sleep(1)
                            # 检查是否已经登录成功
                            if 'myaccount.google.com' in page.url:
                                print(f"[GoogleAuth] ✅ 页面已跳转，登录成功!")
                                return True, "登录成功"
                            continue
                        
                        await totp_input.fill(code)
                        last_2fa_code = code  # 记录已输入的验证码
                        print(f"[GoogleAuth] ✅ 已输入2FA验证码: {code}")
                        await asyncio.sleep(0.5)
                        
                        # 点击下一步（使用短超时，因为页面可能立即跳转）
                        totp_next = page.locator('#totpNext >> button')
                        try:
                            if await totp_next.count() > 0:
                                await totp_next.click(timeout=3000)  # 短超时
                        except Exception as click_err:
                            # 点击失败可能是因为页面已经跳转（登录成功）
                            current_url = page.url
                            if 'myaccount.google.com' in current_url:
                                print(f"[GoogleAuth] ✅ 2FA后页面已跳转，登录成功!")
                                return True, "登录成功"
                            print(f"[GoogleAuth] ⚠️ 2FA下一步点击失败: {click_err}")
                        
                        await asyncio.sleep(1)
                        
                        # 输入后立即检查是否已跳转到登录成功页面
                        if 'myaccount.google.com' in page.url:
                            print(f"[GoogleAuth] ✅ 2FA验证后登录成功!")
                            return True, "登录成功"
                        
                        continue
                    else:
                        print(f"[GoogleAuth] ⚠️ 需要2FA但未提供密钥")
                        return False, "需要2FA验证但未提供密钥"
            except Exception as e:
                # 异常时也检查是否已经登录成功
                if 'myaccount.google.com' in page.url:
                    print(f"[GoogleAuth] ✅ 2FA异常但页面已跳转，登录成功!")
                    return True, "登录成功"
                print(f"[GoogleAuth] 2FA处理异常: {e}")
        
        # 优先级4: 处理选择验证方式 (需要先点击选择辅助邮箱)
        # 先检测是否在 "Verify it's you" 页面
        verify_page = page.get_by_text("Verify it's you", exact=True).or_(page.get_by_text("验证是您本人", exact=True))
        if await verify_page.count() > 0:
            print(f"[GoogleAuth] 🔐 检测到 'Verify it's you' 验证页面")
        
        # 分别检查每个选择器
        recovery_count = await recovery_option.count()
        if recovery_count > 0:
            print(f"[GoogleAuth] 📧 找到辅助邮箱选项! 数量: {recovery_count}")
            try:
                first_option = recovery_option.first
                if await first_option.is_visible():
                    print(f"[GoogleAuth] ✅ 辅助邮箱选项可见，正在点击...")
                    await first_option.click()
                    print(f"[GoogleAuth] ✅ 已点击辅助邮箱选项!")
                    await asyncio.sleep(2)
                    continue  # 点击后继续循环，等待输入框出现
                else:
                    print(f"[GoogleAuth] ⚠️ 辅助邮箱选项找到但不可见")
            except Exception as e:
                print(f"[GoogleAuth] ❌ 验证方式选择异常: {e}")
        else:
            # 单独检查 data-challengeid="5"
            challenge5 = page.locator('[data-challengeid="5"]')
            c5_count = await challenge5.count()
            if c5_count > 0:
                print(f"[GoogleAuth] 🔍 直接找到 data-challengeid=5, 尝试点击...")
                try:
                    await challenge5.first.click()
                    print(f"[GoogleAuth] ✅ 已通过 challengeid=5 点击!")
                    await asyncio.sleep(2)
                    continue
                except Exception as e:
                    print(f"[GoogleAuth] ❌ challengeid=5 点击失败: {e}")
        
        # 优先级5: 处理直接输入辅助邮箱
        if await recovery_input.count() > 0:
            try:
                if await recovery_input.first.is_visible():
                    backup = account_info.get('backup') or account_info.get('backup_email') or account_info.get('recovery_email') or account_info.get('recoveryEmail')
                    if backup:
                        await recovery_input.fill(backup)
                        print(f"[GoogleAuth] ✅ 已输入辅助邮箱: {backup}")
                        await asyncio.sleep(0.5)
                        
                        # 点击下一步（使用短超时）
                        next_btn = page.locator('button:has-text("Next"), button:has-text("下一步")')
                        try:
                            if await next_btn.count() > 0:
                                await next_btn.first.click(timeout=3000)
                        except Exception as click_err:
                            # 点击失败可能是因为页面已经跳转
                            if 'myaccount.google.com' in page.url:
                                print(f"[GoogleAuth] ✅ 辅助邮箱验证后登录成功!")
                                return True, "登录成功"
                            print(f"[GoogleAuth] ⚠️ 辅助邮箱下一步点击失败: {click_err}")
                        
                        await asyncio.sleep(1)
                        
                        # 检查是否已跳转到登录成功页面
                        if 'myaccount.google.com' in page.url:
                            print(f"[GoogleAuth] ✅ 辅助邮箱验证后登录成功!")
                            return True, "登录成功"
                        
                        continue
                    else:
                        print(f"[GoogleAuth] ⚠️ 需要辅助邮箱但未提供")
                        return False, "需要辅助邮箱验证但未提供"
            except Exception as e:
                # 异常时也检查是否已经登录成功
                if 'myaccount.google.com' in page.url:
                    print(f"[GoogleAuth] ✅ 辅助邮箱异常但已登录成功!")
                    return True, "登录成功"
                print(f"[GoogleAuth] 辅助邮箱处理异常: {e}")
        
        # 优先级6: 处理弹窗
        if await popup_buttons.count() > 0:
            try:
                # 找到第一个可见的弹窗按钮并点击
                for i in range(await popup_buttons.count()):
                    btn = popup_buttons.nth(i)
                    if await btn.is_visible():
                        btn_text = await btn.inner_text()
                        await btn.click()
                        print(f"[GoogleAuth] 🔘 已处理弹窗: {btn_text}")
                        await asyncio.sleep(0.5)
                        break
            except Exception as e:
                print(f"[GoogleAuth] 弹窗处理异常: {e}")
        
        await asyncio.sleep(0.5)
    
    # 循环结束仍未成功
    print(f"[GoogleAuth] ⚠️ 验证循环结束，未能确认登录状态")
    return None, "验证超时"


async def get_login_state(page: Page, timeout: float = 5000) -> Tuple[str, Optional[str]]:
    """
    @brief 智能检测当前登录状态
    @param page Playwright 页面对象
    @param timeout 检测超时时间(ms)
    @return (status, email)
            status: 'logged_in' | 'not_logged_in' | 'unknown'
            email: 已登录邮箱或None
    """
    try:
        # ==================== 最优先: URL-based 登录检测 ====================
        # 这是最可靠的方式，某些Google页面只有登录后才能访问
        current_url = page.url
        print(f"[GoogleAuth] get_login_state: 当前URL = {current_url[:80]}...")
        
        # 这些URL只有登录后才能访问
        logged_in_urls = [
            'myaccount.google.com',
            'mail.google.com',
            'drive.google.com', 
            'one.google.com',
            'photos.google.com',
            'calendar.google.com',
            'contacts.google.com',
        ]
        
        for url_pattern in logged_in_urls:
            if url_pattern in current_url:
                print(f"[GoogleAuth] ✅ URL检测已登录: {url_pattern}")
                email = await _extract_logged_in_email(page)
                return GoogleLoginStatus.LOGGED_IN, email
        
        # ==================== 元素检测 ====================
        # 定义定位器 - 多种头像检测模式 (与 verify_after_password 保持一致)
        # 模式1: role="button" 的元素，aria-label 包含 "Google Account"
        avatar_button = page.get_by_role("button", name=re.compile(r"Google (Account|帐号|账号)", re.IGNORECASE))
        # 模式2: 直接通过 href 包含 SignOutOptions
        avatar_signout_link = page.locator('a[href*="accounts.google.com/SignOutOptions"]')
        # 模式3: 通过 aria-label 包含邮箱格式 @
        avatar_with_email = page.locator('a[aria-label*="@"][href*="accounts.google.com"]')
        # 模式4: 通过类名 gb_B
        avatar_gb_class = page.locator('a.gb_B[role="button"][aria-label*="Google"]')
        # 模式5: 头像容器
        avatar_data = page.locator('[data-ogsr-up], [data-ogpc]')
        # 组合所有头像检测模式
        avatar = avatar_button.or_(avatar_signout_link).or_(avatar_with_email).or_(avatar_gb_class).or_(avatar_data.first)
        email_input = page.locator('input[type="email"]')
        
        # 组合定位器
        combined = avatar.or_(email_input)
        
        try:
            await expect(combined).to_be_visible(timeout=timeout)
            
            # 判断状态
            if await avatar.count() > 0 and await avatar.first.is_visible():
                email = await _extract_logged_in_email(page)
                print(f"[GoogleAuth] ✅ 头像检测已登录: {email}")
                return GoogleLoginStatus.LOGGED_IN, email
                
            elif await email_input.count() > 0 and await email_input.first.is_visible():
                print(f"[GoogleAuth] 📝 检测到登录表单 (未登录)")
                return GoogleLoginStatus.NOT_LOGGED_IN, None
                
        except:
            pass
            
        print(f"[GoogleAuth] ⚠️ 状态未知 (元素超时)")
        return GoogleLoginStatus.UNKNOWN, None
        
    except Exception as e:
        print(f"[GoogleAuth] 状态检测异常: {e}")
        return GoogleLoginStatus.UNKNOWN, None


async def google_login(page: Page, account_info: dict) -> Tuple[bool, str]:
    """
    @brief 统一的 Google 登录函数 (V3 - 智能检测版)
    @param page Playwright 页面对象
    @param account_info 账号信息
    @return (success, message)
    """
    email = account_info.get('email', '')
    password = account_info.get('password', '')
    max_retries = 3
    
    print(f"[GoogleAuth] 开始登录: {email}")
    
    for retry in range(max_retries):
        try:
            # Step 1: 智能检测状态
            print(f"[GoogleAuth] Step 1: 智能检测页面状态...")
            status, current_email = await get_login_state(page)
            
            # 情况1: 已登录
            if status == GoogleLoginStatus.LOGGED_IN:
                if current_email and email.lower() in current_email.lower():
                    print(f"[GoogleAuth] ✅ 已登录目标账号: {current_email}")
                    return True, "已登录"
                else:
                    print(f"[GoogleAuth] ⚠️ 当前账号: {current_email}，需要切换")
                    return True, f"已登录其他账号: {current_email}"
            
            # 情况2: 未知状态或未登录 (但没找到输入框)，跳转登录页
            if status == GoogleLoginStatus.UNKNOWN:
                print(f"[GoogleAuth] 跳转到 Google 登录页...")
                await page.goto('https://accounts.google.com/', wait_until='domcontentloaded', timeout=DEFAULT_TIMEOUT)
                await asyncio.sleep(1)  # 等待可能的重定向
                
                # 检查是否被重定向到已登录页面 (URL-based)
                current_url = page.url
                print(f"[GoogleAuth] 导航后URL: {current_url[:80]}...")
                
                if 'myaccount.google.com' in current_url:
                    print(f"[GoogleAuth] ✅ 已重定向到 myaccount，已登录状态")
                    return True, "已登录"
                
                # 再次检测
                status, current_email = await get_login_state(page)
                if status == GoogleLoginStatus.LOGGED_IN:
                    return True, "已登录"
                elif status == GoogleLoginStatus.UNKNOWN:
                    # 最后检查：可能在某个需要登录的页面
                    if 'accounts.google.com/signin' not in current_url and 'identifier' not in current_url:
                        print(f"[GoogleAuth] ⚠️ 页面状态异常，URL: {current_url}")
                    return False, "无法加载登录页面"
            
            # Step 3: 执行登录 (状态为 NOT_LOGGED_IN)
            email_input = page.locator('input[type="email"]')
            
            # 填写邮箱
            print(f"[GoogleAuth] Step 3: 填写邮箱...")
            await email_input.fill(email)
            await asyncio.sleep(0.3)
            
            # 点击下一步
            next_button = page.locator('#identifierNext >> button')
            await next_button.click()
            
            # Step 4: 等待密码框
            print(f"[GoogleAuth] Step 4: 等待密码框...")
            password_input = page.locator('input[type="password"]')
            
            try:
                await expect(password_input.first).to_be_visible(timeout=DEFAULT_TIMEOUT)
            except:
                if await page.locator('text="Couldn\'t find your Google Account"').count() > 0:
                    return False, "账号不存在"
                if retry < max_retries - 1:
                    continue
                return False, "密码框未出现"
            
            # Step 5: 填写密码
            print(f"[GoogleAuth] Step 5: 填写密码...")
            await password_input.fill(password)
            await asyncio.sleep(0.3)
            
            await page.locator('#passwordNext >> button').click()
            
            # Step 6: 智能处理后续验证 (使用 .or() 竞争判断)
            print(f"[GoogleAuth] Step 6: 智能处理后续验证...")
            
            result = await _handle_post_password_verification(page, account_info)
            if result[0] is not None:
                return result
            
            if retry < max_retries - 1:
                continue
                
        except Exception as e:
            print(f"[GoogleAuth] 登录异常: {e}")
            if retry < max_retries - 1:
                continue
            return False, f"登录异常: {e}"
            
    return False, "登录失败"


# ==================== 资格检测函数 ====================

# 资格检测页面 URL
GOOGLE_ONE_STUDENT_URL = "https://one.google.com/ai-student?g1_landing_page=75&utm_source=antigravity&utm_campaign=argon_limit_reached"


def _parse_api_response(response_text: str) -> Optional[str]:
    """
    @brief 解析 GI6Jdd API 响应判断订阅状态
    @param response_text API 响应文本
    @return 'subscribed_antigravity' | 'subscribed' | None
    """
    try:
        # 检查订阅状态
        # 响应通常包含 JSON 数组，这里简化做字符串匹配
        has_2tb = '2 TB' in response_text or '2TB' in response_text or '"2 TB"' in response_text
        has_antigravity = 'Antigravity' in response_text or '"Antigravity"' in response_text
        
        if has_2tb:
            if has_antigravity:
                return STATUS_SUBSCRIBED_ANTIGRAVITY
            else:
                return STATUS_SUBSCRIBED
        return None
    except Exception:
        return None


async def check_google_one_status(
    page: Page,
    timeout: float = 20.0
) -> Tuple[str, Optional[str]]:
    """
    @brief V3资格检测：导航 + API拦截 + 资格检测 (不含登录检测)
    @details 流程：
             1. 注册 API 响应拦截 (rpcids=GI6Jdd)
             2. 导航到资格检测页面
             3. 根据 API 响应判断订阅状态
             4. 使用 .or() 并行检测其他资格状态
             注：调用方需自行确保已登录
    @param page Playwright 页面对象
    @param timeout 超时时间(秒)
    @return (status, sheerid_link)
            status: 'subscribed_antigravity' | 'subscribed' | 'verified' | 'link_ready' | 'ineligible' | 'error'
    """
    api_response_data = None
    response_received = asyncio.Event()
    
    async def handle_response(response):
        """响应拦截处理"""
        nonlocal api_response_data
        try:
            # 关键特征 rpcids=GI6Jdd
            if 'rpcids=GI6Jdd' in response.url:
                text = await response.text()
                api_response_data = text
                response_received.set()
                print(f"[GoogleAuth] 🔍 拦截到 GI6Jdd API 响应")
        except Exception:
            pass
    
    # 注册响应监听器
    page.on("response", handle_response)
    
    try:
        # ============ Step 1: 导航到资格检测页面 ============
        print(f"[GoogleAuth] 导航到资格检测页面...")
        await page.goto(GOOGLE_ONE_STUDENT_URL, wait_until="domcontentloaded", timeout=timeout * 1000)

        # 等待 API 响应 (最多 timeout 秒)
        try:
            await asyncio.wait_for(response_received.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass  # 超时没收到API，继续检查元素

        # 等待页面基本加载
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except:
            pass

        # ============ Step 2: 优先根据 API 响应判断订阅状态 ============
        if api_response_data:
            api_status = _parse_api_response(api_response_data)
            if api_status:
                print(f"[GoogleAuth] 🎯 API 响应判断状态: {api_status}")
                return api_status, None

        # ============ Step 3: 使用 .or() 并行检测其他资格状态 ============
        return await detect_eligibility_status(page, timeout=timeout)

    except Exception as e:
        print(f"[GoogleAuth] 资格检测异常: {e}")
        return STATUS_ERROR, str(e)
    
    finally:
        # 移除监听器
        page.remove_listener("response", handle_response)


async def detect_eligibility_status(page: Page, timeout: float = 15.0) -> Tuple[str, Optional[str]]:
    """
    @brief 使用 .or() 并行检测资格状态 (封装函数，可独立调用)
    @details 同时检测多种状态，哪个先出现就返回对应结果：
             - sheerid.com 链接 → link_ready (有资格未验证)
             - jsname="V67aGc":not([aria-hidden]) → verified (已验证未绑卡)
             - 无资格文本 → ineligible
             注：已订阅状态通过 API 响应 (rpcids=GI6Jdd) 判断，不在此函数检测
    @param page Playwright 页面对象
    @param timeout 检测超时时间(秒)
    @return (status, sheerid_link)
    """
    try:
        # ==================== 定义所有状态的定位器 ====================
        
        # 1. SheerID 链接 (有资格未验证) - 包含 sheerid.com 的链接
        sheerid_locator = page.locator('a[href*="sheerid.com"]')
        
        # 2. 已验证未绑卡 - jsname="V67aGc" 且无 aria-hidden="true"
        # "Get student offer" 等文案
        verified_locator = page.locator('[jsname="V67aGc"]:not([aria-hidden="true"])')
        
        # 3. 无资格文本 - 常见的拒绝/不可用文案（英文/中文）
        ineligible_locator = (
            page.locator('text=/isn.t eligible/i')  # isn't eligible
            .or_(page.locator('text=/not eligible/i'))
            .or_(page.locator('text=/not available/i'))
            .or_(page.locator('text=/ineligible/i'))
            .or_(page.locator('text=/unavailable/i'))
            .or_(page.locator('text="不符合条件"'))
            .or_(page.locator('text="无法使用"'))
            .or_(page.locator('text="不可用"'))
            .or_(page.locator('text=/under a certain age/i'))  # 年龄限制文案
        )
        
        # ==================== 🔑 并行竞争：翻译检测 + 元素检测 ====================
        
        async def translate_h1_check():
            """翻译 h1 检测无资格（多语言通用）"""
            try:
                h1_loc = page.locator('h1')
                if await h1_loc.count() == 0:
                    return None
                h1_text = await h1_loc.first.inner_text(timeout=3000)
                if not h1_text or len(h1_text) < 5:
                    return None
                
                chinese_keywords = ["无", "没有", "不"]
                
                # 先检查原文
                for kw in chinese_keywords:
                    if kw in h1_text:
                        print(f"[GoogleAuth] ❌ h1 原文含 '{kw}': {h1_text[:30]}...")
                        return STATUS_INELIGIBLE
                
                # 翻译成中文
                from deep_translator import GoogleTranslator
                translated = GoogleTranslator(source='auto', target='zh-CN').translate(h1_text)
                print(f"[GoogleAuth] 🌐 h1 翻译: {translated[:30]}...")
                
                for kw in chinese_keywords:
                    if kw in translated:
                        print(f"[GoogleAuth] ❌ 翻译后含 '{kw}'")
                        return STATUS_INELIGIBLE
                return None
            except Exception as e:
                return None
        
        async def element_check():
            """元素定位器检测"""
            combined = sheerid_locator.or_(verified_locator).or_(ineligible_locator)
            try:
                await expect(combined).to_be_visible(timeout=timeout * 1000)
                return "element_ready"
            except:
                return None
        
        # 并行执行，哪个先完成就用哪个
        translate_task = asyncio.create_task(translate_h1_check())
        element_task = asyncio.create_task(element_check())
        
        done, pending = await asyncio.wait(
            [translate_task, element_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 清理未完成的任务（避免 "Future exception was never retrieved" 警告）
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass  # 忽略取消异常和其他异常
        
        # 检查翻译结果（如果翻译先完成且检测到无资格）
        if translate_task in done:
            try:
                translate_result = translate_task.result()
                if translate_result == STATUS_INELIGIBLE:
                    return STATUS_INELIGIBLE, None
            except Exception:
                pass
        
        # ==================== 判断具体是哪个状态 (按优先级) ====================
        
        # 优先级1: 检查 SheerID 链接 (有资格未验证)
        if await sheerid_locator.count() > 0:
            try:
                if await sheerid_locator.first.is_visible():
                    sheerid_link = await sheerid_locator.first.get_attribute("href")
                    if sheerid_link:
                        print(f"[GoogleAuth] 🔗 检测到 SheerID 链接: {sheerid_link}")
                        return STATUS_LINK_READY, sheerid_link
            except:
                pass
        
        # 优先级2: 检查已验证未绑卡
        if await verified_locator.count() > 0:
            try:
                if await verified_locator.first.is_visible():
                    text = await verified_locator.first.inner_text()
                    print(f"[GoogleAuth] ✅ 检测到已验证元素: {text}")
                    return STATUS_VERIFIED, None
            except:
                pass
        
        # 优先级3: 检查无资格
        if await ineligible_locator.count() > 0:
            try:
                if await ineligible_locator.first.is_visible():
                    text = await ineligible_locator.first.inner_text()
                    print(f"[GoogleAuth] ❌ 检测到无资格: {text}")
                    return STATUS_INELIGIBLE, None
            except:
                pass
        
        # ==================== 备选方案：从页面源码提取 SheerID 链接 ====================
        sheerid_link = await _extract_sheerid_link_from_content(page)
        if sheerid_link:
            print(f"[GoogleAuth] 🔗 从源码提取到 SheerID 链接: {sheerid_link}")
            return STATUS_LINK_READY, sheerid_link
        
        # ==================== 其他情况默认无资格 ====================
        print(f"[GoogleAuth] ❌ 未检测到明确资格标识，判定为无资格")
        return STATUS_INELIGIBLE, None

    except Exception as e:
        print(f"[GoogleAuth] 资格检测异常: {e}")
        return STATUS_INELIGIBLE, None


# ==================== 辅助函数 ====================

async def _extract_sheerid_link_from_content(page: Page) -> Optional[str]:
    """从页面源码中正则提取 SheerID 链接"""
    try:
        content = await page.content()
        match = re.search(r'https://[^"\']*sheerid\.com[^"\']*', content)
        if match:
            return match.group(0)
        return None
    except:
        return None


async def _check_ineligible_by_translation(page: Page) -> bool:
    """
    @brief 通过翻译检测无资格状态（支持多语言）
    @details 提取页面 h1 标题，翻译成中文后检测是否包含"无"或"没有"
    @param page Playwright 页面对象
    @return True 表示无资格，False 表示未检测到
    """
    try:
        # 提取 h1 标题文本
        h1_locator = page.locator('h1')
        if await h1_locator.count() == 0:
            return False
        
        h1_text = await h1_locator.first.inner_text()
        if not h1_text or len(h1_text) < 5:
            return False
        
        print(f"[GoogleAuth] 🌐 检测到标题 (原文): {h1_text[:50]}...")
        
        # 中文无资格关键词（简单有效）
        chinese_ineligible_keywords = ["无", "没有", "不"]
        
        # 如果已经是中文，直接匹配
        for keyword in chinese_ineligible_keywords:
            if keyword in h1_text:
                print(f"[GoogleAuth] ❌ 标题包含无资格关键词: {keyword}")
                return True
        
        # 尝试导入翻译库，翻译成中文
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source='auto', target='zh-CN')
            translated = translator.translate(h1_text)
            
            print(f"[GoogleAuth] 🌐 翻译成中文: {translated[:50]}...")
            
            # 检测翻译后的文本是否包含无资格关键词
            for keyword in chinese_ineligible_keywords:
                if keyword in translated:
                    print(f"[GoogleAuth] ❌ 翻译后包含无资格关键词: {keyword}")
                    return True
                    
        except ImportError:
            print("[GoogleAuth] ⚠️ deep-translator 未安装，跳过翻译检测")
        except Exception as translate_err:
            print(f"[GoogleAuth] ⚠️ 翻译失败: {translate_err}")
            # 翻译失败时，检查是否包含 "Google AI Pro"（产品名不翻译）
            if "Google AI Pro" in h1_text:
                print(f"[GoogleAuth] ❌ 标题包含 'Google AI Pro'，疑似无资格页面")
                return True
        
        return False
        
    except Exception as e:
        print(f"[GoogleAuth] ⚠️ 翻译检测异常: {e}")
        return False


async def _extract_logged_in_email(page: Page) -> Optional[str]:
    """
    @brief 提取已登录邮箱
    @details 尝试从 aria-label 属性提取邮箱
             格式如: "Google Account: Name (email@gmail.com)"
    """
    try:
        # 尝试从 aria-label 提取
        label_locator = page.locator('a[aria-label*="Google"]')
        if await label_locator.count() > 0:
            label = await label_locator.first.get_attribute('aria-label') or ""
            match = re.search(r'[\w\.-]+@[\w\.-]+', label)
            if match:
                return match.group(0)

        # 备选：从按钮的 aria-label 提取
        btn_locator = page.locator('button[aria-label*="Google"]')
        if await btn_locator.count() > 0:
            label = await btn_locator.first.get_attribute('aria-label') or ""
            match = re.search(r'[\w\.-]+@[\w\.-]+', label)
            if match:
                return match.group(0)

    except:
        pass
    return None
