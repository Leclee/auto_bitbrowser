"""
一键全自动处理 GUI - 登录 → 状态检测 → SheerID验证 → 绑卡订阅
"""
import sys
import os
import asyncio
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLabel, QLineEdit, QTextEdit, 
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QMessageBox, QCheckBox, QSpinBox, QGroupBox,
                              QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from playwright.async_api import async_playwright
from bit_api import openBrowser, closeBrowser
from create_window import get_browser_info, get_browser_list
from database import DBManager
from sheerid_verifier import SheerIDVerifier

class AutoAllInOneWorker(QThread):
    """一键全自动工作线程"""
    progress_signal = pyqtSignal(str, str, str)  # browser_id, status, message
    finished_signal = pyqtSignal()
    log_signal = pyqtSignal(str)
    
    def __init__(self, accounts, cards, cards_per_account, delays, api_key, thread_count=3):
        super().__init__()
        self.accounts = accounts
        self.cards = cards
        self.cards_per_account = cards_per_account
        self.delays = delays
        self.api_key = api_key
        self.thread_count = thread_count
        self.is_running = True
    
    def run(self):
        try:
            asyncio.run(self._process_all())
        except Exception as e:
            self.log_signal.emit(f"❌ 工作线程错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.finished_signal.emit()
    
    async def _process_all(self):
        """处理所有账号（支持并发）"""
        card_index = 0
        card_usage_count = 0
        
        # 将账号分批处理
        for batch_start in range(0, len(self.accounts), self.thread_count):
            if not self.is_running:
                break
            
            batch_end = min(batch_start + self.thread_count, len(self.accounts))
            batch_accounts = self.accounts[batch_start:batch_end]
            
            self.log_signal.emit(f"\n{'='*50}")
            self.log_signal.emit(f"并发处理第 {batch_start+1}-{batch_end} 个账号（共 {len(self.accounts)} 个）")
            self.log_signal.emit(f"{'='*50}")
            
            # 为每个账号分配卡片和创建任务
            tasks = []
            for i, account in enumerate(batch_accounts):
                global_index = batch_start + i
                
                # 检查是否需要切换到下一张卡
                if card_usage_count >= self.cards_per_account:
                    card_index += 1
                    card_usage_count = 0
                    self.log_signal.emit(f"💳 切换到下一张卡 (卡 #{card_index + 1})")
                
                # 检查卡是否用完
                if card_index >= len(self.cards):
                    self.log_signal.emit("⚠️ 卡片已用完，停止处理")
                    break
                
                current_card = self.cards[card_index] if card_index < len(self.cards) else None
                
                # 创建异步任务
                task = self._process_single_account_wrapper(
                    account, 
                    current_card, 
                    global_index + 1
                )
                tasks.append(task)
                
                if current_card:
                    card_usage_count += 1
            
            # 并发执行这一批
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_single_account_wrapper(self, account, card_info, index):
        """单个账号处理的包装器"""
        if not self.is_running:
            return
        
        browser_id = account.get('browser_id')
        email = account.get('email')
        
        self.log_signal.emit(f"\n[{index}] 开始处理账号: {email}")
        
        try:
            success, message = await self._process_single_account(
                browser_id, email, card_info
            )
            
            if success:
                self.progress_signal.emit(browser_id, "✅ 完成", message)
                self.log_signal.emit(f"[{index}] ✅ {email}: {message}")
                
                # 更新卡片使用计数
                if card_info and card_info.get('id'):
                    try:
                        from database import DBManager
                        DBManager.increment_card_usage(card_info['id'])
                    except Exception as e:
                        self.log_signal.emit(f"[{index}] ⚠️ 更新卡片使用计数失败: {e}")
            else:
                self.progress_signal.emit(browser_id, "❌ 失败", message)
                self.log_signal.emit(f"[{index}] ❌ {email}: {message}")
                
        except Exception as e:
            error_msg = f"处理出错: {e}"
            self.progress_signal.emit(browser_id, "❌ 错误", error_msg)
            self.log_signal.emit(f"[{index}] ❌ {email}: {error_msg}")
    
    async def _process_single_account(self, browser_id, email, card_info):
        """
        处理单个账号的完整流程
        1. 登录
        2. 检测状态
        3. 根据状态执行相应操作
        """
        try:
            # 获取账号信息
            target_browser = get_browser_info(browser_id)
            if not target_browser:
                return False, "无法获取浏览器信息"
            
            remark = target_browser.get('remark', '')
            parts = remark.split('----')
            
            account_info = None
            if len(parts) >= 4:
                account_info = {
                    'email': parts[0].strip(),
                    'password': parts[1].strip(),
                    'backup': parts[2].strip(),
                    'secret': parts[3].strip()
                }
            
            # 打开浏览器（全程不关闭）
            self.progress_signal.emit(browser_id, "🚀 启动中", "正在打开浏览器...")
            result = openBrowser(browser_id)
            if not result.get('success'):
                return False, f"打开浏览器失败"
            
            ws_endpoint = result['data']['ws']
            
            async with async_playwright() as playwright:
                try:
                    chromium = playwright.chromium
                    browser = await chromium.connect_over_cdp(ws_endpoint)
                    context = browser.contexts[0]
                    page = context.pages[0] if context.pages else await context.new_page()
                    
                    # 从 auto_bind_card 导入
                    from auto_bind_card import check_and_login, auto_bind_card
                    
                    # Step 1: 导航到目标页面并登录检测
                    self.log_signal.emit(f"  🔐 步骤1: 导航并登录检测...")
                    self.progress_signal.emit(browser_id, "🔐 登录中", "正在检测登录状态...")
                    
                    target_url = "https://one.google.com/ai-student?g1_landing_page=75&utm_source=antigravity&utm_campaign=argon_limit_reached"
                    
                    # 先导航到目标页面
                    await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(3)
                    
                    # 然后检测登录
                    login_success, login_msg = await check_and_login(page, account_info)
                    if not login_success:
                        return False, f"登录失败: {login_msg}"
                    
                    self.log_signal.emit(f"  ✅ 登录成功")
                    self.progress_signal.emit(browser_id, "✅ 登录成功", "登录完成，准备检测状态")
                    
                    # Step 2: 状态检测
                    self.log_signal.emit(f"  🔍 步骤2: 状态检测...")
                    self.progress_signal.emit(browser_id, "🔍 检测中", "正在分析账号资格...")
                    await asyncio.sleep(3)
                    
                    # 检测状态（使用内联逻辑）
                    status = await self._detect_status(page)
                    self.log_signal.emit(f"  📊 当前状态: {status}")
                    self.progress_signal.emit(browser_id, f"📊 {status}", f"状态检测完成: {status}")
                    
                    # Step 3: 根据状态执行操作
                    if status == "link_ready":
                        # 有资格待验证 → 提取链接 → 验证 → 绑卡
                        self.progress_signal.emit(browser_id, "🔗 提取链接", "正在提取SheerID验证链接...")
                        return await self._handle_link_ready(page, email, card_info, browser_id)
                        
                    elif status == "verified":
                        # 已验证未绑卡 → 直接绑卡
                        self.progress_signal.emit(browser_id, "💳 准备绑卡", "已验证，准备绑卡...")
                        return await self._handle_verified(page, card_info, account_info, browser_id)
                        
                    elif status == "subscribed":
                        # 已订阅
                        return True, "账号已订阅，无需处理"
                        
                    elif status == "ineligible":
                        # 无资格
                        return False, "账号无资格"
                        
                    else:
                        # 其他状态
                        return False, f"未知状态: {status}"
                    
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return False, str(e)
                    
        except Exception as e:
            return False, str(e)
    
    async def _detect_status(self, page):
        """
        检测账号当前状态 (调用 run_playwright_google.py 统一逻辑)
        返回: link_ready, verified, subscribed, ineligible, error
        """
        from run_playwright_google import check_google_one_status
        
        self.log_signal.emit(f"  🔍 调用 run_playwright_google 模块进行多轮状态检测...")
        
        try:
            # 调用复用的函数 (timeout=15)
            status, extra_data = await check_google_one_status(page, timeout=15)
            
            if status == "timeout":
                self.log_signal.emit("  ⚠️ 检测超时")
                return "error"
            
            self.log_signal.emit(f"  ✅ 检测结果: {status}")
            return status
            
        except Exception as e:
            self.log_signal.emit(f"  ❌ 检测出错: {e}")
            import traceback
            traceback.print_exc()
            return "error"

    
    async def _handle_link_ready(self, page, email, card_info, browser_id=None):
        """处理有资格待验证的账号"""
        try:
            self.log_signal.emit(f"  🔗 步骤3a: 提取SheerID链接...")
            
            # 提取链接（内联实现）
            try:
                # 0. 直接从页面提取 SheerID 链接 (最优先)
                # 用户反馈链接就在 a 标签中: <a href="https://services.sheerid.com/verify/..." ...>
                # 不需要 is_visible() 检查，只要存在就提取
                sheerid_locator = page.locator('a[href*="sheerid.com"]').first
                if await sheerid_locator.count() > 0:
                     link = await sheerid_locator.get_attribute("href")
                     self.log_signal.emit(f"  ℹ️ 直接从页面提取到 SheerID 链接")
                
                else:
                    # 1. 如果没提取到，才尝试点击按钮触发
                    # ... (保留点击逻辑作为后备)
                    verify_btns = [
                        'button:has-text("Verify eligibility")', 
                        'button:has-text("verify your eligibility")',
                        'a:has-text("Verify eligibility")',
                        'div[role="button"]:has-text("Verify eligibility")',
                        'text="Verify eligibility"', # 兜底
                        'text="verify your eligibility"'
                    ]
                    
                    clicked = False
                    for selector in verify_btns:
                        btn = page.locator(selector).first
                        if await btn.count() > 0 and await btn.is_visible():
                            self.log_signal.emit(f"  🖱️ 点击验证按钮: {selector}")
                            await btn.click()
                            clicked = True
                            break
                    
                    if not clicked:
                        self.log_signal.emit("  ⚠️ 未找到明显的验证按钮，尝试直接寻找链接...")
                    
                    await asyncio.sleep(3)
                
                # 如果上面已经获取到 link，则跳过后续查找
                if not 'link' in locals() or not link:
                    # 等待新页面或iframe加载
                    await asyncio.sleep(2)
                    
                    # 获取当前URL或iframe中的链接
                    link = None
                    current_url = page.url
                    
                    if "sheerid" in current_url.lower():
                        link = current_url
                    else:
                        # 尝试从iframe获取
                        frames = page.frames
                        for frame in frames:
                            frame_url = frame.url
                            if "sheerid" in frame_url.lower():
                                link = frame_url
                                break
                    
                    if not link:
                        # 再次尝试从页面内容中提取 (作为最后的保险)
                        page_content = await page.content()
                        import re
                        sheerid_match = re.search(r'https://[^"\']*sheerid[^"\']*', page_content)
                        if sheerid_match:
                            link = sheerid_match.group()
            
            except Exception as e:
                self.log_signal.emit(f"  ⚠️ 提取链接时出错: {e}")
                if 'link' not in locals(): link = None
            
            if not link:
                return False, "无法提取SheerID链接"
            
            self.log_signal.emit(f"  ✅ 链接提取成功: {link[:50]}...")
            if browser_id: self.progress_signal.emit(browser_id, "✔️ 验证中", "已提取链接，开始SheerID验证...")
            
            # 保存链接到数据库
            from account_manager import AccountManager
            line = f"{link}----{email}"
            AccountManager.save_link(line)
            
            # Step 3b: 验证SheerID
            self.log_signal.emit(f"  ✔️ 步骤3b: SheerID验证...")
            
            verifier = SheerIDVerifier(api_key=self.api_key)
            
            # 提取 VID 用于 verify_batch
            import re
            vid = link
            if "http" in vid:
                 match = re.search(r'verificationId=([a-zA-Z0-9]+)', link)
                 if match: vid = match.group(1)
            
            # 定义实时回调函数
            def verification_callback(callback_vid, msg):
                # 将实时消息发送到 UI
                # 注意：callback可能在任何线程调用，emit是线程安全的
                if browser_id:
                    self.progress_signal.emit(browser_id, "⏳ 验证中", f"{msg}")
                # 也可以打印到日志
                # self.log_signal.emit(f"    [SheerID] {msg}")

            # 调用 verify_batch 并传入回调
            # 注意：verify_batch 是同步阻塞的（内部有轮询），所以用 to_thread 放到后台执行
            results = await asyncio.to_thread(
                verifier.verify_batch,
                [vid],
                callback=verification_callback
            )

            # 处理最终结果
            success = False
            msg = "验证未完成"
            
            if vid in results:
                res = results[vid]
                status = res.get('status')
                msg = res.get('message') or res.get('msg') or ''
                
                # 判断成功条件 (与 sheerid_verifier.py 保持一致)
                if status == 'success' or res.get('success') == True or "successfully" in msg.lower():
                    success = True
                    msg = f"验证成功: {msg}" if msg else "验证成功"
                else:
                    success = False
                    msg = f"验证失败: {msg or '未知错误'}"
            
            if not success:
                return False, f"SheerID验证失败: {msg}"
            
            self.log_signal.emit(f"  ✅ SheerID验证成功: {msg}")
            if browser_id: self.progress_signal.emit(browser_id, "✅ 验证成功", "SheerID验证通过，准备刷新...")
            
            # 更新状态为已验证
            AccountManager.move_to_verified(line)
            
            # 刷新页面
            await page.reload(wait_until='domcontentloaded')
            await asyncio.sleep(5)
            
            # Step 3c: 绑卡订阅
            return await self._handle_verified(page, card_info, None, browser_id)
            
        except Exception as e:
            return False, f"处理link_ready状态出错: {e}"
    
    async def _handle_verified(self, page, card_info, account_info, browser_id=None):
        """处理已验证未绑卡的账号"""
        try:
            self.log_signal.emit(f"  💳 步骤4: 绑卡订阅...")
            if browser_id: self.progress_signal.emit(browser_id, "💳 绑卡中", "正在执行绑卡操作...")
            
            if not card_info:
                return False, "没有可用的卡片"
            
            # 使用现有的绑卡函数
            from auto_bind_card import auto_bind_card
            
            success, message = await auto_bind_card(
                page, 
                card_info=card_info, 
                account_info=account_info
            )
            
            if success:
                self.log_signal.emit(f"  ✅ 绑卡订阅成功")
                return True, "全流程完成：已绑卡订阅"
            else:
                return False, f"绑卡失败: {message}"
                
        except Exception as e:
            return False, f"绑卡过程出错: {e}"
    
    def stop(self):
        """停止工作线程"""
        self.is_running = False


class AutoAllInOneWindow(QWidget):
    """一键全自动处理窗口"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.initUI()
        self.load_accounts()
        self.load_cards()
    
    def initUI(self):
        self.setWindowTitle("一键全自动处理")
        self.setGeometry(100, 100, 1000, 750)
        
        layout = QVBoxLayout()
        
        # 顶部设置区域
        settings_group = QGroupBox("设置")
        settings_layout = QFormLayout()
        
        # SheerID API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("请输入SheerID API Key")
        settings_layout.addRow("API Key:", self.api_key_input)
        
        # 一卡几绑
        self.cards_per_account_spin = QSpinBox()
        self.cards_per_account_spin.setMinimum(1)
        self.cards_per_account_spin.setMaximum(100)
        self.cards_per_account_spin.setValue(1)
        settings_layout.addRow("一卡几绑:", self.cards_per_account_spin)
        
        # 并发数
        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setMinimum(1)
        self.thread_count_spin.setMaximum(20)
        self.thread_count_spin.setValue(3)
        settings_layout.addRow("并发数:", self.thread_count_spin)
        
        #延迟设置
        delay_layout = QHBoxLayout()
        
        self.delay_after_offer = QSpinBox()
        self.delay_after_offer.setMinimum(1)
        self.delay_after_offer.setMaximum(60)
        self.delay_after_offer.setValue(8)
        delay_layout.addWidget(QLabel("Offer后:"))
        delay_layout.addWidget(self.delay_after_offer)
        delay_layout.addWidget(QLabel("秒"))
        
        self.delay_after_add_card = QSpinBox()
        self.delay_after_add_card.setMinimum(1)
        self.delay_after_add_card.setMaximum(60)
        self.delay_after_add_card.setValue(10)
        delay_layout.addWidget(QLabel("AddCard后:"))
        delay_layout.addWidget(self.delay_after_add_card)
        delay_layout.addWidget(QLabel("秒"))
        
        self.delay_after_save = QSpinBox()
        self.delay_after_save.setMinimum(1)
        self.delay_after_save.setMaximum(60)
        self.delay_after_save.setValue(18)
        delay_layout.addWidget(QLabel("Save后:"))
        delay_layout.addWidget(self.delay_after_save)
        delay_layout.addWidget(QLabel("秒"))
        
        settings_layout.addRow("延迟:", delay_layout)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # 卡片和账号信息
        info_layout = QHBoxLayout()
        self.card_count_label = QLabel("卡片: 0")
        info_layout.addWidget(self.card_count_label)
        self.account_count_label = QLabel("账号: 0")
        info_layout.addWidget(self.account_count_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # 账号列表
        accounts_label = QLabel("待处理账号列表:")
        layout.addWidget(accounts_label)
        
        # 全选复选框
        select_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("全选/取消全选")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        select_layout.addWidget(self.select_all_checkbox)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["选择", "邮箱", "浏览器ID", "状态", "消息"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # 日志区域
        log_label = QLabel("运行日志:")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("刷新列表")
        self.btn_refresh.clicked.connect(self.refresh_all)
        button_layout.addWidget(self.btn_refresh)
        
        self.btn_start = QPushButton("开始全自动处理")
        self.btn_start.clicked.connect(self.start_processing)
        button_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_processing)
        button_layout.addWidget(self.btn_stop)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_cards(self):
        """从数据库加载可用卡片"""
        self.cards = []
        
        try:
            DBManager.init_db()
            db_cards = DBManager.get_available_cards()
            
            for card in db_cards:
                self.cards.append({
                    'id': card['id'],
                    'number': card['card_number'],
                    'exp_month': card['exp_month'],
                    'exp_year': card['exp_year'],
                    'cvv': card['cvv'],
                    'holder_name': card.get('holder_name'),
                    'max_usage': card.get('max_usage', 1),
                    'usage_count': card.get('usage_count', 0)
                })
            
            self.card_count_label.setText(f"卡片: {len(self.cards)}")
            self.log(f"✅ 从数据库加载了 {len(self.cards)} 张可用卡片")
            
            if not self.cards:
                self.log("⚠️ 数据库中没有可用卡片，请在Web管理后台导入卡片")
            
        except Exception as e:
            self.card_count_label.setText(f"卡片: 0")
            self.log(f"❌ 加载卡片失败: {e}")
            import traceback
            traceback.print_exc()
    
    def load_accounts(self):
        """加载所有待处理账号"""
        try:
            DBManager.init_db()
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            # 查询所有非已订阅和无资格的账号（包括待检测资格的）
            cursor.execute("""
                SELECT email, password, recovery_email, secret_key, verification_link 
                FROM accounts 
                WHERE status NOT IN ('subscribed', 'ineligible')
                ORDER BY 
                    CASE status
                        WHEN 'link_ready' THEN 1
                        WHEN 'verified' THEN 2
                        WHEN 'pending_check' THEN 3
                        ELSE 4
                    END,
                    email
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            # 获取浏览器列表
            browsers = get_browser_list(page=0, pageSize=1000)
            email_to_browser = {}
            for browser in browsers:
                remark = browser.get('remark', '')
                if '----' in remark:
                    parts = remark.split('----')
                    if parts and '@' in parts[0]:
                        browser_email = parts[0].strip()
                        browser_id = browser.get('id', '')
                        email_to_browser[browser_email] = browser_id
            
            self.table.setRowCount(0)
            self.accounts = []
            
            for row in rows:
                email = row[0]
                browser_id = email_to_browser.get(email, '')
                
                if not browser_id:
                    continue
                
                account = {
                    'email': email,
                    'password': row[1] or '',
                    'backup': row[2] or '',
                    'secret': row[3] or '',
                    'link': row[4] or '',
                    'browser_id': browser_id
                }
                self.accounts.append(account)
                
                # 添加到表格
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)
                
                # 复选框
                checkbox = QCheckBox()
                checkbox.setChecked(True)
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row_idx, 0, checkbox_widget)
                
                self.table.setItem(row_idx, 1, QTableWidgetItem(account['email']))
                self.table.setItem(row_idx, 2, QTableWidgetItem(account['browser_id']))
                self.table.setItem(row_idx, 3, QTableWidgetItem("待处理"))
                self.table.setItem(row_idx, 4, QTableWidgetItem(""))
            
            self.account_count_label.setText(f"账号: {len(self.accounts)}")
            self.log(f"✅ 加载了 {len(self.accounts)} 个待处理账号")
            
        except Exception as e:
            self.log(f"❌ 加载账号失败: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_all(self):
        """刷新"""
        self.load_accounts()
        self.load_cards()
    
    def toggle_select_all(self, state):
        """全选/取消全选"""
        is_checked = (state == Qt.CheckState.Checked.value)
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(is_checked)
    
    def get_selected_accounts(self):
        """获取选中的账号"""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    if row < len(self.accounts):
                        selected.append(self.accounts[row])
        return selected
    
    def start_processing(self):
        """开始处理"""
        selected_accounts = self.get_selected_accounts()
        
        if not selected_accounts:
            QMessageBox.warning(self, "提示", "请先勾选要处理的账号")
            return
        
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "提示", "请输入SheerID API Key")
            return
        
        # 收集设置
        delays = {
            'after_offer': self.delay_after_offer.value(),
            'after_add_card': self.delay_after_add_card.value(),
            'after_save': self.delay_after_save.value()
        }
        
        cards_per_account = self.cards_per_account_spin.value()
        thread_count = self.thread_count_spin.value()
        
        self.log(f"\n{'='*50}")
        self.log(f"开始全自动处理")
        self.log(f"选中账号: {len(selected_accounts)}")
        self.log(f"卡片数量: {len(self.cards)}")
        self.log(f"一卡几绑: {cards_per_account}")
        self.log(f"并发数: {thread_count}")
        self.log(f"{'='*50}\n")
        
        # 创建并启动工作线程
        self.worker = AutoAllInOneWorker(
            selected_accounts,
            self.cards,
            cards_per_account,
            delays,
            api_key,
            thread_count
        )
        self.worker.progress_signal.connect(self.update_account_status)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_refresh.setEnabled(False)
    
    def stop_processing(self):
        """停止处理"""
        if self.worker:
            self.worker.stop()
            self.log("⚠️ 正在停止...")
    
    def on_finished(self):
        """处理完成"""
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_refresh.setEnabled(True)
        self.log("\n✅ 全自动处理任务完成！")
        QMessageBox.information(self, "完成", "全自动处理任务已完成")
    
    def update_account_status(self, browser_id, status, message):
        """更新表格状态"""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 2) and self.table.item(row, 2).text() == browser_id:
                self.table.setItem(row, 3, QTableWidgetItem(status))
                self.table.setItem(row, 4, QTableWidgetItem(message))
                break
    
    def log(self, message):
        """添加日志"""
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    app = QApplication(sys.argv)
    window = AutoAllInOneWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
