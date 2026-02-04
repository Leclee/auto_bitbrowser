"""
@file sheerlink_service.py
@brief SheerID链接提取服务 (V3)
@details 提供Google One学生资格验证链接的自动提取功能，
        使用V3检测模块 (Playwright .or() 智能等待)
"""

import asyncio
from typing import Tuple, Optional, Dict, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.async_api import async_playwright, Page

from .google_auth import (
    check_google_one_status,
    google_login,
    STATUS_SUBSCRIBED_ANTIGRAVITY,
    STATUS_SUBSCRIBED,
    STATUS_VERIFIED,
    STATUS_LINK_READY,
    STATUS_INELIGIBLE,
)
from .account_manager import AccountManager


class SheerLinkService:
    """
    @brief SheerID链接提取服务类
    @details 封装完整的SheerLink提取流程
    """
    
    def __init__(self, log_callback: Callable[[str], None] = None):
        """
        @brief 初始化服务
        @param log_callback 日志回调函数
        """
        self.log_callback = log_callback or print
        self._bit_api = None
    
    def log(self, message: str):
        """输出日志"""
        self.log_callback(f"[SheerLink] {message}")
    
    def _get_bit_api(self):
        """获取比特浏览器API"""
        if self._bit_api is None:
            try:
                from core.bit_api import openBrowser, closeBrowser, get_browser_info
                self._bit_api = {
                    'open': openBrowser, 
                    'close': closeBrowser,
                    'info': get_browser_info
                }
            except ImportError:
                self._bit_api = None
        return self._bit_api
    
    def _get_account_info(self, browser_id: str) -> dict:
        """
        @brief 获取账号信息
        @param browser_id 浏览器窗口ID
        @return 账号信息字典
        """
        account_info = {}
        
        # 1. 优先从数据库获取
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
            
            if row and row[1]:  # 确保有密码
                account_info = {
                    'email': row[0],
                    'password': row[1],
                    'backup': row[2],
                    'backup_email': row[2],
                    'secret': row[3],
                    '2fa_secret': row[3]
                }
                return account_info
        except Exception as e:
            self.log(f"从数据库读取失败: {e}")
        
        # 2. 降级使用浏览器备注
        bit_api = self._get_bit_api()
        if bit_api:
            browser_info = bit_api['info'](browser_id)
            if browser_info:
                remark = browser_info.get('remark', '')
                parts = remark.split('----')
                if len(parts) >= 4:
                    account_info = {
                        'email': parts[0].strip(),
                        'password': parts[1].strip(),
                        'backup': parts[2].strip(),
                        'backup_email': parts[2].strip(),
                        'secret': parts[3].strip(),
                        '2fa_secret': parts[3].strip()
                    }
        
        return account_info
    
    async def extract_sheerlink_async(
        self,
        browser_id: str,
        account_info: dict = None
    ) -> Tuple[bool, str]:
        """
        @brief 异步提取SheerLink
        @param browser_id 浏览器窗口ID
        @param account_info 账号信息（可选）
        @return (success, message)
        """
        bit_api = self._get_bit_api()
        if not bit_api:
            return False, "比特浏览器API不可用"
        
        # 获取账号信息
        if not account_info:
            account_info = self._get_account_info(browser_id)
        
        email = account_info.get('email', 'unknown')
        self.log(f"处理账号: {email}")
        
        # 打开浏览器
        res = bit_api['open'](browser_id)
        if not res or not res.get('success'):
            return False, f"打开浏览器失败: {res.get('msg', '未知错误')}"
        
        ws_endpoint = res.get('data', {}).get('ws')
        if not ws_endpoint:
            bit_api['close'](browser_id)
            return False, "无法获取WebSocket端点"
        
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()
                
                # ============================================================
                # V3: 一键获取 G-SheerLink
                # Step 1: 智能登录（内部自动检测状态，未登录则自动登录）
                # Step 2: 调用资格检测函数（自动获取sheerlink）
                # ============================================================
                
                # Step 1: 智能登录（google_login 内部已集成状态检测）
                self.log("Step 1: 智能登录检测...")
                
                # 先检查当前页面URL，如果已在Google服务页面则可能已登录
                current_url = page.url
                self.log(f"当前页面: {current_url[:60]}...")
                
                if account_info and account_info.get('password'):
                    login_success, login_msg = await google_login(page, account_info)
                    if not login_success:
                        # 额外检查：如果在Google服务页面，可能实际已登录
                        final_url = page.url
                        logged_in_indicators = ['myaccount.google.com', 'mail.google.com', 
                                                 'drive.google.com', 'one.google.com']
                        for indicator in logged_in_indicators:
                            if indicator in final_url:
                                self.log(f"⚠️ 登录函数返回失败，但URL显示已登录: {indicator}")
                                login_success = True
                                login_msg = "已登录 (URL检测)"
                                break
                        
                        if not login_success:
                            self.log(f"登录失败: {login_msg}")
                            return False, f"登录失败: {login_msg}"
                    
                    self.log(f"登录状态: {login_msg}")
                else:
                    self.log("无账号密码信息，跳过登录直接检测资格...")
                
                # Step 2: 调用资格检测函数（自动获取sheerlink）
                self.log("Step 2: 执行资格检测...")
                status, extra_data = await check_google_one_status(page, timeout=30.0)
                
                self.log(f"检测结果: {status}")
                
                # 构建账号行
                acc_line = email
                if 'password' in account_info: 
                    acc_line += f"----{account_info['password']}"
                if 'backup' in account_info: 
                    acc_line += f"----{account_info['backup']}"
                if 'secret' in account_info: 
                    acc_line += f"----{account_info['secret']}"
                
                # ==================== 处理不同状态 ====================
                
                # 已订阅
                if status in [STATUS_SUBSCRIBED, STATUS_SUBSCRIBED_ANTIGRAVITY]:
                    AccountManager.move_to_subscribed(acc_line)
                    if status == STATUS_SUBSCRIBED_ANTIGRAVITY:
                        from core.database import DBManager
                        DBManager.update_account_status(email, STATUS_SUBSCRIBED_ANTIGRAVITY)
                    return True, f"已绑卡 ({status})"
                
                # 已验证未绑卡
                elif status == STATUS_VERIFIED:
                    AccountManager.move_to_verified(acc_line)
                    return True, "已过验证未绑卡 (Get Offer)"
                
                # 有资格待验证
                elif status == STATUS_LINK_READY:
                    if extra_data:
                        line = f"{extra_data}----{acc_line}"
                        AccountManager.save_link(line)
                        return True, f"提取成功 (Link Found): {extra_data[:50]}..."
                    else:
                        AccountManager.move_to_verified(acc_line)
                        return True, "有资格待验证 (Eligible)"
                
                # 无资格
                elif status == STATUS_INELIGIBLE:
                    AccountManager.move_to_ineligible(acc_line)
                    return False, "无资格 (Not Available)"
                
                # 错误或未知状态
                else:
                    AccountManager.move_to_error(acc_line)
                    try:
                        await page.screenshot(path=f"debug_{browser_id}.png")
                    except:
                        pass
                    return False, f"超时或错误 ({status})"
                
        except Exception as e:
            self.log(f"提取异常: {e}")
            import traceback
            traceback.print_exc()
            return False, f"错误: {str(e)}"
        finally:
            self.log(f"关闭浏览器: {browser_id}")
            bit_api['close'](browser_id)
    
    def extract_sheerlink_sync(
        self,
        browser_id: str,
        account_info: dict = None
    ) -> Tuple[bool, str]:
        """
        @brief 同步方式提取SheerLink
        @param browser_id 浏览器窗口ID
        @param account_info 账号信息（可选）
        @return (success, message)
        """
        return asyncio.run(self.extract_sheerlink_async(browser_id, account_info))
    
    def extract_batch(
        self,
        browser_ids: List[str],
        thread_count: int = 1,
        callback: Callable[[str, bool, str], None] = None,
        stop_check: Callable[[], bool] = None
    ) -> Dict[str, any]:
        """
        @brief 批量提取SheerLink
        @param browser_ids 浏览器ID列表
        @param thread_count 并发线程数
        @param callback 回调函数 callback(browser_id, success, message)
        @param stop_check 停止检查函数
        @return 统计结果字典
        """
        stats = {
            'link_unverified': 0,
            'link_verified': 0,
            'subscribed': 0,
            'ineligible': 0,
            'timeout': 0,
            'error': 0,
            'total': len(browser_ids),
            'processed': 0
        }
        
        self.log(f"开始批量提取，共 {len(browser_ids)} 个，并发: {thread_count}")
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {}
            
            for bid in browser_ids:
                if stop_check and stop_check():
                    break
                future = executor.submit(self.extract_sheerlink_sync, bid)
                futures[future] = bid
            
            for future in as_completed(futures):
                if stop_check and stop_check():
                    self.log("任务已停止")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                bid = futures[future]
                stats['processed'] += 1
                
                try:
                    success, msg = future.result()
                    
                    # 统计分类
                    if "Verified Link" in msg or "Get Offer" in msg:
                        stats['link_verified'] += 1
                    elif "Link Found" in msg or "提取成功" in msg:
                        stats['link_unverified'] += 1
                    elif "Subscribed" in msg or "已绑卡" in msg:
                        stats['subscribed'] += 1
                    elif "无资格" in msg or "not available" in msg.lower():
                        stats['ineligible'] += 1
                    elif "超时" in msg or "Timeout" in msg:
                        stats['timeout'] += 1
                    else:
                        stats['error'] += 1
                    
                    if callback:
                        callback(bid, success, msg)
                        
                except Exception as e:
                    stats['error'] += 1
                    if callback:
                        callback(bid, False, str(e))
        
        return stats


# ==================== 便捷函数 ====================

def process_browser(browser_id: str, log_callback: Callable = None) -> Tuple[bool, str]:
    """
    @brief 处理单个浏览器窗口（兼容旧接口）
    @param browser_id 浏览器窗口ID
    @param log_callback 日志回调
    @return (success, message)
    """
    service = SheerLinkService(log_callback)
    return service.extract_sheerlink_sync(browser_id)


def extract_sheerlink_batch(
    browser_ids: List[str],
    thread_count: int = 1,
    callback: Callable = None,
    stop_check: Callable = None,
    log_callback: Callable = None
) -> Dict[str, any]:
    """
    @brief 批量提取SheerLink
    @param browser_ids 浏览器ID列表
    @param thread_count 并发线程数
    @param callback 进度回调
    @param stop_check 停止检查
    @param log_callback 日志回调
    @return 统计结果
    """
    service = SheerLinkService(log_callback)
    return service.extract_batch(browser_ids, thread_count, callback, stop_check)
