"""
一键绑卡订阅 GUI
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
from create_window import get_browser_info
from auto_bind_card import auto_bind_card
from database import DBManager

class BindCardWorker(QThread):
    """绑卡工作线程"""
    progress_signal = pyqtSignal(str, str, str)  # browser_id, status, message
    finished_signal = pyqtSignal()
    log_signal = pyqtSignal(str)
    
    def __init__(self, accounts, cards, cards_per_account, delays, thread_count=3):
        super().__init__()
        self.accounts = accounts  # verified 状态的账号列表
        self.cards = cards  # cards.txt 中的卡信息列表
        self.cards_per_account = cards_per_account  # 一卡几绑
        self.delays = delays  # 延迟设置字典
        self.thread_count = thread_count  # 并发数
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
        """处理所有账号的绑卡（支持并发）"""
        card_index = 0
        card_usage_count = 0
        
        # 将账号分批处理，每批 thread_count 个
        for batch_start in range(0, len(self.accounts), self.thread_count):
            if not self.is_running:
                break
            
            batch_end = min(batch_start + self.thread_count, len(self.accounts))
            batch_accounts = self.accounts[batch_start:batch_end]
            
            self.log_signal.emit(f"\n{'='*50}")
            self.log_signal.emit(f"并发处理第 {batch_start+1}-{batch_end} 个账号（共 {len(self.accounts)} 个）")
            self.log_signal.emit(f"{'='*50}")
            
            # 为每个账号分配卡片
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
                
                current_card = self.cards[card_index]
                
                # 创建异步任务
                task = self._process_single_account_wrapper(
                    account, 
                    current_card, 
                    global_index + 1
                )
                tasks.append(task)
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
        
        self.log_signal.emit(f"\n[{index}] 处理账号: {email}")
        self.log_signal.emit(f"[{index}] 使用卡片: {card_info['number']}")
        
        try:
            success, message = await self._process_single_account(
                browser_id, email, card_info
            )
            
            if success:
                self.progress_signal.emit(browser_id, "✅ 成功", message)
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
        """处理单个账号的绑卡"""
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
            
            # 打开浏览器
            result = openBrowser(browser_id)
            if not result.get('success'):
                return False, f"打开浏览器失败: {result}"
            
            ws_endpoint = result['data']['ws']
            
            async with async_playwright() as playwright:
                try:
                    chromium = playwright.chromium
                    browser = await chromium.connect_over_cdp(ws_endpoint)
                    context = browser.contexts[0]
                    page = context.pages[0] if context.pages else await context.new_page()
                    
                    # 导航到目标页面
                    target_url = "https://one.google.com/ai-student?g1_landing_page=75&utm_source=antigravity&utm_campaign=argon_limit_reached"
                    await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
                    
                    # 等待页面加载
                    await asyncio.sleep(5)
                    
                    # 执行自动绑卡（使用自定义延迟）
                    # TODO: 需要修改 auto_bind_card 函数支持自定义延迟
                    success, message = await auto_bind_card(page, card_info=card_info, account_info=account_info)
                    
                    return success, message
                    
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return False, str(e)
                finally:
                    # 不关闭浏览器
                    pass
                    
        except Exception as e:
            return False, str(e)
    
    def stop(self):
        """停止工作线程"""
        self.is_running = False


class BindCardWindow(QWidget):
    """一键绑卡订阅窗口"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.initUI()
        self.load_accounts()
        self.load_cards()
    
    def initUI(self):
        self.setWindowTitle("一键绑卡订阅")
        self.setGeometry(100, 100, 1000, 700)
        
        layout = QVBoxLayout()
        
        # 顶部设置区域
        settings_group = QGroupBox("设置")
        settings_layout = QFormLayout()
        
        # 一卡几绑
        self.cards_per_account_spin = QSpinBox()
        self.cards_per_account_spin.setMinimum(1)
        self.cards_per_account_spin.setMaximum(100)
        self.cards_per_account_spin.setValue(1)
        settings_layout.addRow("一卡几绑:", self.cards_per_account_spin)
        
        # 并发数设置
        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setMinimum(1)
        self.thread_count_spin.setMaximum(20)
        self.thread_count_spin.setValue(3)
        settings_layout.addRow("并发数:", self.thread_count_spin)
        
        # 延迟设置（秒）
        delay_layout = QHBoxLayout()
        
        self.delay_after_offer = QSpinBox()
        self.delay_after_offer.setMinimum(1)
        self.delay_after_offer.setMaximum(60)
        self.delay_after_offer.setValue(8)
        delay_layout.addWidget(QLabel("点击Offer后:"))
        delay_layout.addWidget(self.delay_after_offer)
        delay_layout.addWidget(QLabel("秒"))
        
        self.delay_after_add_card = QSpinBox()
        self.delay_after_add_card.setMinimum(1)
        self.delay_after_add_card.setMaximum(60)
        self.delay_after_add_card.setValue(10)
        delay_layout.addWidget(QLabel("点击Add Card后:"))
        delay_layout.addWidget(self.delay_after_add_card)
        delay_layout.addWidget(QLabel("秒"))
        
        self.delay_after_save = QSpinBox()
        self.delay_after_save.setMinimum(1)
        self.delay_after_save.setMaximum(60)
        self.delay_after_save.setValue(18)
        delay_layout.addWidget(QLabel("点击Save后:"))
        delay_layout.addWidget(self.delay_after_save)
        delay_layout.addWidget(QLabel("秒"))
        
        settings_layout.addRow("延迟设置:", delay_layout)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # 卡片信息
        card_info_label = QLabel(f"卡片文件: cards.txt")
        layout.addWidget(card_info_label)
        
        self.card_count_label = QLabel("卡片数量: 0")
        layout.addWidget(self.card_count_label)
        
        # 账号列表
        accounts_label = QLabel("待绑卡账号列表（已验证未绑卡）:")
        layout.addWidget(accounts_label)
        
        # 全选复选框
        select_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("全选/取消全选")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        select_layout.addWidget(self.select_all_checkbox)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)  # 增加一列复选框
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
        
        self.btn_start = QPushButton("开始绑卡订阅")
        self.btn_start.clicked.connect(self.start_binding)
        button_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_binding)
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
            
            self.card_count_label.setText(f"卡片数量: {len(self.cards)}")
            self.log(f"✅ 从数据库加载了 {len(self.cards)} 张可用卡片")
            
            if not self.cards:
                self.log("⚠️ 数据库中没有可用卡片，请在Web管理后台导入卡片")
            
        except Exception as e:
            self.card_count_label.setText(f"卡片数量: 0 (加载失败)")
            self.log(f"❌ 加载卡片失败: {e}")
            import traceback
            traceback.print_exc()
    
    def load_accounts(self):
        """从数据库加载已验证未绑卡的账号，并匹配浏览器ID"""
        try:
            from create_window import get_browser_list
            
            DBManager.init_db()
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            # 查询 verified 状态的账号（使用正确的字段名）
            cursor.execute("""
                SELECT email, password, recovery_email, secret_key, verification_link 
                FROM accounts 
                WHERE status = 'verified'
                ORDER BY email
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            # 获取所有浏览器窗口
            browsers = get_browser_list(page=0, pageSize=1000)
            
            # 创建 email -> browser_id 的映射
            email_to_browser = {}
            for browser in browsers:
                remark = browser.get('remark', '')
                # remark 格式: email----password----backup----secret
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
                
                # 从浏览器列表中查找对应的 browser_id
                browser_id = email_to_browser.get(email, '')
                
                if not browser_id:
                    self.log(f"⚠️ 账号 {email} 没有找到对应的浏览器窗口，跳过")
                    continue
                
                account = {
                    'email': email,
                    'password': row[1] or '',
                    'backup': row[2] or '',  # recovery_email 字段
                    'secret': row[3] or '',  # secret_key 字段
                    'link': row[4] or '',    # verification_link 字段
                    'browser_id': browser_id
                }
                self.accounts.append(account)
                
                # 添加到表格
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)
                
                # 复选框（默认选中）
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
            
            self.log(f"✅ 加载了 {len(self.accounts)} 个待绑卡账号")
            
        except Exception as e:
            self.log(f"❌ 加载账号失败: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_all(self):
        """刷新所有数据"""
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
        """获取选中的账号列表"""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    if row < len(self.accounts):
                        selected.append(self.accounts[row])
        return selected
    
    def start_binding(self):
        """开始绑卡订阅"""
        # 获取选中的账号
        selected_accounts = self.get_selected_accounts()
        
        if not selected_accounts:
            QMessageBox.warning(self, "提示", "请先勾选要处理的账号")
            return
        
        if not self.cards:
            QMessageBox.warning(self, "提示", "没有可用的卡片，请检查 cards.txt")
            return
        
        # 收集延迟设置
        delays = {
            'after_offer': self.delay_after_offer.value(),
            'after_add_card': self.delay_after_add_card.value(),
            'after_save': self.delay_after_save.value()
        }
        
        cards_per_account = self.cards_per_account_spin.value()
        thread_count = self.thread_count_spin.value()
        
        self.log(f"\n{'='*50}")
        self.log(f"开始批量绑卡订阅")
        self.log(f"选中账号数量: {len(selected_accounts)}")
        self.log(f"卡片数量: {len(self.cards)}")
        self.log(f"一卡几绑: {cards_per_account}")
        self.log(f"并发数: {thread_count}")
        self.log(f"延迟设置: Offer后{delays['after_offer']}秒, AddCard后{delays['after_add_card']}秒, Save后{delays['after_save']}秒")
        self.log(f"{'='*50}\n")
        
        # 创建并启动工作线程（使用选中的账号）
        self.worker = BindCardWorker(
            selected_accounts,
            self.cards,
            cards_per_account,
            delays,
            thread_count  # 添加并发数参数
        )
        self.worker.progress_signal.connect(self.update_account_status)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_refresh.setEnabled(False)
    
    def stop_binding(self):
        """停止绑卡"""
        if self.worker:
            self.worker.stop()
            self.log("⚠️ 正在停止...")
    
    def on_finished(self):
        """绑卡完成"""
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_refresh.setEnabled(True)
        self.log("\n✅ 批量绑卡订阅任务完成！")
        QMessageBox.information(self, "完成", "批量绑卡订阅任务已完成")
    
    def update_account_status(self, browser_id, status, message):
        """更新表格中的账号状态"""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 2) and self.table.item(row, 2).text() == browser_id:
                self.table.setItem(row, 3, QTableWidgetItem(status))
                self.table.setItem(row, 4, QTableWidgetItem(message))
                break
    
    def log(self, message):
        """添加日志"""
        self.log_text.append(message)
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    app = QApplication(sys.argv)
    window = BindCardWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
