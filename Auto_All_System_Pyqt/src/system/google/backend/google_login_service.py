"""
@file google_login_service.py
@brief Google登录服务模块 (V3)
@details 提供完整的Google账号登录功能，结合比特浏览器和登录状态检测
         使用V3检测模块 (Playwright .or() 智能等待)
"""

import asyncio
import time
from typing import Tuple, Optional, Dict, Any, Callable
from playwright.async_api import async_playwright, Page, BrowserContext

from .google_auth import (
    GoogleLoginStatus,
    get_login_state,   # V3: 替代 check_google_login_status
    google_login,
)


class GoogleLoginService:
    """
    @brief Google登录服务类
    @details 封装完整的登录流程，支持比特浏览器集成
    """
    
    def __init__(self, log_callback: Callable[[str], None] = None):
        """
        @brief 初始化登录服务
        @param log_callback 日志回调函数
        """
        self.log_callback = log_callback or print
        self._bit_api = None
    
    def log(self, message: str):
        """输出日志"""
        self.log_callback(f"[GoogleLoginService] {message}")
    
    def _get_bit_api(self):
        """获取比特浏览器API实例"""
        if self._bit_api is None:
            try:
                # 尝试从core模块导入
                from core.bit_api import openBrowser, closeBrowser
                self._bit_api = {'open': openBrowser, 'close': closeBrowser}
            except ImportError:
                try:
                    # 尝试从_legacy导入
                    import sys
                    import os
                    legacy_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '_legacy')
                    if legacy_dir not in sys.path:
                        sys.path.insert(0, legacy_dir)
                    from bit_api import openBrowser, closeBrowser
                    self._bit_api = {'open': openBrowser, 'close': closeBrowser}
                except ImportError:
                    self._bit_api = None
        return self._bit_api
    
    async def login_with_playwright(
        self, 
        page: Page, 
        account_info: dict,
        force_login: bool = False
    ) -> Tuple[bool, str, str]:
        """
        @brief 使用已有的Playwright页面执行登录
        @param page Playwright页面对象
        @param account_info 账号信息字典
        @param force_login 是否强制重新登录（即使已登录）
        @return (success, status, message)
        """
        email = account_info.get('email', 'unknown')
        self.log(f"开始登录: {email}")
        
        # 1. 首先检查当前登录状态 (V3: 使用 get_login_state)
        status, current_email = await get_login_state(page)
        self.log(f"当前状态: {status}")
        
        if status == GoogleLoginStatus.LOGGED_IN and not force_login:
            if current_email:
                if current_email.lower() == email.lower():
                    self.log(f"已登录正确账号: {current_email}")
                    return True, "already_logged_in", f"已登录: {current_email}"
                else:
                    self.log(f"当前登录账号 {current_email} 与目标 {email} 不符")
                    # 需要切换账号，先登出
                    await self._logout(page)
            else:
                self.log("已登录但无法确定账号")
                return True, "logged_in_unknown", "已登录（账号未知）"
        
        # 2. 执行登录流程
        success, message = await google_login(page, account_info)
        
        if success:
            # 3. 验证登录结果 (V3: 使用 get_login_state)
            await asyncio.sleep(2)
            final_status, final_email = await get_login_state(page)
            
            if final_status == GoogleLoginStatus.LOGGED_IN:
                logged_email = final_email or email
                self.log(f"登录成功: {logged_email}")
                return True, "login_success", f"登录成功: {logged_email}"
            else:
                self.log(f"登录后状态异常: {final_status}")
                return False, final_status, f"登录后状态: {final_status}"
        else:
            self.log(f"登录失败: {message}")
            return False, "login_failed", message
    
    async def _logout(self, page: Page):
        """
        @brief 登出当前账号
        @param page Playwright页面对象
        """
        try:
            self.log("正在登出...")
            await page.goto("https://accounts.google.com/Logout", timeout=30000)
            await asyncio.sleep(2)
        except Exception as e:
            self.log(f"登出异常: {e}")
    
    def login_browser_sync(
        self,
        browser_id: str,
        account_info: dict = None,
        target_url: str = None,
        close_after: bool = True
    ) -> Tuple[bool, str, str]:
        """
        @brief 同步方式登录比特浏览器窗口
        @param browser_id 比特浏览器窗口ID
        @param account_info 账号信息（如果为None则从数据库获取）
        @param target_url 登录后跳转的URL
        @param close_after 完成后是否关闭浏览器
        @return (success, status, message)
        """
        return asyncio.run(self._login_browser_async(
            browser_id, account_info, target_url, close_after
        ))
    
    async def _login_browser_async(
        self,
        browser_id: str,
        account_info: dict = None,
        target_url: str = None,
        close_after: bool = True
    ) -> Tuple[bool, str, str]:
        """异步登录比特浏览器窗口"""
        bit_api = self._get_bit_api()
        if not bit_api:
            return False, "error", "比特浏览器API不可用"
        
        # 1. 获取账号信息（如果未提供）
        if not account_info:
            account_info = await self._get_account_from_db(browser_id)
            if not account_info:
                return False, "error", "无法获取账号信息"
        
        self.log(f"打开浏览器: {browser_id}")
        
        # 2. 打开浏览器
        res = bit_api['open'](browser_id)
        if not res or not res.get('success'):
            return False, "error", f"打开浏览器失败: {res}"
        
        ws_endpoint = res.get('data', {}).get('ws')
        if not ws_endpoint:
            return False, "error", "无法获取WebSocket端点"
        
        try:
            # 3. 连接Playwright
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()
                
                # 4. 执行登录
                success, status, message = await self.login_with_playwright(page, account_info)
                
                # 5. 如果有目标URL，导航过去
                if success and target_url:
                    try:
                        await page.goto(target_url, timeout=30000)
                        await asyncio.sleep(2)
                    except Exception as e:
                        self.log(f"导航到目标URL失败: {e}")
                
                return success, status, message
                
        except Exception as e:
            self.log(f"登录异常: {e}")
            return False, "error", str(e)
        finally:
            if close_after and bit_api:
                self.log(f"关闭浏览器: {browser_id}")
                bit_api['close'](browser_id)
    
    async def _get_account_from_db(self, browser_id: str) -> Optional[dict]:
        """从数据库获取账号信息"""
        try:
            from core.database import DBManager
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, password, recovery_email, secret_key 
                FROM accounts WHERE browser_id = ?
            """, (browser_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'email': row[0],
                    'password': row[1],
                    'backup': row[2],
                    'backup_email': row[2],
                    'secret': row[3],
                    '2fa_secret': row[3],
                    'secret_key': row[3]
                }
        except Exception as e:
            self.log(f"从数据库获取账号失败: {e}")
        
        return None
    
    async def batch_check_login_status(
        self,
        browser_ids: list,
        callback: Callable[[str, str, dict], None] = None
    ) -> Dict[str, Tuple[str, dict]]:
        """
        @brief 批量检查多个浏览器窗口的登录状态
        @param browser_ids 浏览器ID列表
        @param callback 每个窗口检查完成的回调 (browser_id, status, info)
        @return {browser_id: (status, info)}
        """
        results = {}
        bit_api = self._get_bit_api()
        
        if not bit_api:
            return {bid: ("error", {"message": "API不可用"}) for bid in browser_ids}
        
        for browser_id in browser_ids:
            try:
                res = bit_api['open'](browser_id)
                if not res or not res.get('success'):
                    results[browser_id] = ("error", {"message": "打开失败"})
                    continue
                
                ws_endpoint = res.get('data', {}).get('ws')
                if not ws_endpoint:
                    results[browser_id] = ("error", {"message": "无WS端点"})
                    bit_api['close'](browser_id)
                    continue
                
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
                    context = browser.contexts[0]
                    page = context.pages[0] if context.pages else await context.new_page()
                    
                    # 导航到Google账号页面检查
                    try:
                        await page.goto("https://myaccount.google.com", timeout=30000)
                        await asyncio.sleep(2)
                    except:
                        pass
                    
                    # V3: 使用 get_login_state
                    status, email = await get_login_state(page)
                    info = {"email": email} if email else {}
                    results[browser_id] = (status, info)
                    
                    if callback:
                        callback(browser_id, status, info)
                
                bit_api['close'](browser_id)
                await asyncio.sleep(1)  # 避免API过载
                
            except Exception as e:
                results[browser_id] = ("error", {"message": str(e)})
                try:
                    bit_api['close'](browser_id)
                except:
                    pass
        
        return results


# ==================== 便捷函数 ====================

def login_google_account(
    browser_id: str,
    account_info: dict = None,
    log_callback: Callable = None
) -> Tuple[bool, str, str]:
    """
    @brief 便捷函数：登录Google账号
    @param browser_id 比特浏览器窗口ID
    @param account_info 账号信息（可选，默认从数据库获取）
    @param log_callback 日志回调
    @return (success, status, message)
    
    使用示例:
        success, status, msg = login_google_account("abc123")
        if success:
            print(f"登录成功: {msg}")
    """
    service = GoogleLoginService(log_callback)
    return service.login_browser_sync(browser_id, account_info)


def check_browser_login_status(
    browser_id: str,
    log_callback: Callable = None
) -> Tuple[str, dict]:
    """
    @brief 便捷函数：检查浏览器窗口的登录状态
    @param browser_id 比特浏览器窗口ID
    @param log_callback 日志回调
    @return (status, info)
    """
    service = GoogleLoginService(log_callback)
    results = asyncio.run(service.batch_check_login_status([browser_id]))
    return results.get(browser_id, ("error", {}))


async def quick_login_check(page: Page) -> bool:
    """
    @brief 快速检查页面是否已登录Google
    @param page Playwright页面对象
    @return True已登录，False未登录
    """
    # V3: 使用 get_login_state
    status, _ = await get_login_state(page, timeout=5000)
    return status == GoogleLoginStatus.LOGGED_IN
