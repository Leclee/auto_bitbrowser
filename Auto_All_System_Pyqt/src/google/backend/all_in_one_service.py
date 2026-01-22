"""
@file all_in_one_service.py
@brief 一键全自动处理服务模块
@details 完整流程: 登录检测 → 资格检测 → 验证SheerID → 绑卡订阅
         使用V2检测模块 (API拦截 + 智能等待)
"""
import asyncio
from typing import Tuple, Optional, Callable
from playwright.async_api import async_playwright, Page


def process_all_in_one(
    browser_id: str,
    api_key: str = '',
    card_info: dict = None,
    log_callback: Callable = None
) -> Tuple[bool, str, str]:
    """
    @brief 处理单个浏览器的全自动流程
    @param browser_id 浏览器ID
    @param api_key SheerID验证API Key（为空则从数据库获取）
    @param card_info 卡信息（为空则从数据库获取）
    @param log_callback 日志回调
    @return (success, final_status, message)
           final_status: 'subscribed_antigravity' | 'subscribed' | 'verified' | 'link_ready' | 'ineligible' | 'error'
    """
    def log(msg):
        print(msg)
        if log_callback:
            log_callback(msg)
    
    log("🚀 开始全自动处理流程 (V2)...")
    
    try:
        from core.bit_api import open_browser, close_browser, get_browser_info
        from core.database import DBManager
        from google.backend.google_detector import (
            check_google_login_by_avatar,
            check_google_one_status_v2,
        )
        from google.backend.sheerid_verifier import SheerIDVerifier
        from google.backend.bind_card_service import auto_bind_card, get_card_from_db
    except ImportError as e:
        return False, 'error', f"导入失败: {e}"
    
    # 从数据库获取API Key（如果未提供）
    if not api_key:
        api_key = DBManager.get_setting('sheerid_api_key', '')
        if api_key:
            log("🔑 已从数据库获取API Key")
    
    # 从数据库获取卡片（如果未提供）
    if card_info is None:
        card_info = get_card_from_db()
        if card_info:
            log(f"💳 已从数据库获取卡片: {card_info['number'][:4]}****")
    
    # 获取账号信息
    account_info = None
    try:
        browser_info = get_browser_info(browser_id)
        if browser_info:
            remark = browser_info.get('remark', '')
            if '----' in remark:
                parts = remark.split('----')
                if len(parts) >= 4:
                    account_info = {
                        'email': parts[0].strip(),
                        'password': parts[1].strip(),
                        'backup': parts[2].strip(),
                        'secret': parts[3].strip()
                    }
                    log(f"📧 账号: {account_info['email']}")
    except:
        pass
    
    # 打开浏览器
    log("🌐 打开浏览器...")
    result = open_browser(browser_id)
    if not result.get('success'):
        return False, 'error', f"打开浏览器失败"
    
    ws_endpoint = result['data']['ws']
    
    async def _run():
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()
                
                # Step 1: 检测登录状态 (V2)
                log("🔐 步骤1: 检测登录状态...")
                is_logged_in = await check_google_login_by_avatar(page, timeout=15)
                
                if not is_logged_in:
                    log("❌ 账号未登录")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], 'not_logged_in')
                    return False, 'not_logged_in', "未登录"
                
                log("✅ 已登录")
                
                # Step 2: 检测资格状态 (V2 - API拦截)
                log("🔍 步骤2: 检测资格状态 (API拦截)...")
                status, sheer_link = await check_google_one_status_v2(page, timeout=20)
                log(f"   当前状态: {status}")
                
                # 根据状态决定下一步
                if status == 'subscribed_antigravity':
                    log("🌟 账号已订阅且已解锁Antigravity")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], 'subscribed_antigravity')
                    return True, 'subscribed_antigravity', "已订阅+已解锁"
                
                if status == 'subscribed':
                    log("👑 账号已订阅")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], 'subscribed')
                    return True, 'subscribed', "已订阅"
                
                elif status == 'verified':
                    log("📋 账号已验证未绑卡，开始绑卡订阅...")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], 'verified')
                    
                    # 执行绑卡
                    success, msg = await auto_bind_card(page, card_info, account_info)
                    if success:
                        if account_info:
                            DBManager.update_account_status(account_info['email'], 'subscribed')
                        return True, 'subscribed', msg
                    else:
                        return False, 'verified', msg
                
                elif status == 'link_ready':
                    log("🔗 有资格待验证...")
                    
                    if account_info:
                        DBManager.update_account_status(account_info['email'], 'link_ready')
                        if sheer_link:
                            DBManager.update_sheerid_link(account_info['email'], sheer_link)
                    
                    if sheer_link and api_key:
                        # 从链接中提取verification ID
                        import re
                        vid_match = re.search(r'verificationId=([a-f0-9]+)', sheer_link)
                        if vid_match:
                            vid = vid_match.group(1)
                            log(f"   验证ID: {vid[:20]}...")
                            
                            # 验证SheerID
                            log("🔄 步骤3: 验证SheerID...")
                            verifier = SheerIDVerifier(api_key)
                            results = verifier.verify_batch([vid])
                            
                            result = results.get(vid, {})
                            if result.get('currentStep') == 'success' or result.get('status') == 'success':
                                log("✅ SheerID验证成功")
                                
                                # 重新检测状态
                                await page.reload(wait_until='domcontentloaded')
                                await page.wait_for_load_state('networkidle', timeout=10000)
                                
                                new_status, _ = await check_google_one_status_v2(page, timeout=15)
                                if new_status == 'verified':
                                    log("📋 验证成功，开始绑卡订阅...")
                                    if account_info:
                                        DBManager.update_account_status(account_info['email'], 'verified')
                                    
                                    success, msg = await auto_bind_card(page, card_info, account_info)
                                    if success:
                                        if account_info:
                                            DBManager.update_account_status(account_info['email'], 'subscribed')
                                        return True, 'subscribed', msg
                                    else:
                                        return True, 'verified', f"验证成功但绑卡失败: {msg}"
                                else:
                                    return True, new_status, f"验证成功，当前状态: {new_status}"
                            else:
                                log(f"❌ SheerID验证失败: {result.get('message', 'unknown')}")
                                return False, 'link_ready', f"验证失败: {result.get('message', 'unknown')}"
                        else:
                            log("⚠️ 无法提取验证ID")
                            return True, 'link_ready', f"已提取链接但无法验证"
                    else:
                        return True, 'link_ready', f"已提取SheerLink (未提供API Key)"
                
                elif status == 'ineligible':
                    log("❌ 账号无资格")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], 'ineligible')
                    return False, 'ineligible', "无资格"
                
                else:
                    return False, 'error', f"未知状态: {status}"
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                return False, 'error', str(e)
    
    return asyncio.run(_run())

