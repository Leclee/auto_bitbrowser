import asyncio
import time
import pyotp
import re
import os
import sys
import threading
from playwright.async_api import async_playwright, Playwright
from bit_api import openBrowser, closeBrowser
from bit_playwright import google_login
from create_window import get_browser_list, get_browser_info
from deep_translator import GoogleTranslator
from account_manager import AccountManager

# Global lock for file writing safety
file_write_lock = threading.Lock()

# Phrases indicating the offer is not available in various languages
NOT_AVAILABLE_PHRASES = [
    "This offer is not available",
    "Ưu đãi này hiện không dùng được",
    "Esta oferta no está disponible",
    "Cette offre n'est pas disponible",
    "Esta oferta não está disponível",
    "Tawaran ini tidak tersedia",
    "此优惠目前不可用",
    "這項優惠目前無法使用",
    "Oferta niedostępna",
    "Oferta nu este disponibilă",
    "Die Aktion ist nicht verfügbar",
    "Il'offerta non è disponibile",
    "Această ofertă nu este disponibilă",
    "Ez az ajánlat nem áll rendelkezésre",
    "Tato nabídka není k dispozici",
    "Bu teklif kullanılamıyor"
]

# Phrases indicating the account is already subscribed/verified
SUBSCRIBED_PHRASES = [
    "You're already subscribed",
    "Bạn đã đăng ký",
    "已订阅", 
    "Ya estás suscrito"
]

# Phrases indicating verified but not bound ("Get student offer")
VERIFIED_UNBOUND_PHRASES = [
    "Get student offer",
    "Nhận ưu đãi dành cho sinh viên",
    "Obtener oferta para estudiantes",
    "Obter oferta de estudante",
    "获取学生优惠",
    "獲取學生優惠",
    "Dapatkan penawaran pelajar",
]

def get_base_path():
    """获取数据目录路径"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # 开发时，数据文件在 data/ 目录
    src_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(src_dir), 'data')

# Helper function for automation logic
async def _automate_login_and_extract(playwright: Playwright, browser_id: str, account_info: dict, ws_endpoint: str, log_callback=None):
    chromium = playwright.chromium
    try:
        browser = await chromium.connect_over_cdp(ws_endpoint)
        default_context = browser.contexts[0]
        page = default_context.pages[0] if default_context.pages else await default_context.new_page()

        print("Proxy warmup: Waiting for 2 seconds...")
        if log_callback: log_callback("正在打开浏览器预热...")
        await asyncio.sleep(2)

        print('Navigating to accounts.google.com...')
        # Retry logic for poor network
        max_retries = 3
        
        # 1. 自动登录流程 (使用统一封装的函数)
        print("Starting unified Google login process...")
        if log_callback: log_callback("正在执行自动登录...")
        
        await google_login(page, account_info)

        # Wait briefly after login attempt
        await asyncio.sleep(3)

        # 4. Navigate to Google One AI page
        target_url = "https://one.google.com/ai-student?g1_landing_page=75&utm_source=antigravity&utm_campaign=argon_limit_reached"
        
        print("Opening a new page for target URL...")
        # Open new page first to ensure browser doesn't close
        new_page = await default_context.new_page()
        page = new_page # Switch to new page
        
        print(f"Navigating to {target_url}...")
        
        nav_success = False
        for attempt in range(max_retries):
            try:
                await page.goto(target_url, timeout=60000)
                print("Target navigation successful.")
                nav_success = True
                break
            except Exception as e:
                print(f"Target navigation failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("Retrying in 5 seconds...")
                    await asyncio.sleep(5)
        
        if not nav_success:
            print("Failed to navigate to target URL after retries.")
            return False

        # 5. Extract "Verify eligibility" link or check for non-eligibility
        print("Checking for eligibility...")
        if log_callback: log_callback("正在检测学生资格...")
        
        found_link = False
        is_invalid = False
        
        # 使用统一的状态检测函数
        status, extra_data = await check_google_one_status(page, timeout=10)
        
        if status == "subscribed":
            acc_line = account_info.get('email', '')
            if 'password' in account_info: acc_line += f"----{account_info['password']}"
            if 'backup' in account_info: acc_line += f"----{account_info['backup']}"
            if 'secret' in account_info: acc_line += f"----{account_info['secret']}"
            AccountManager.move_to_subscribed(acc_line)
            return True, "已绑卡 (Subscribed)"
        
        elif status == "verified":
            acc_line = account_info.get('email', '')
            if 'password' in account_info: acc_line += f"----{account_info['password']}"
            if 'backup' in account_info: acc_line += f"----{account_info['backup']}"
            if 'secret' in account_info: acc_line += f"----{account_info['secret']}"
            AccountManager.move_to_verified(acc_line)
            return True, "已过验证未绑卡 (Get Offer)"
        
        elif status == "link_ready":
            acc_line = account_info.get('email', '')
            if 'password' in account_info: acc_line += f"----{account_info['password']}"
            if 'backup' in account_info: acc_line += f"----{account_info['backup']}"
            if 'secret' in account_info: acc_line += f"----{account_info['secret']}"
            if extra_data:
                line = f"{extra_data}----{acc_line}"
                AccountManager.save_link(line)
                return True, "提取成功 (Link Found)"
            else:
                AccountManager.move_to_verified(acc_line)
                return True, "有资格待验证 (Eligible)"
        
        elif status == "ineligible":
            acc_line = account_info.get('email', '')
            if 'password' in account_info: acc_line += f"----{account_info['password']}"
            if 'backup' in account_info: acc_line += f"----{account_info['backup']}"
            if 'secret' in account_info: acc_line += f"----{account_info['secret']}"
            AccountManager.move_to_ineligible(acc_line)
            return False, "无资格 (Not Available)"
        
        else:  # timeout or error
            acc_line = account_info.get('email', '')
            if 'password' in account_info: acc_line += f"----{account_info['password']}"
            if 'backup' in account_info: acc_line += f"----{account_info['backup']}"
            if 'secret' in account_info: acc_line += f"----{account_info['secret']}"
            AccountManager.move_to_error(acc_line)
            await page.screenshot(path="debug_eligibility_timeout.png")
            return False, f"超时或错误 ({status})"
            
    except Exception as e:
        print(f"An error occurred in automation: {e}")
        import traceback
        traceback.print_exc()
        return False, f"错误: {str(e)}"


async def check_google_one_status(page, timeout=10):
    """
    统一的 Google One AI 页面状态检测函数
    被 auto_all_in_one_gui.py 调用
    返回: (status, extra_data)
      status: 'subscribed', 'verified', 'link_ready', 'ineligible', 'error', 'timeout'
      extra_data: 链接或其他信息
    """
    import time
    from deep_translator import GoogleTranslator
    
    start_time = time.time()
    print(f"Checking for eligibility (max {timeout}s)...")
    
    while time.time() - start_time < timeout:
        try:
            # 0. Precise CSS Class Check
            # Eligible (link_ready)
            css_eligible = False
            if await page.locator('.krEaxf.ZLZvHe.rv8wkf.b3UMcc').count() > 0:
                css_eligible = True
            
            # Ineligible
            if await page.locator('.krEaxf.tTa5V.rv8wkf.b3UMcc').count() > 0:
                return "ineligible", None

            # 1. Check for "Already Subscribed"
            for phrase in SUBSCRIBED_PHRASES:
                if await page.locator(f'text="{phrase}"').is_visible():
                    return "subscribed", None
            
            # 1.5 Check for "Verified Unbound" (Get Offer)
            for phrase in VERIFIED_UNBOUND_PHRASES:
                element = page.locator(f'text="{phrase}"')
                if await element.is_visible():
                    # 尝试提取链接
                    return "verified", None # 可以进一步提取链接，这里先返回状态
            
            # 2. Check for "Not Available"
            for phrase in NOT_AVAILABLE_PHRASES:
                if await page.locator(f'text="{phrase}"').is_visible():
                    return "ineligible", None
            
            # 3. Check for SheerID Link (link_ready)
            link_element = page.locator('a[href*="sheerid.com"]').first
            if await link_element.count() > 0:
                # 进一步检查内容翻译
                try:
                    text_content = await link_element.inner_text()
                    if text_content:
                        translated_text = GoogleTranslator(source='auto', target='en').translate(text_content).lower()
                        if "student offer" in translated_text or "get offer" in translated_text:
                            return "verified", None
                except: pass
                
                return "link_ready", await link_element.get_attribute("href")
            
            # 3.1 Check for "Verify eligibility" buttons (without link yet)
            if await page.locator('text="Verify eligibility"').count() > 0 or \
               await page.locator('text="verify your eligibility"').count() > 0:
                return "link_ready", None

            # 如果没有链接但 CSS 说有资格，则也是 link_ready
            if css_eligible:
                 # 此时可能需要点击按钮才能出链接，仍归为 link_ready
                 return "link_ready", None

            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Check status check error: {e}")
            await asyncio.sleep(1)

    return "timeout", None


# 删除了旧的孤立代码块，现在使用上面的 check_google_one_status 函数
# 原代码块从 "try: start_time = time.time()" 到 "return False" 被移除


async def _async_process_wrapper(browser_id, account_info, ws_endpoint, log_callback=None):
    """异步处理包装器"""
    async with async_playwright() as playwright:
        return await _automate_login_and_extract(playwright, browser_id, account_info, ws_endpoint, log_callback)


def process_browser(browser_id, log_callback=None):
    """
    Synchronous entry point for processing a single browser.
    Returns (success, message)
    """
    print(f"Fetching info for browser ID: {browser_id}")
    
    target_browser = get_browser_info(browser_id)
    if not target_browser:
        # Fallback search
        print(f"Direct info fetch failed for {browser_id}, attempting list search...")
        browsers = get_browser_list(page=0, pageSize=1000)
        for b in browsers:
             if b.get('id') == browser_id:
                 target_browser = b
                 break
    
    if not target_browser:
        return False, f"Browser {browser_id} not found."

    account_info = {}
    
    # 1. 优先尝试从数据库获取完整信息
    try:
        from database import DBManager
        conn = DBManager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email, password, recovery_email, secret_key FROM accounts WHERE browser_id = ?", (browser_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row[1]: # 确保有密码
            print(f"✅ 从数据库获取到账号信息: {row[0]}")
            account_info = {
                'email': row[0],
                'password': row[1],
                'backup': row[2],
                'secret': row[3],
                '2fa_secret': row[3],
                'backup_email': row[2]
            }
            # 调试日志：确认密钥是否读取成功
            secret_len = len(row[3]) if row[3] else 0
            print(f"✅ 账号数据详情: Email={row[0]}, SecretLength={secret_len}")
    except Exception as e:
        print(f"⚠️ 从数据库读取失败: {e}")

    # 2. 如果数据库没有或没读到，降级使用备注(remark)
    if not account_info or not account_info.get('password'):
        remark = target_browser.get('remark', '')
        parts = remark.split('----')
        if len(parts) >= 4:
            print("⚠️ 数据库无完整信息，使用浏览器备注信息")
            account_info = {
                'email': parts[0].strip(),
                'password': parts[1].strip(),
                'backup': parts[2].strip(),
                'secret': parts[3].strip(),
                '2fa_secret': parts[3].strip(),
                'backup_email': parts[2].strip()
            }
        else:
            if len(parts) >= 1:
                 account_info['email'] = parts[0].strip()
            else:
                 account_info['email'] = 'unknown'
            print("⚠️ 数据库和备注均未提供完整密码信息，登录可能失败。")

    print(f"Opening browser {browser_id}...")
    res = openBrowser(browser_id)
    if not res or not res.get('success', False):
        return False, f"Failed to open browser: {res}"

    ws_endpoint = res.get('data', {}).get('ws')
    if not ws_endpoint:
        closeBrowser(browser_id)
        return False, "No WebSocket endpoint returned."

    try:
        # Run automation
        result = asyncio.run(_async_process_wrapper(browser_id, account_info, ws_endpoint, log_callback))
        
        # Handle tuple return or boolean for backward compatibility
        if isinstance(result, tuple):
            success, msg = result
            return success, msg
        else:
            if result:
                return True, "Successfully extracted and saved link."
            else:
                return False, "Automation finished but link not found or error occurred."
    finally:
        print(f"Closing browser {browser_id}...")
        closeBrowser(browser_id)

if __name__ == "__main__":
    # Test with specific ID
    target_id = "62b1596a5e064629a7126b11feed7c89"
    success, msg = process_browser(target_id)
    print(f"Result: {success} - {msg}")
