"""
@file all_in_one_service.py
@brief 一键全自动处理服务模块 (V4 - 完整版)
@details 完整流程: 登录检测 → 资格检测 → 验证SheerID → 绑卡订阅
         包含详细步骤追踪、错误重试机制、状态回调
"""
import asyncio
import re
import time
from typing import Tuple, Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from playwright.async_api import async_playwright, Page


# ==================== 步骤定义 ====================

class ProcessStep(Enum):
    """处理步骤枚举"""
    INIT = "init"                      # 初始化
    OPEN_BROWSER = "open_browser"      # 打开浏览器
    NAVIGATE = "navigate"              # 导航页面
    CHECK_LOGIN = "check_login"        # 检测登录
    DO_LOGIN = "do_login"              # 执行登录
    HANDLE_2FA = "handle_2fa"          # 处理2FA
    HANDLE_BACKUP = "handle_backup"    # 辅助邮箱
    CHECK_ELIGIBILITY = "check_eligibility"  # 检测资格
    EXTRACT_LINK = "extract_link"      # 提取链接
    VERIFY_SHEERID = "verify_sheerid"  # SheerID验证
    BIND_CARD = "bind_card"            # 绑定卡片
    SUBSCRIBE = "subscribe"            # 订阅服务
    COMPLETE = "complete"              # 完成
    ERROR = "error"                    # 错误


STEP_DISPLAY = {
    ProcessStep.INIT: "🚀 初始化",
    ProcessStep.OPEN_BROWSER: "🌐 打开浏览器",
    ProcessStep.NAVIGATE: "📍 导航页面",
    ProcessStep.CHECK_LOGIN: "🔍 检测登录",
    ProcessStep.DO_LOGIN: "🔐 执行登录",
    ProcessStep.HANDLE_2FA: "🔑 2FA验证",
    ProcessStep.HANDLE_BACKUP: "📧 辅助邮箱",
    ProcessStep.CHECK_ELIGIBILITY: "📋 检测资格",
    ProcessStep.EXTRACT_LINK: "🔗 提取链接",
    ProcessStep.VERIFY_SHEERID: "✅ SheerID验证",
    ProcessStep.BIND_CARD: "💳 绑定卡片",
    ProcessStep.SUBSCRIBE: "👑 订阅服务",
    ProcessStep.COMPLETE: "🎉 完成",
    ProcessStep.ERROR: "❌ 错误",
}


# ==================== 重试配置 ====================

RETRY_CONFIG = {
    ProcessStep.OPEN_BROWSER: {"max_retries": 3, "delay": 2},
    ProcessStep.NAVIGATE: {"max_retries": 2, "delay": 2},
    ProcessStep.CHECK_LOGIN: {"max_retries": 2, "delay": 1},
    ProcessStep.DO_LOGIN: {"max_retries": 3, "delay": 1},
    ProcessStep.HANDLE_2FA: {"max_retries": 5, "delay": 30},
    ProcessStep.HANDLE_BACKUP: {"max_retries": 3, "delay": 1},
    ProcessStep.CHECK_ELIGIBILITY: {"max_retries": 2, "delay": 3},
    ProcessStep.EXTRACT_LINK: {"max_retries": 2, "delay": 1},
    ProcessStep.VERIFY_SHEERID: {"max_retries": 2, "delay": 5},
    ProcessStep.BIND_CARD: {"max_retries": 3, "delay": 2},
    ProcessStep.SUBSCRIBE: {"max_retries": 2, "delay": 3},
}


# ==================== 处理状态 ====================

@dataclass
class ProcessState:
    """处理状态数据类"""
    browser_id: str = ""
    email: str = ""
    current_step: ProcessStep = ProcessStep.INIT
    step_history: List[Dict] = field(default_factory=list)
    retry_counts: Dict[str, int] = field(default_factory=dict)
    final_status: str = ""
    sheer_link: str = ""
    error_message: str = ""
    start_time: float = 0
    end_time: float = 0
    
    def add_step(self, step: ProcessStep, status: str, message: str = ""):
        """记录步骤"""
        self.step_history.append({
            "step": step.value,
            "step_display": STEP_DISPLAY.get(step, step.value),
            "status": status,
            "message": message,
            "time": time.time()
        })
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "browser_id": self.browser_id,
            "email": self.email,
            "current_step": self.current_step.value,
            "current_step_display": STEP_DISPLAY.get(self.current_step, ""),
            "step_history": self.step_history,
            "final_status": self.final_status,
            "sheer_link": self.sheer_link,
            "error_message": self.error_message,
            "duration": self.end_time - self.start_time if self.end_time else time.time() - self.start_time,
        }


# ==================== 回调类型 ====================

StepCallback = Callable[[ProcessStep, str, str], None]  # (step, status, message)
LogCallback = Callable[[str], None]  # (message)
ProgressCallback = Callable[[ProcessState], None]  # (state)


# ==================== 核心处理函数 ====================

def process_all_in_one(
    browser_id: str,
    api_key: str = '',
    card_info: dict = None,
    log_callback: LogCallback = None,
    step_callback: StepCallback = None,
    progress_callback: ProgressCallback = None,
) -> Tuple[bool, str, str, ProcessState]:
    """
    @brief 处理单个浏览器的全自动流程 (V4 - 完整版)
    @param browser_id 浏览器ID
    @param api_key SheerID验证API Key（为空则从数据库获取）
    @param card_info 卡信息（为空则从数据库获取）
    @param log_callback 日志回调
    @param step_callback 步骤回调 (step, status, message)
    @param progress_callback 进度回调 (state)
    @return (success, final_status, message, state)
    """
    state = ProcessState(browser_id=browser_id, start_time=time.time())
    
    def log(msg: str):
        print(msg)
        if log_callback:
            log_callback(msg)
    
    def update_step(step: ProcessStep, status: str, message: str = ""):
        state.current_step = step
        state.add_step(step, status, message)
        log(f"{STEP_DISPLAY.get(step, step.value)} - {status}: {message}")
        if step_callback:
            step_callback(step, status, message)
        if progress_callback:
            progress_callback(state)
    
    def can_retry(step: ProcessStep) -> bool:
        """检查是否可以重试"""
        config = RETRY_CONFIG.get(step, {"max_retries": 1})
        current = state.retry_counts.get(step.value, 0)
        return current < config["max_retries"]
    
    def increment_retry(step: ProcessStep) -> int:
        """增加重试计数"""
        current = state.retry_counts.get(step.value, 0)
        state.retry_counts[step.value] = current + 1
        return current + 1
    
    def get_retry_delay(step: ProcessStep) -> float:
        """获取重试延迟"""
        config = RETRY_CONFIG.get(step, {"delay": 1})
        return config["delay"]
    
    # ==================== 初始化阶段 ====================
    update_step(ProcessStep.INIT, "running", "开始初始化...")
    
    try:
        from core.bit_api import open_browser, close_browser, get_browser_info
        from core.database import DBManager
        from google.backend.google_auth import (
            check_google_one_status,
            google_login,
            detect_eligibility_status,
            STATUS_NOT_LOGGED_IN,
            STATUS_SUBSCRIBED_ANTIGRAVITY,
            STATUS_SUBSCRIBED,
            STATUS_VERIFIED,
            STATUS_LINK_READY,
            STATUS_INELIGIBLE,
            STATUS_ERROR,
        )
        from google.backend.sheerid_verifier import SheerIDVerifier
        from google.backend.bind_card_service import auto_bind_card, get_card_from_db
    except ImportError as e:
        update_step(ProcessStep.INIT, "error", f"导入失败: {e}")
        state.final_status = 'error'
        state.error_message = str(e)
        state.end_time = time.time()
        return False, 'error', f"导入失败: {e}", state
    
    # 获取API Key
    if not api_key:
        api_key = DBManager.get_setting('sheerid_api_key', '')
        if api_key:
            log("🔑 已从数据库获取API Key")
    
    # 获取卡片信息
    if card_info is None:
        card_info = get_card_from_db()
        if card_info:
            log(f"💳 已从数据库获取卡片: {card_info['number'][:4]}****")
    
    # 获取账号信息（复用 sheerlink_service 的逻辑：优先数据库，降级浏览器备注）
    account_info = None
    
    # 1. 优先从数据库获取账号信息
    try:
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
            state.email = account_info['email']
            log(f"📧 账号: {account_info['email']} (从数据库获取)")
    except Exception as e:
        log(f"⚠️ 从数据库读取账号失败: {e}")
    
    # 2. 降级从浏览器备注获取
    if not account_info or not account_info.get('password'):
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
                            'backup_email': parts[2].strip(),
                            'secret': parts[3].strip(),
                            '2fa_secret': parts[3].strip()
                        }
                        state.email = account_info['email']
                        log(f"📧 账号: {account_info['email']} (从浏览器备注获取)")
            else:
                log(f"⚠️ 未找到浏览器 {browser_id} 的信息，可能该窗口在比特浏览器中不存在")
        except Exception as e:
            log(f"⚠️ 获取浏览器信息失败: {e}")
    
    if not account_info or not account_info.get('password'):
        log(f"⚠️ 无法获取账号密码信息，将跳过自动登录")
    
    update_step(ProcessStep.INIT, "success", "初始化完成")
    
    # ==================== 打开浏览器 ====================
    ws_endpoint = None
    max_open_retries = RETRY_CONFIG[ProcessStep.OPEN_BROWSER]["max_retries"]
    open_delay = RETRY_CONFIG[ProcessStep.OPEN_BROWSER]["delay"]
    
    for open_attempt in range(max_open_retries):
        update_step(ProcessStep.OPEN_BROWSER, "running", f"尝试打开浏览器 (第{open_attempt + 1}/{max_open_retries}次)")
        
        try:
            result = open_browser(browser_id)
            
            if result.get('success'):
                # 检查 data 是否存在且包含 ws
                data = result.get('data')
                if data and isinstance(data, dict) and data.get('ws'):
                    ws_endpoint = data['ws']
                    update_step(ProcessStep.OPEN_BROWSER, "success", "浏览器已打开")
                    break
                else:
                    raise Exception(f"API返回成功但数据无效: {data}")
            else:
                raise Exception(result.get('msg', '未知错误'))
        except Exception as e:
            state.retry_counts[ProcessStep.OPEN_BROWSER.value] = open_attempt + 1
            
            if open_attempt < max_open_retries - 1:
                update_step(ProcessStep.OPEN_BROWSER, "retry", f"失败: {e}, {open_delay}秒后重试...")
                time.sleep(open_delay)
            else:
                update_step(ProcessStep.OPEN_BROWSER, "error", f"打开浏览器失败: {e}")
                state.final_status = 'error'
                state.error_message = str(e)
                state.end_time = time.time()
                return False, 'error', f"打开浏览器失败: {e}", state
    
    if not ws_endpoint:
        update_step(ProcessStep.OPEN_BROWSER, "error", "无法获取浏览器连接")
        state.final_status = 'error'
        state.error_message = "无法获取浏览器连接"
        state.end_time = time.time()
        return False, 'error', "无法获取浏览器连接", state
    
    # ==================== 异步处理主流程 ====================
    async def _run_async():
        nonlocal state
        
        async with async_playwright() as playwright:
            browser = None
            try:
                browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()
                
                # ========== Step 1: 智能登录（复用 sheerlink_service 逻辑） ==========
                # 不要先导航到资格页面！让 google_login 自己处理
                # check_google_one_status 会自己导航到资格页面
                update_step(ProcessStep.CHECK_LOGIN, "running", "智能登录检测...")
                
                current_url = page.url
                log(f"当前页面: {current_url[:60]}...")
                
                if account_info and account_info.get('password'):
                    # 执行智能登录（google_login 内部会检测是否需要登录）
                    max_login_retries = RETRY_CONFIG[ProcessStep.DO_LOGIN]["max_retries"]
                    login_delay = RETRY_CONFIG[ProcessStep.DO_LOGIN]["delay"]
                    login_success_flag = False
                    
                    for login_attempt in range(max_login_retries):
                        update_step(ProcessStep.DO_LOGIN, "running", f"智能登录 (第{login_attempt + 1}/{max_login_retries}次)")
                        
                        try:
                            login_success, login_msg = await google_login(page, account_info)
                            
                            if login_success:
                                update_step(ProcessStep.DO_LOGIN, "success", login_msg)
                                login_success_flag = True
                                break
                            else:
                                # 额外检查：如果在Google服务页面，可能实际已登录
                                final_url = page.url
                                logged_in_indicators = ['myaccount.google.com', 'mail.google.com', 
                                                         'drive.google.com', 'one.google.com']
                                for indicator in logged_in_indicators:
                                    if indicator in final_url:
                                        log(f"⚠️ 登录函数返回失败，但URL显示已登录: {indicator}")
                                        login_success_flag = True
                                        login_msg = "已登录 (URL检测)"
                                        update_step(ProcessStep.DO_LOGIN, "success", login_msg)
                                        break
                                
                                if login_success_flag:
                                    break
                                    
                                raise Exception(login_msg)
                                
                        except Exception as e:
                            state.retry_counts[ProcessStep.DO_LOGIN.value] = login_attempt + 1
                            
                            if login_attempt < max_login_retries - 1:
                                update_step(ProcessStep.DO_LOGIN, "retry", f"登录失败: {e}，{login_delay}秒后重试...")
                                await asyncio.sleep(login_delay)
                            else:
                                update_step(ProcessStep.DO_LOGIN, "error", f"登录失败: {e}")
                                if account_info:
                                    DBManager.update_account_status(account_info['email'], STATUS_NOT_LOGGED_IN)
                                return False, STATUS_NOT_LOGGED_IN, f"登录失败: {e}"
                    
                    if not login_success_flag:
                        return False, STATUS_NOT_LOGGED_IN, "登录重试次数用尽"
                    
                    log(f"✅ 登录成功: {login_msg}")
                    await asyncio.sleep(1)  # 等待登录状态稳定
                else:
                    log("⚠️ 无账号密码信息，跳过登录直接检测资格...")
                
                # ========== Step 2: 检测资格状态 ==========
                # check_google_one_status 会自动导航到资格页面
                update_step(ProcessStep.CHECK_ELIGIBILITY, "running", "检测资格状态...")
                log("执行资格检测（自动导航到资格页面）...")
                status, sheer_link = await check_google_one_status(page, timeout=30.0)
                log(f"   检测结果: {status}")
                
                # 检查是否真的未登录
                if status == STATUS_NOT_LOGGED_IN:
                    update_step(ProcessStep.CHECK_LOGIN, "error", "检测仍显示未登录")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], STATUS_NOT_LOGGED_IN)
                    return False, STATUS_NOT_LOGGED_IN, "登录后仍显示未登录状态"
                
                update_step(ProcessStep.CHECK_LOGIN, "success", f"已登录，状态: {status}")
                
                # ========== 根据状态执行后续操作 ==========
                update_step(ProcessStep.CHECK_ELIGIBILITY, "running", f"当前状态: {status}")
                
                # 已订阅 + 已解锁
                if status == STATUS_SUBSCRIBED_ANTIGRAVITY:
                    update_step(ProcessStep.CHECK_ELIGIBILITY, "success", "已订阅且已解锁Antigravity")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], STATUS_SUBSCRIBED_ANTIGRAVITY)
                    update_step(ProcessStep.COMPLETE, "success", "🌟 流程完成")
                    return True, STATUS_SUBSCRIBED_ANTIGRAVITY, "已订阅+已解锁"
                
                # 已订阅
                if status == STATUS_SUBSCRIBED:
                    update_step(ProcessStep.CHECK_ELIGIBILITY, "success", "已订阅")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], STATUS_SUBSCRIBED)
                    update_step(ProcessStep.COMPLETE, "success", "👑 流程完成")
                    return True, STATUS_SUBSCRIBED, "已订阅"
                
                # 无资格
                if status == STATUS_INELIGIBLE:
                    update_step(ProcessStep.CHECK_ELIGIBILITY, "warning", "账号无资格")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], STATUS_INELIGIBLE)
                    update_step(ProcessStep.COMPLETE, "warning", "❌ 无资格")
                    return False, STATUS_INELIGIBLE, "无资格"
                
                # 已验证未绑卡 → 直接绑卡
                if status == STATUS_VERIFIED:
                    update_step(ProcessStep.CHECK_ELIGIBILITY, "success", "已验证，准备绑卡")
                    if account_info:
                        DBManager.update_account_status(account_info['email'], STATUS_VERIFIED)
                    
                    # 执行绑卡
                    bind_success, bind_msg = await _do_bind_card(
                        page, card_info, account_info, state, update_step, log
                    )
                    
                    if bind_success:
                        # 检测是否解锁了 Antigravity
                        final_status = STATUS_SUBSCRIBED
                        if "Antigravity" in bind_msg:
                            final_status = STATUS_SUBSCRIBED_ANTIGRAVITY
                        
                        if account_info:
                            DBManager.update_account_status(account_info['email'], final_status)
                        return True, final_status, bind_msg
                    else:
                        update_step(ProcessStep.BIND_CARD, "error", f"绑卡失败: {bind_msg}")
                        return False, STATUS_VERIFIED, f"绑卡失败: {bind_msg}"
                
                # 有资格待验证 → 验证SheerID → 绑卡
                if status == STATUS_LINK_READY:
                    update_step(ProcessStep.CHECK_ELIGIBILITY, "success", "有资格，待验证")
                    state.sheer_link = sheer_link or ""
                    
                    if account_info:
                        DBManager.update_account_status(account_info['email'], STATUS_LINK_READY)
                        if sheer_link:
                            DBManager.update_sheerid_link(account_info['email'], sheer_link)
                    
                    # ========== SheerID验证 (带刷新重试) ==========
                    if not api_key:
                        update_step(ProcessStep.VERIFY_SHEERID, "warning", "无API Key，跳过验证")
                        return True, STATUS_LINK_READY, "已提取链接 (无API Key)"
                    
                    verify_success = False
                    max_link_retries = 3  # 最多刷新获取3次新链接
                    last_verify_error = ""
                    current_sheer_link = sheer_link
                    
                    for link_attempt in range(max_link_retries):
                        # ========== 提取验证链接 ==========
                        update_step(ProcessStep.EXTRACT_LINK, "running", f"提取验证ID (第{link_attempt + 1}/{max_link_retries}次)...")
                        
                        if not current_sheer_link:
                            update_step(ProcessStep.EXTRACT_LINK, "error", "无法获取验证链接")
                            last_verify_error = "无法获取验证链接"
                            break
                        
                        vid_match = re.search(r'verificationId=([a-fA-F0-9]+)', current_sheer_link)
                        if not vid_match:
                            update_step(ProcessStep.EXTRACT_LINK, "error", "无法提取验证ID")
                            last_verify_error = "链接格式错误"
                            break
                        
                        vid = vid_match.group(1)
                        update_step(ProcessStep.EXTRACT_LINK, "success", f"验证ID: {vid[:20]}...")
                        
                        # ========== 调用 API 验证 ==========
                        update_step(ProcessStep.VERIFY_SHEERID, "running", f"验证中...")
                        
                        try:
                            verifier = SheerIDVerifier(api_key)
                            results = verifier.verify_batch([vid])
                            
                            result = results.get(vid, {})
                            if result.get('currentStep') == 'success' or result.get('status') == 'success':
                                update_step(ProcessStep.VERIFY_SHEERID, "success", "SheerID验证成功")
                                verify_success = True
                                break
                            else:
                                last_verify_error = result.get('message', 'unknown')
                                raise Exception(last_verify_error)
                                
                        except Exception as e:
                            last_verify_error = str(e)
                            state.retry_counts[ProcessStep.VERIFY_SHEERID.value] = link_attempt + 1
                            
                            # 验证失败，先取消当前验证
                            try:
                                log(f"🚫 验证失败，取消当前验证: {vid[:20]}...")
                                cancel_result = verifier.cancel_verification(vid)
                                log(f"   取消结果: {cancel_result.get('status', 'unknown')}")
                            except Exception as cancel_err:
                                log(f"   取消验证异常: {cancel_err}")
                            
                            # 刷新页面获取新链接重试
                            if link_attempt < max_link_retries - 1:
                                update_step(ProcessStep.VERIFY_SHEERID, "retry", f"验证失败: {str(e)[:50]}，刷新获取新链接...")
                                log(f"🔄 刷新页面获取新的 SheerID 链接 (第{link_attempt + 2}次)...")
                                
                                await page.reload(wait_until='domcontentloaded')
                                await asyncio.sleep(3)
                                
                                # 重新检测状态和链接
                                new_status, new_link = await detect_eligibility_status(page, timeout=15)
                                log(f"   刷新后状态: {new_status}")
                                
                                if new_status == STATUS_LINK_READY and new_link:
                                    current_sheer_link = new_link
                                    log(f"   获取到新链接: {new_link[:60]}...")
                                    
                                    # 更新数据库中的链接
                                    if account_info:
                                        DBManager.update_sheerid_link(account_info['email'], new_link)
                                    
                                    await asyncio.sleep(2)
                                    continue
                                elif new_status == STATUS_VERIFIED:
                                    # 刷新后已验证，可能之前验证成功了
                                    log(f"   刷新后已是已验证状态")
                                    verify_success = True
                                    break
                                else:
                                    log(f"   刷新后无法获取新链接，状态: {new_status}")
                                    last_verify_error = f"刷新后状态异常: {new_status}"
                                    break
                            else:
                                update_step(ProcessStep.VERIFY_SHEERID, "error", f"验证失败: {e}")
                                break
                    
                    if not verify_success:
                        return False, STATUS_LINK_READY, f"验证失败: {last_verify_error}"
                    
                    # ========== 刷新页面重新检测 ==========
                    log("🔄 刷新页面检测新状态...")
                    await page.reload(wait_until='domcontentloaded')
                    await asyncio.sleep(3)
                    
                    new_status, _ = await detect_eligibility_status(page, timeout=15)
                    log(f"   新状态: {new_status}")
                    
                    if new_status == STATUS_VERIFIED:
                        if account_info:
                            DBManager.update_account_status(account_info['email'], STATUS_VERIFIED)
                        
                        # 执行绑卡
                        bind_success, bind_msg = await _do_bind_card(
                            page, card_info, account_info, state, update_step, log
                        )
                        
                        if bind_success:
                            # 检测是否解锁了 Antigravity
                            final_status = STATUS_SUBSCRIBED
                            if "Antigravity" in bind_msg:
                                final_status = STATUS_SUBSCRIBED_ANTIGRAVITY
                            
                            if account_info:
                                DBManager.update_account_status(account_info['email'], final_status)
                            return True, final_status, bind_msg
                        else:
                            update_step(ProcessStep.BIND_CARD, "error", f"绑卡失败: {bind_msg}")
                            return False, STATUS_VERIFIED, f"验证成功但绑卡失败: {bind_msg}"
                    else:
                        if account_info:
                            DBManager.update_account_status(account_info['email'], new_status)
                        # 验证后状态不是 VERIFIED，可能失败了
                        if new_status in [STATUS_INELIGIBLE, STATUS_ERROR]:
                            return False, new_status, f"验证后状态异常: {new_status}"
                        return True, new_status, f"验证后状态: {new_status}"
                
                # 其他未知状态
                update_step(ProcessStep.CHECK_ELIGIBILITY, "error", f"未知状态: {status}")
                return False, STATUS_ERROR, f"未知状态: {status}"
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                update_step(ProcessStep.ERROR, "error", str(e))
                return False, 'error', str(e)
            
            finally:
                # 关闭浏览器连接（不关闭浏览器窗口）
                if browser:
                    try:
                        await browser.close()
                    except:
                        pass
    
    # 执行异步流程
    success, final_status, message = asyncio.run(_run_async())
    
    state.final_status = final_status
    if not success:
        state.error_message = message
    state.end_time = time.time()
    
    # 关闭浏览器
    try:
        close_browser(browser_id)
        log("🔒 浏览器已关闭")
    except:
        pass
    
    return success, final_status, message, state


async def _do_bind_card(
    page: Page,
    card_info: dict,
    account_info: dict,
    state: ProcessState,
    update_step: Callable,
    log: Callable
) -> Tuple[bool, str]:
    """
    @brief 执行绑卡流程 (带重试和换卡机制)
    """
    from google.backend.bind_card_service import auto_bind_card, get_card_from_db
    from core.database import DBManager
    
    current_card = card_info
    max_card_retries = 3  # 最多换3张卡
    
    for card_attempt in range(max_card_retries):
        if not current_card:
            # 尝试获取新卡
            log(f"🔍 尝试获取可用卡片...")
            current_card = get_card_from_db()
            if not current_card:
                update_step(ProcessStep.BIND_CARD, "error", "无可用卡片")
                return False, "无可用卡片"
            log(f"💳 获取到卡片: ****{current_card.get('number', '')[-4:]}")
        
        max_retries = RETRY_CONFIG[ProcessStep.BIND_CARD]["max_retries"]
        delay = RETRY_CONFIG[ProcessStep.BIND_CARD]["delay"]
        last_error = ""
        card_invalid = False
        
        for attempt in range(max_retries):
            card_suffix = current_card.get('number', '')[-4:] if current_card.get('number') else '****'
            update_step(ProcessStep.BIND_CARD, "running", f"绑卡中 (卡****{card_suffix}, 第{attempt + 1}/{max_retries}次)")
            
            try:
                success, msg = await auto_bind_card(page, current_card, account_info, log_callback=log)
                
                if success:
                    update_step(ProcessStep.BIND_CARD, "success", "绑卡成功")
                    update_step(ProcessStep.SUBSCRIBE, "success", "订阅完成")
                    
                    # 绑卡成功后，通过 API 拦截检测 Antigravity 状态
                    log("🔍 检测 Antigravity 解锁状态 (API拦截)...")
                    try:
                        from google.backend.google_auth import STATUS_SUBSCRIBED_ANTIGRAVITY, _parse_api_response
                        
                        api_response_data = None
                        response_received = asyncio.Event()
                        
                        async def handle_response(response):
                            nonlocal api_response_data
                            try:
                                if 'rpcids=GI6Jdd' in response.url:
                                    text = await response.text()
                                    api_response_data = text
                                    response_received.set()
                                    log("🔍 拦截到 GI6Jdd API 响应")
                            except:
                                pass
                        
                        # 注册响应监听器
                        page.on("response", handle_response)
                        
                        try:
                            # 刷新页面触发 API 请求
                            await page.reload(wait_until='domcontentloaded')
                            
                            # 等待 API 响应（最多 10 秒）
                            try:
                                await asyncio.wait_for(response_received.wait(), timeout=10)
                            except asyncio.TimeoutError:
                                log("⏳ API 响应超时")
                            
                            # 分析 API 响应
                            if api_response_data:
                                api_status = _parse_api_response(api_response_data)
                                log(f"📊 API 响应状态: {api_status}")
                                
                                if api_status == STATUS_SUBSCRIBED_ANTIGRAVITY:
                                    log("🌟 已解锁 Antigravity！")
                                    update_step(ProcessStep.COMPLETE, "success", "🌟 订阅成功并解锁 Antigravity")
                                    return True, "绑卡订阅成功 + Antigravity已解锁"
                                elif api_status:
                                    log(f"📋 订阅状态: {api_status} (未解锁 Antigravity)")
                            else:
                                log("⚠️ 未获取到 API 响应")
                        finally:
                            # 移除响应监听器
                            page.remove_listener("response", handle_response)
                            
                    except Exception as ag_err:
                        log(f"⚠️ 检测 Antigravity 异常: {ag_err}")
                    
                    return True, msg
                else:
                    last_error = msg
                    
                    # 检查是否是新卡无效错误（绑新卡后失败）
                    if msg.startswith("CARD_INVALID:"):
                        card_invalid = True
                        last_error = msg.replace("CARD_INVALID:", "")
                        break
                    
                    # 检查是否是旧卡失败需要换绑（账号原有卡失败，不标记当前新卡为不可用）
                    if msg.startswith("REBIND_NEEDED:"):
                        last_error = msg.replace("REBIND_NEEDED:", "")
                        log(f"⚠️ 账号原有旧卡失败，需要换绑新卡（不标记当前卡为不可用）")
                        # 刷新页面重试，使用同一张新卡
                        if attempt < max_retries - 1:
                            update_step(ProcessStep.BIND_CARD, "retry", f"旧卡失败，{delay}秒后重试换绑新卡...")
                            try:
                                log("🔄 刷新页面准备换绑...")
                                await page.reload(wait_until='domcontentloaded')
                            except:
                                pass
                            await asyncio.sleep(delay)
                            continue
                        else:
                            # 重试次数用尽，但不标记卡为不可用
                            break
                    
                    raise Exception(msg)
                    
            except Exception as e:
                last_error = str(e)
                state.retry_counts[ProcessStep.BIND_CARD.value] = attempt + 1
                
                # 检查是否是新卡无效错误
                if "CARD_INVALID:" in str(e):
                    card_invalid = True
                    last_error = str(e).replace("CARD_INVALID:", "")
                    break
                
                # 检查是否是旧卡失败需要换绑
                if "REBIND_NEEDED:" in str(e):
                    last_error = str(e).replace("REBIND_NEEDED:", "")
                    log(f"⚠️ 账号原有旧卡失败，需要换绑新卡")
                    if attempt < max_retries - 1:
                        update_step(ProcessStep.BIND_CARD, "retry", f"旧卡失败，{delay}秒后重试换绑新卡...")
                        try:
                            log("🔄 刷新页面准备换绑...")
                            await page.reload(wait_until='domcontentloaded')
                        except:
                            pass
                        await asyncio.sleep(delay)
                        continue
                    else:
                        break
                
                if attempt < max_retries - 1:
                    update_step(ProcessStep.BIND_CARD, "retry", f"绑卡失败: {e}，{delay}秒后重试...")
                    # 刷新页面清除之前的状态
                    try:
                        log("🔄 刷新页面重试...")
                        await page.reload(wait_until='domcontentloaded')
                    except:
                        pass
                    await asyncio.sleep(delay)
                else:
                    update_step(ProcessStep.BIND_CARD, "error", f"绑卡失败: {e}")
        
        # 如果新卡无效，标记并换卡
        if card_invalid:
            card_id = current_card.get('id')
            card_suffix = current_card.get('number', '')[-4:] if current_card.get('number') else '****'
            log(f"❌ 新卡 ****{card_suffix} 无效，标记为不可用")
            
            try:
                DBManager.set_card_active(card_id, False)
                log(f"✅ 已禁用卡片 ID: {card_id}")
            except Exception as db_err:
                log(f"⚠️ 禁用卡片失败: {db_err}")
            
            # 清空当前卡，下一轮循环会获取新卡
            current_card = None
            
            if card_attempt < max_card_retries - 1:
                update_step(ProcessStep.BIND_CARD, "retry", f"换卡重试 (第{card_attempt + 2}/{max_card_retries}张)...")
                
                # 刷新页面清除之前的 iframe 状态
                log("🔄 刷新页面准备换卡...")
                try:
                    await page.reload(wait_until='domcontentloaded')
                    await asyncio.sleep(1)  # 等待页面稳定
                except Exception as reload_err:
                    log(f"⚠️ 刷新页面失败: {reload_err}")
                
                continue
            else:
                update_step(ProcessStep.BIND_CARD, "error", "所有卡片都已尝试，无可用卡片")
                return False, "所有卡片都无效或不可用"
        else:
            # 不是卡无效错误，直接返回失败
            break
    
    return False, last_error or "绑卡重试次数用尽"


# ==================== 批量处理 ====================

def process_all_in_one_batch(
    browser_ids: list,
    api_key: str = '',
    card_info: dict = None,
    log_callback: LogCallback = None,
    step_callback: StepCallback = None,
    progress_callback: ProgressCallback = None,
    batch_progress_callback: Callable = None,  # (current, total, state)
    stop_check: Callable = None,
    thread_count: int = 1  # 并发线程数
) -> Dict[str, Any]:
    """
    @brief 批量处理浏览器的全自动流程（支持多线程）
    @param browser_ids 浏览器ID列表
    @param api_key SheerID验证API Key
    @param card_info 卡信息
    @param log_callback 日志回调
    @param step_callback 步骤回调
    @param progress_callback 单个进度回调
    @param batch_progress_callback 批量进度回调 (current, total, state)
    @param stop_check 停止检查函数
    @param thread_count 并发线程数
    @return 统计结果字典
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    stats = {
        'total': len(browser_ids),
        'processed': 0,
        'subscribed_antigravity': 0,
        'subscribed': 0,
        'verified': 0,
        'link_ready': 0,
        'ineligible': 0,
        'not_logged_in': 0,
        'error': 0,
        'results': []  # 每个账号的详细结果
    }
    
    _stats_lock = threading.Lock()
    
    def process_single(idx_browser):
        """处理单个浏览器"""
        idx, browser_id = idx_browser
        
        if stop_check and stop_check():
            return None
        
        log_callback and log_callback(f"\n{'='*50}")
        log_callback and log_callback(f"📋 处理 {idx+1}/{len(browser_ids)}: {browser_id}")
        log_callback and log_callback(f"{'='*50}")
        
        success, status, message, state = process_all_in_one(
            browser_id, 
            api_key, 
            card_info, 
            log_callback,
            step_callback,
            progress_callback
        )
        
        with _stats_lock:
            stats['processed'] += 1
            
            # 更新统计
            if status in stats:
                stats[status] += 1
            else:
                stats['error'] += 1
            
            # 记录详细结果
            stats['results'].append(state.to_dict())
        
        # 回调批量进度
        if batch_progress_callback:
            batch_progress_callback(stats['processed'], len(browser_ids), state)
        
        return state
    
    # 使用线程池并发处理
    actual_threads = max(1, min(thread_count, len(browser_ids)))
    log_callback and log_callback(f"🚀 启动 {actual_threads} 个线程并发处理 {len(browser_ids)} 个账号")
    
    if actual_threads == 1:
        # 单线程模式，按顺序处理
        for i, browser_id in enumerate(browser_ids):
            if stop_check and stop_check():
                log_callback and log_callback("⛔ 用户停止处理")
                break
            process_single((i, browser_id))
    else:
        # 多线程模式
        with ThreadPoolExecutor(max_workers=actual_threads) as executor:
            futures = {
                executor.submit(process_single, (i, bid)): bid 
                for i, bid in enumerate(browser_ids)
            }
            
            for future in as_completed(futures):
                if stop_check and stop_check():
                    log_callback and log_callback("⛔ 用户停止处理")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    future.result()
                except Exception as e:
                    log_callback and log_callback(f"❌ 线程异常: {e}")
    
    return stats


# ==================== Web API 支持 ====================

# 全局任务状态存储 (用于 Web API)
_active_tasks: Dict[str, ProcessState] = {}
_batch_task_status: Dict[str, Any] = {}


def get_active_task(task_id: str) -> Optional[ProcessState]:
    """获取活跃任务状态"""
    return _active_tasks.get(task_id)


def get_all_active_tasks() -> Dict[str, Dict]:
    """获取所有活跃任务"""
    return {tid: state.to_dict() for tid, state in _active_tasks.items()}


def get_batch_task_status(task_id: str) -> Optional[Dict]:
    """获取批量任务状态"""
    return _batch_task_status.get(task_id)


def start_batch_task(
    task_id: str,
    browser_ids: list,
    api_key: str = '',
    card_info: dict = None,
    thread_count: int = 1
) -> Dict:
    """
    @brief 启动批量处理任务 (供 Web API 调用)
    @param thread_count 并发线程数
    @return 初始状态
    """
    import threading
    
    # 线程锁 - 用于保护共享状态
    _task_lock = threading.Lock()
    
    _batch_task_status[task_id] = {
        'task_id': task_id,
        'status': 'running',
        'total': len(browser_ids),
        'processed': 0,
        'current_browser': '',
        'current_step': '',
        'current_step_status': '',
        'current_step_message': '',
        'thread_count': thread_count,
        'stats': {
            'subscribed_antigravity': 0,
            'subscribed': 0,
            'verified': 0,
            'link_ready': 0,
            'ineligible': 0,
            'not_logged_in': 0,
            'error': 0,
        },
        'logs': [],
        'results': [],
        'stop_requested': False,
    }
    
    def log_cb(msg):
        with _task_lock:
            status = _batch_task_status.get(task_id)
            if status:
                status['logs'].append({
                    'time': time.time(),
                    'message': msg
                })
                # 只保留最近 500 条日志
                if len(status['logs']) > 500:
                    status['logs'] = status['logs'][-500:]
    
    def step_cb(step, step_status, message):
        with _task_lock:
            status = _batch_task_status.get(task_id)
            if status:
                step_name = STEP_DISPLAY.get(step, step.value)
                status['current_step'] = step_name
                status['current_step_status'] = step_status
                status['current_step_message'] = message
    
    def progress_cb(state):
        with _task_lock:
            _active_tasks[state.browser_id] = state
            status = _batch_task_status.get(task_id)
            if status:
                status['current_browser'] = state.browser_id
    
    def batch_progress_cb(current, total, state):
        with _task_lock:
            status = _batch_task_status.get(task_id)
            if status:
                status['processed'] = current
                status['results'].append(state.to_dict())
                
                # 更新统计
                final_status = state.final_status
                if final_status in status['stats']:
                    status['stats'][final_status] += 1
                elif final_status:
                    status['stats']['error'] += 1
    
    def stop_check():
        status = _batch_task_status.get(task_id)
        return status and status.get('stop_requested', False)
    
    def run_task():
        try:
            process_all_in_one_batch(
                browser_ids,
                api_key,
                card_info,
                log_callback=log_cb,
                step_callback=step_cb,
                progress_callback=progress_cb,
                batch_progress_callback=batch_progress_cb,
                stop_check=stop_check,
                thread_count=thread_count
            )
        finally:
            status = _batch_task_status.get(task_id)
            if status:
                status['status'] = 'completed' if not status.get('stop_requested') else 'stopped'
    
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()
    
    return _batch_task_status[task_id]


def stop_batch_task(task_id: str) -> bool:
    """停止批量任务"""
    status = _batch_task_status.get(task_id)
    if status:
        status['stop_requested'] = True
        return True
    return False
