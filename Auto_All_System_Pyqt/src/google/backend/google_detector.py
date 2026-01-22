"""
@file google_detector.py
@brief Google 登录与资格检测模块 (V2)
@details 使用 Playwright 智能等待 + API 拦截实现可靠检测
"""
import asyncio
import re
from typing import Tuple, Optional
from playwright.async_api import Page, expect


# ==================== 登录状态检测 ====================

async def check_google_login_by_avatar(page: Page, timeout: float = 10.0) -> bool:
    """
    @brief 通过检测头像按钮判断是否已登录
    @param page Playwright 页面对象
    @param timeout 超时时间(秒)
    @return True=已登录, False=未登录
    """
    try:
        # 导航到 Google 账号页面
        await page.goto(
            "https://accounts.google.com/",
            wait_until="domcontentloaded",
            timeout=timeout * 1000
        )
        
        # 头像按钮选择器 (多个备选)
        avatar_selectors = [
            'a[aria-label*="Google Account"] img.gbii',
            'a.gb_B[role="button"] img',
            'a[href*="SignOutOptions"] img',
            'img.gb_Q.gbii',
        ]
        
        # 尝试检测头像元素
        for selector in avatar_selectors:
            try:
                avatar_locator = page.locator(selector)
                # 使用 expect 自动重试等待
                await expect(avatar_locator.first).to_be_visible(timeout=timeout * 1000)
                print(f"[GoogleDetector] ✅ 检测到头像元素: {selector} -> 已登录")
                return True
            except Exception:
                continue
        
        print("[GoogleDetector] ❌ 未检测到头像元素 -> 未登录")
        return False
        
    except Exception as e:
        print(f"[GoogleDetector] 登录检测异常: {e}")
        return False


async def is_on_login_page(page: Page) -> bool:
    """
    @brief 判断当前是否在登录页面
    @param page Playwright 页面对象
    @return True=在登录页面
    """
    try:
        current_url = page.url
        login_indicators = [
            'accounts.google.com/v3/signin',
            'accounts.google.com/signin',
            'accounts.google.com/ServiceLogin',
        ]
        return any(indicator in current_url for indicator in login_indicators)
    except:
        return False


# ==================== 资格状态检测 ====================

async def check_google_one_status_v2(
    page: Page, 
    timeout: float = 20.0
) -> Tuple[str, Optional[str]]:
    """
    @brief 通过 API 拦截 + jsname 属性检测资格状态
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
            if 'rpcids=GI6Jdd' in response.url:
                text = await response.text()
                api_response_data = text
                response_received.set()
                print(f"[GoogleDetector] 🔍 拦截到 GI6Jdd API 响应 ({len(text)} bytes)")
        except Exception as e:
            print(f"[GoogleDetector] API响应处理异常: {e}")
    
    # 注册响应监听器
    page.on("response", handle_response)
    
    try:
        print("[GoogleDetector] 🌐 导航到 Google One 学生页面...")
        
        # 导航到目标页面
        await page.goto(
            "https://one.google.com/ai-student?g1_landing_page=75",
            wait_until="domcontentloaded",
            timeout=timeout * 1000
        )
        
        # 等待网络空闲或 API 响应
        try:
            await asyncio.wait_for(
                response_received.wait(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("[GoogleDetector] ⚠️ API 响应等待超时，尝试检测页面元素...")
        
        # 等待页面稳定
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # ============ 分析 API 响应 ============
        if api_response_data:
            status = _parse_api_response(api_response_data)
            if status:
                return status, None
        
        # ============ 检测页面元素 ============
        return await _detect_page_elements(page)
        
    except Exception as e:
        print(f"[GoogleDetector] ❌ 资格检测异常: {e}")
        import traceback
        traceback.print_exc()
        return 'error', None
        
    finally:
        # 移除监听器
        page.remove_listener("response", handle_response)


def _parse_api_response(response_text: str) -> Optional[str]:
    """
    @brief 解析 GI6Jdd API 响应
    @param response_text 响应文本
    @return 状态字符串或 None
    """
    try:
        # 检查订阅状态
        has_2tb = '2 TB' in response_text or '2TB' in response_text or '"2 TB"' in response_text
        has_antigravity = 'Antigravity' in response_text or '"Antigravity"' in response_text
        
        if has_2tb:
            if has_antigravity:
                print("[GoogleDetector] ✅ API响应: 已订阅 + 已解锁 Antigravity")
                return 'subscribed_antigravity'
            else:
                print("[GoogleDetector] ✅ API响应: 已订阅 (未解锁 Antigravity)")
                return 'subscribed'
        
        print("[GoogleDetector] API响应: 未检测到订阅状态")
        return None
        
    except Exception as e:
        print(f"[GoogleDetector] API响应解析异常: {e}")
        return None


async def _detect_page_elements(page: Page) -> Tuple[str, Optional[str]]:
    """
    @brief 通过页面元素检测资格状态
    @param page Playwright 页面对象
    @return (status, sheerid_link)
    """
    try:
        # 1. 检查 hSRGPd (有资格待验证 - 含有 SheerID 验证链接)
        link_ready_locator = page.locator('[jsname="hSRGPd"]')
        if await link_ready_locator.count() > 0:
            print("[GoogleDetector] 🔗 检测到 jsname=hSRGPd -> 有资格待验证")
            sheerid_link = await _extract_sheerid_link(page)
            return 'link_ready', sheerid_link
        
        # 2. 检查 V67aGc (已验证未绑卡 - Get student offer 按钮)
        verified_locator = page.locator('[jsname="V67aGc"]')
        if await verified_locator.count() > 0:
            print("[GoogleDetector] ✅ 检测到 jsname=V67aGc -> 已验证未绑卡")
            return 'verified', None
        
        # 3. 再次检查是否有 SheerID 链接 (备选方案)
        sheerid_link = await _extract_sheerid_link(page)
        if sheerid_link:
            print("[GoogleDetector] 🔗 检测到 SheerID 链接 -> 有资格待验证")
            return 'link_ready', sheerid_link
        
        # 4. 检查是否有 "Get student offer" 相关按钮
        offer_selectors = [
            'button:has-text("Get student offer")',
            'button:has-text("Get offer")',
            '[data-action="offerDetails"]',
        ]
        for selector in offer_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    print(f"[GoogleDetector] ✅ 检测到 offer 按钮 -> 已验证未绑卡")
                    return 'verified', None
            except:
                continue
        
        # 5. 其他情况 = 无资格
        print("[GoogleDetector] ❌ 未检测到有效状态 -> 无资格")
        return 'ineligible', None
        
    except Exception as e:
        print(f"[GoogleDetector] 页面元素检测异常: {e}")
        return 'ineligible', None


async def _extract_sheerid_link(page: Page) -> Optional[str]:
    """
    @brief 提取 SheerID 验证链接
    @param page Playwright 页面对象
    @return SheerID 链接或 None
    """
    try:
        # 方法1: 查找 sheerid.com 链接
        sheerid_locator = page.locator('a[href*="sheerid.com"]')
        if await sheerid_locator.count() > 0:
            href = await sheerid_locator.first.get_attribute("href")
            if href:
                print(f"[GoogleDetector] 🔗 提取到 SheerID 链接: {href[:60]}...")
                return href
        
        # 方法2: 从页面内容中查找
        content = await page.content()
        match = re.search(r'https://[^"\']*sheerid\.com[^"\']*', content)
        if match:
            href = match.group(0)
            print(f"[GoogleDetector] 🔗 从内容提取 SheerID 链接: {href[:60]}...")
            return href
        
        return None
        
    except Exception as e:
        print(f"[GoogleDetector] SheerID 链接提取异常: {e}")
        return None


# ==================== 综合检测流程 ====================

async def full_google_detection(
    page: Page,
    account_info: dict = None,
    timeout: float = 20.0
) -> Tuple[bool, str, Optional[str]]:
    """
    @brief 完整的 Google 检测流程 (登录 + 资格)
    @param page Playwright 页面对象
    @param account_info 账号信息 (用于登录)
    @param timeout 超时时间
    @return (is_logged_in, status, sheerid_link)
    """
    # 1. 检测登录状态
    is_logged_in = await check_google_login_by_avatar(page, timeout=timeout)
    
    if not is_logged_in:
        return False, 'not_logged_in', None
    
    # 2. 检测资格状态
    status, sheerid_link = await check_google_one_status_v2(page, timeout=timeout)
    
    return True, status, sheerid_link


# ==================== 状态常量 ====================

# 账号状态定义
STATUS_NOT_LOGGED_IN = 'not_logged_in'
STATUS_SUBSCRIBED_ANTIGRAVITY = 'subscribed_antigravity'
STATUS_SUBSCRIBED = 'subscribed'
STATUS_VERIFIED = 'verified'
STATUS_LINK_READY = 'link_ready'
STATUS_INELIGIBLE = 'ineligible'
STATUS_ERROR = 'error'
STATUS_PENDING = 'pending_check'

# 状态显示映射
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
