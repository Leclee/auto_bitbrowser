"""
@file main_window.py
@brief 主窗口框架
@details 多业务管理系统的主窗口，支持Google、Microsoft、Facebook、Telegram等多个业务专区
"""

import sys
import os
import time

# 确保src目录在路径中（支持直接运行）
_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_current_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QMessageBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QSplitter,
    QAbstractItemView, QSpinBox, QToolBox, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon

# 使用绝对导入（支持直接运行和作为模块导入）
try:
    from gui.base_window import resource_path, get_data_path
except ImportError:
    from base_window import resource_path, get_data_path


class MainWindow(QMainWindow):
    """
    @brief 主窗口框架类
    @details 提供多业务管理的主界面框架，包含：
    - 左侧功能工具箱（按业务分区）
    - 中间控制面板和浏览器列表
    - 右侧运行状态日志
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("比特浏览器窗口管理工具")
        self.resize(1300, 800)
        
        # 任务控制标志
        self._stop_flag = False
        
        # 设置窗口图标
        self._set_icon()
        
        # 初始化数据库
        self._init_database()
        
        # 初始化UI
        self._init_function_panel()
        self._init_ui()
        
        # 加载初始数据
        QTimer.singleShot(100, self._on_startup)
    
    def _set_icon(self):
        """设置窗口图标"""
        try:
            icon_path = resource_path("beta-1.svg")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
    
    def _init_database(self):
        """初始化数据库"""
        try:
            from core.database import DBManager
            DBManager.init_db()
        except ImportError:
            try:
                _legacy_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_legacy')
                if _legacy_dir not in sys.path:
                    sys.path.insert(0, _legacy_dir)
                from database import DBManager
                DBManager.init_db()
            except Exception as e:
                print(f"[警告] 数据库初始化失败: {e}")
    
    def _init_function_panel(self):
        """初始化左侧功能工具箱"""
        self.function_panel = QWidget()
        self.function_panel.setFixedWidth(250)
        self.function_panel.setVisible(False)  # 默认隐藏
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.function_panel.setLayout(layout)
        
        # 标题
        title = QLabel("🔥 功能工具箱")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(title)
        
        # 分区工具箱
        self.toolbox = QToolBox()
        self.toolbox.setStyleSheet("""
            QToolBox::tab {
                background: #e1e1e1;
                border-radius: 5px;
                color: #555;
                font-weight: bold;
            }
            QToolBox::tab:selected {
                background: #d0d0d0;
                color: black;
            }
        """)
        layout.addWidget(self.toolbox)
        
        # --- Google 专区 ---
        google_page = self._create_google_panel()
        self.toolbox.addItem(google_page, "Google 专区")
        
        # --- Microsoft 专区 ---
        ms_page = self._create_microsoft_panel()
        self.toolbox.addItem(ms_page, "Microsoft 专区")
        
        # --- Facebook 专区 ---
        fb_page = self._create_facebook_panel()
        self.toolbox.addItem(fb_page, "Facebook 专区")
        
        # --- Telegram 专区 ---
        tg_page = self._create_telegram_panel()
        self.toolbox.addItem(tg_page, "Telegram 专区")
        
        # 默认展开Google
        self.toolbox.setCurrentIndex(0)
    
    def _create_google_panel(self) -> QWidget:
        """创建Google专区面板"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 10, 5, 10)
        
        # 一键获取SheerLink
        btn_sheerlink = QPushButton("一键获取 G-SheerLink")
        btn_sheerlink.setFixedHeight(40)
        btn_sheerlink.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sheerlink.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #4CAF50;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        btn_sheerlink.clicked.connect(self._action_get_sheerlink)
        layout.addWidget(btn_sheerlink)
        
        # 批量验证SheerID
        btn_verify = QPushButton("批量验证 SheerID Link")
        btn_verify.setFixedHeight(40)
        btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_verify.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #2196F3;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        btn_verify.clicked.connect(self._action_verify_sheerid)
        layout.addWidget(btn_verify)
        
        # 一键绑卡订阅
        btn_bind = QPushButton("🔗 一键绑卡订阅")
        btn_bind.setFixedHeight(40)
        btn_bind.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bind.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #FF9800;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        btn_bind.clicked.connect(self._action_bind_card)
        layout.addWidget(btn_bind)
        
        # 一键全自动处理
        btn_auto = QPushButton("🚀 一键全自动处理")
        btn_auto.setFixedHeight(40)
        btn_auto.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_auto.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #9C27B0;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        btn_auto.clicked.connect(self._action_auto_all)
        layout.addWidget(btn_auto)
        
        layout.addStretch()
        page.setLayout(layout)
        return page
    
    def _create_microsoft_panel(self) -> QWidget:
        """创建Microsoft专区面板"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 10, 5, 10)
        
        label = QLabel("🔧 功能开发中...")
        label.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(label)
        
        layout.addStretch()
        page.setLayout(layout)
        return page
    
    def _create_facebook_panel(self) -> QWidget:
        """创建Facebook专区面板"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 10, 5, 10)
        
        label = QLabel("🔧 功能开发中...")
        label.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(label)
        
        layout.addStretch()
        page.setLayout(layout)
        return page
    
    def _create_telegram_panel(self) -> QWidget:
        """创建Telegram专区面板"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 10, 5, 10)
        
        label = QLabel("🔧 功能开发中...")
        label.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(label)
        
        layout.addStretch()
        page.setLayout(layout)
        return page
    
    def _init_ui(self):
        """初始化主界面UI"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setSpacing(5)
        main_widget.setLayout(main_layout)
        
        # 1. 左侧功能面板
        main_layout.addWidget(self.function_panel)
        
        # 2. 中间区域（控制面板 + 浏览器列表）
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        # 顶部栏
        top_bar = self._create_top_bar()
        left_layout.addLayout(top_bar)
        
        # 创建参数配置
        config_group = self._create_config_group()
        left_layout.addWidget(config_group)
        
        # 操作按钮
        action_buttons = self._create_action_buttons()
        left_layout.addLayout(action_buttons)
        
        # 浏览器列表
        browser_group = self._create_browser_list_group()
        left_layout.addWidget(browser_group)
        
        # 3. 右侧日志区域
        right_widget = self._create_log_panel()
        
        # 使用分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
    
    def _create_top_bar(self) -> QHBoxLayout:
        """创建顶部栏"""
        layout = QHBoxLayout()
        
        # 工具箱切换按钮
        self.btn_toggle_tools = QPushButton("工具箱 📂")
        self.btn_toggle_tools.setCheckable(True)
        self.btn_toggle_tools.setChecked(False)
        self.btn_toggle_tools.setFixedHeight(30)
        self.btn_toggle_tools.setStyleSheet("""
            QPushButton { background-color: #607D8B; color: white; border-radius: 4px; padding: 5px 10px; }
            QPushButton:checked { background-color: #455A64; }
        """)
        self.btn_toggle_tools.clicked.connect(lambda checked: self.function_panel.setVisible(checked))
        layout.addWidget(self.btn_toggle_tools)
        
        # 标题
        title_label = QLabel("控制面板")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setContentsMargins(10, 0, 10, 0)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Web服务器按钮
        self.btn_web_server = QPushButton("🌐 启动Web服务器")
        self.btn_web_server.setFixedHeight(30)
        self.btn_web_server.setStyleSheet("""
            QPushButton { background-color: #9C27B0; color: white; border-radius: 4px; padding: 5px 10px; }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        self.btn_web_server.clicked.connect(self._toggle_web_server)
        layout.addWidget(self.btn_web_server)
        
        # 全局并发数
        layout.addWidget(QLabel("🔥 全局并发数:"))
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 50)
        self.thread_spinbox.setValue(1)
        self.thread_spinbox.setFixedSize(70, 30)
        self.thread_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thread_spinbox.setStyleSheet("font-size: 14px; font-weight: bold; color: #E91E63;")
        layout.addWidget(self.thread_spinbox)
        
        return layout
    
    def _toggle_web_server(self):
        """启动/停止Web服务器"""
        try:
            from main import start_web_server, stop_web_server, is_web_server_running
        except ImportError:
            self.log("⚠️ 无法导入Web服务器模块")
            return
        
        if is_web_server_running():
            stop_web_server()
            self.btn_web_server.setText("🌐 启动Web服务器")
            self.btn_web_server.setStyleSheet("""
                QPushButton { background-color: #9C27B0; color: white; border-radius: 4px; padding: 5px 10px; }
                QPushButton:hover { background-color: #7B1FA2; }
            """)
            self.log("🌐 Web服务器已停止")
        else:
            if start_web_server(8080):
                self.btn_web_server.setText("🔴 停止Web服务器")
                self.btn_web_server.setStyleSheet("""
                    QPushButton { background-color: #f44336; color: white; border-radius: 4px; padding: 5px 10px; }
                    QPushButton:hover { background-color: #d32f2f; }
                """)
                self.log("🌐 Web服务器已启动: http://localhost:8080")
            else:
                self.log("⚠️ Web服务器启动失败")
    
    def _create_config_group(self) -> QGroupBox:
        """创建参数配置区"""
        group = QGroupBox("创建参数配置")
        layout = QVBoxLayout()
        
        # 模板窗口ID
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("模板窗口ID:"))
        self.template_input = QLineEdit()
        self.template_input.setPlaceholderText("请输入模板窗口ID")
        row1.addWidget(self.template_input)
        layout.addLayout(row1)
        
        # 窗口前缀
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("窗口前缀:"))
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("可选，默认按模板名或'默认模板'命名")
        row2.addWidget(self.prefix_input)
        layout.addLayout(row2)
        
        # 平台URL
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("平台URL:"))
        self.platform_input = QLineEdit()
        self.platform_input.setPlaceholderText("可选，平台URL")
        row3.addWidget(self.platform_input)
        layout.addLayout(row3)
        
        # 额外URL
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("额外URL:"))
        self.extra_url_input = QLineEdit()
        self.extra_url_input.setPlaceholderText("可选，逗号分隔")
        row4.addWidget(self.extra_url_input)
        layout.addLayout(row4)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        self.stats_accounts = QLabel("📋 待创建窗口账号: 0")
        self.stats_proxies = QLabel("📡 可用代理: 0")
        stats_layout.addWidget(self.stats_accounts)
        stats_layout.addWidget(self.stats_proxies)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self) -> QHBoxLayout:
        """创建操作按钮"""
        layout = QHBoxLayout()
        
        # 开始创建（模板）
        self.btn_create_template = QPushButton("开始根据模板创建窗口")
        self.btn_create_template.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        self.btn_create_template.clicked.connect(self._start_creation_template)
        layout.addWidget(self.btn_create_template)
        
        # 使用默认模板创建
        self.btn_create_default = QPushButton("使用默认模板创建")
        self.btn_create_default.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.btn_create_default.clicked.connect(self._start_creation_default)
        layout.addWidget(self.btn_create_default)
        
        # 停止
        self.btn_stop = QPushButton("停止任务")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_task)
        layout.addWidget(self.btn_stop)
        
        return layout
    
    def _create_browser_list_group(self) -> QGroupBox:
        """创建浏览器列表区域"""
        group = QGroupBox("现有窗口列表")
        layout = QVBoxLayout()
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.btn_refresh = QPushButton("刷新列表")
        self.btn_refresh.clicked.connect(self._refresh_browser_list)
        toolbar.addWidget(self.btn_refresh)
        
        self.btn_refresh_2fa = QPushButton("刷新并保存验证码")
        self.btn_refresh_2fa.clicked.connect(self._refresh_2fa)
        toolbar.addWidget(self.btn_refresh_2fa)
        
        self.cb_select_all = QCheckBox("全选")
        self.cb_select_all.stateChanged.connect(self._toggle_select_all)
        toolbar.addWidget(self.cb_select_all)
        
        toolbar.addStretch()
        
        self.btn_open = QPushButton("打开选中窗口")
        self.btn_open.setStyleSheet("color: #2196F3;")
        self.btn_open.clicked.connect(self._open_selected_browsers)
        toolbar.addWidget(self.btn_open)
        
        self.btn_delete = QPushButton("删除选中窗口")
        self.btn_delete.setStyleSheet("color: #f44336;")
        self.btn_delete.clicked.connect(self._delete_selected_browsers)
        toolbar.addWidget(self.btn_delete)
        
        layout.addLayout(toolbar)
        
        # 浏览器表格
        self.browser_table = QTableWidget()
        self.browser_table.setColumnCount(6)
        self.browser_table.setHorizontalHeaderLabels(["选择", "序号", "名称", "窗口ID", "状态", "备注"])
        
        # 设置列宽可拖动（Interactive模式）
        header = self.browser_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # 设置初始列宽
        self.browser_table.setColumnWidth(0, 40)   # 选择
        self.browser_table.setColumnWidth(1, 50)   # 序号
        self.browser_table.setColumnWidth(2, 120)  # 名称
        self.browser_table.setColumnWidth(3, 280)  # 窗口ID
        self.browser_table.setColumnWidth(4, 100)  # 状态
        self.browser_table.setColumnWidth(5, 200)  # 备注
        
        # 最后一列自动拉伸填充剩余空间
        header.setStretchLastSection(True)
        
        self.browser_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.browser_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)  # 禁用选中效果
        self.browser_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 禁用焦点框
        self.browser_table.setAlternatingRowColors(True)  # 隔行变色
        layout.addWidget(self.browser_table)
        
        group.setLayout(layout)
        return group
    
    def _create_log_panel(self) -> QWidget:
        """创建日志面板"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 标题
        title = QLabel("运行状态日志")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumWidth(200)
        self.log_text.setStyleSheet("background-color: #ffffff; color: #333333; font-family: Consolas; border: 1px solid #ccc;")
        layout.addWidget(self.log_text)
        
        # 清除日志按钮
        btn_clear = QPushButton("清除日志")
        btn_clear.clicked.connect(lambda: self.log_text.clear())
        layout.addWidget(btn_clear)
        
        return widget
    
    # ==================== 事件处理 ====================
    
    def _on_startup(self):
        """启动时执行"""
        self._refresh_browser_list()
        self._check_files()
    
    def _check_files(self):
        """检查数据库状态"""
        try:
            from core.database import DBManager
            accounts = DBManager.get_accounts_without_browser()
            proxies = DBManager.get_available_proxies()
            self.stats_accounts.setText(f"📋 待创建窗口账号: {len(accounts)}")
            self.stats_proxies.setText(f"📡 可用代理: {len(proxies)}")
        except Exception as e:
            self.log(f"检查数据库状态失败: {e}")
    
    def log(self, message: str):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _refresh_browser_list(self):
        """刷新浏览器列表"""
        self.log("正在刷新窗口列表...")
        try:
            from core.bit_api import get_browser_list_simple
            from core.database import DBManager
            
            browsers = get_browser_list_simple(page=0, page_size=1000)
            
            # 获取所有账号状态
            accounts = {acc['browser_id']: acc for acc in DBManager.get_all_accounts() if acc.get('browser_id')}
            
            self.browser_table.setRowCount(0)
            
            # 状态显示映射
            status_display = {
                'pending_check': '❔待检测',
                'not_logged_in': '🔒未登录',
                'ineligible': '❌无资格',
                'link_ready': '🔗待验证',
                'verified': '✅已验证',
                'subscribed': '👑已订阅',
                'subscribed_antigravity': '🌟已解锁',
                'error': '⚠️错误',
            }
            
            for browser in browsers:
                name = browser.get('name', '')
                browser_id = browser.get('id', '')
                remark = browser.get('remark', '')
                seq = browser.get('seq', '')
                
                # 获取状态
                account = accounts.get(browser_id, {})
                status_code = account.get('status', 'pending_check')
                status_text = status_display.get(status_code, status_code)
                
                row = self.browser_table.rowCount()
                self.browser_table.insertRow(row)
                
                # 复选框
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                self.browser_table.setItem(row, 0, chk_item)
                
                self.browser_table.setItem(row, 1, QTableWidgetItem(str(seq)))
                self.browser_table.setItem(row, 2, QTableWidgetItem(name))
                self.browser_table.setItem(row, 3, QTableWidgetItem(browser_id))
                self.browser_table.setItem(row, 4, QTableWidgetItem(status_text))
                self.browser_table.setItem(row, 5, QTableWidgetItem(remark[:80] + '...' if len(remark) > 80 else remark))
            
            self.log(f"列表刷新完成，共 {len(browsers)} 个窗口")
            
        except Exception as e:
            self.log(f"刷新列表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _refresh_2fa(self):
        """刷新并保存2FA验证码到文件"""
        self.log("正在刷新2FA验证码...")
        
        try:
            import pyotp
            from core.bit_api import get_browser_list_simple
            
            browsers = get_browser_list_simple(page=0, page_size=1000)
            
            # 收集2FA信息
            twofa_data = []
            for browser in browsers:
                name = browser.get('name', '')
                remark = browser.get('remark', '')
                
                if '----' in remark:
                    parts = remark.split('----')
                    email = parts[0] if len(parts) > 0 else ''
                    secret = parts[3].strip() if len(parts) >= 4 else ''
                    
                    if secret:
                        try:
                            totp = pyotp.TOTP(secret.replace(' ', ''))
                            code = totp.now()
                            twofa_data.append({
                                'name': name,
                                'email': email,
                                'secret': secret,
                                'code': code
                            })
                        except:
                            pass
            
            if not twofa_data:
                self.log("没有找到2FA验证码数据")
                return
            
            # 保存到文件
            import os
            from datetime import datetime
            
            # 获取数据目录
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
            os.makedirs(data_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(data_dir, f'2fa_codes_{timestamp}.txt')
            
            # 写入文件
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# 2FA验证码 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 共 {len(twofa_data)} 个账号\n\n")
                for item in twofa_data:
                    f.write(f"{item['name']}\t{item['email']}\t{item['code']}\t{item['secret']}\n")
            
            # 同时更新表格中的2FA列
            self._refresh_browser_list()
            
            self.log(f"✅ 已保存 {len(twofa_data)} 个2FA验证码到: {filename}")
            QMessageBox.information(self, "完成", f"已保存 {len(twofa_data)} 个2FA验证码\n文件: {os.path.basename(filename)}")
            
        except Exception as e:
            self.log(f"刷新2FA失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _toggle_select_all(self, state):
        """全选/取消全选"""
        is_checked = (state == Qt.CheckState.Checked.value)
        for row in range(self.browser_table.rowCount()):
            item = self.browser_table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
    
    def _open_selected_browsers(self):
        """打开选中的浏览器"""
        selected_ids = self._get_selected_browser_ids()
        if not selected_ids:
            QMessageBox.information(self, "提示", "请先选择要打开的窗口")
            return
        
        self.log(f"正在打开 {len(selected_ids)} 个窗口...")
        
        from core.bit_api import open_browsers_batch
        
        def on_open(browser_id, success, message):
            if success:
                self.log(f"  ✅ 打开成功: {browser_id[:16]}...")
            else:
                self.log(f"  ❌ 打开失败: {message}")
            QApplication.processEvents()
        
        success_count, total = open_browsers_batch(selected_ids, callback=on_open)
        self.log(f"打开完成，成功 {success_count}/{total} 个")
    
    def _delete_selected_browsers(self):
        """删除选中的浏览器"""
        selected_ids = self._get_selected_browser_ids()
        if not selected_ids:
            QMessageBox.information(self, "提示", "请先选择要删除的窗口")
            return
        
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除选中的 {len(selected_ids)} 个窗口吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"正在删除 {len(selected_ids)} 个窗口...")
        
        from core.bit_api import delete_browsers_batch
        from core.database import DBManager
        
        def on_delete(browser_id, success, message):
            if success:
                self.log(f"  ✅ 删除成功: {browser_id[:16]}...")
                # 清除数据库中对应账号的browser_id
                try:
                    accounts = DBManager.get_all_accounts()
                    for acc in accounts:
                        if acc.get('browser_id') == browser_id:
                            DBManager.update_account_browser_id(acc['email'], '')
                            break
                except:
                    pass
            else:
                self.log(f"  ❌ 删除失败: {message}")
            QApplication.processEvents()
        
        success_count, total = delete_browsers_batch(selected_ids, callback=on_delete)
        self.log(f"删除完成，成功 {success_count}/{total} 个")
        self._refresh_browser_list()
        self._check_files()
    
    def _get_selected_browser_ids(self) -> list:
        """获取选中的浏览器ID列表"""
        selected = []
        for row in range(self.browser_table.rowCount()):
            chk_item = self.browser_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                id_item = self.browser_table.item(row, 3)  # 窗口ID在第4列
                if id_item:
                    selected.append(id_item.text())
        return selected

    
    def _start_creation_template(self):
        """使用模板创建窗口"""
        template_id = self.template_input.text().strip()
        if not template_id:
            QMessageBox.warning(self, "提示", "请输入模板窗口ID")
            return
        self.log(f"开始使用模板 {template_id} 创建窗口...")
        self._do_create_windows(template_id=template_id)
    
    def _start_creation_default(self):
        """使用默认模板创建窗口"""
        self.log("开始使用默认模板创建窗口...")
        self._do_create_windows(template_id=None)
    
    def _do_create_windows(self, template_id: str = None):
        """执行创建窗口"""
        try:
            from core.database import DBManager
            from core.bit_api import create_browsers_batch, get_browser_info
            
            # 获取待创建窗口的账号
            accounts = DBManager.get_accounts_without_browser()
            if not accounts:
                QMessageBox.information(self, "提示", "没有待创建窗口的账号")
                return
            
            # 获取可用代理
            proxies_db = DBManager.get_available_proxies()
            proxies = [
                {
                    'type': p.get('proxy_type', 'socks5'),
                    'host': p.get('host', ''),
                    'port': str(p.get('port', '')),
                    'username': p.get('username', ''),
                    'password': p.get('password', '')
                }
                for p in proxies_db
            ] if proxies_db else None
            
            # 禁用按钮
            self.btn_create_template.setEnabled(False)
            self.btn_create_default.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self._stop_flag = False
            
            # 获取配置
            prefix = self.prefix_input.text().strip() or "默认模板"
            platform_url = self.platform_input.text().strip()
            extra_url = self.extra_url_input.text().strip()
            
            # 如果使用模板ID，获取模板信息推断前缀
            if template_id and not self.prefix_input.text().strip():
                template_info = get_browser_info(template_id)
                if template_info:
                    ref_name = template_info.get('name', '')
                    if ref_name:
                        if '_' in ref_name:
                            prefix = '_'.join(ref_name.split('_')[:-1])
                        else:
                            prefix = ref_name
            
            self.log(f"准备创建 {len(accounts)} 个窗口，前缀: {prefix}")
            
            # 转换账号格式
            accounts_list = [
                {
                    'email': acc.get('email', ''),
                    'password': acc.get('password', ''),
                    'backup_email': acc.get('recovery_email', ''),
                    '2fa_secret': acc.get('secret_key', '')
                }
                for acc in accounts
            ]
            
            created_count = 0
            
            def on_create(index, account, browser_id, error):
                nonlocal created_count
                email = account.get('email', '')
                if browser_id:
                    self.log(f"  [{index+1}/{len(accounts)}] ✅ {email} -> {browser_id}")
                    DBManager.update_account_browser_id(email, browser_id)
                    created_count += 1
                else:
                    self.log(f"  [{index+1}/{len(accounts)}] ❌ {email}: {error}")
                QApplication.processEvents()
            
            def stop_check():
                return self._stop_flag
            
            # 批量创建
            success, total = create_browsers_batch(
                accounts=accounts_list,
                name_prefix=prefix,
                template_id=template_id,
                proxies=proxies,
                platform_url=platform_url,
                extra_url=extra_url,
                callback=on_create,
                stop_check=stop_check
            )
            
            if self._stop_flag:
                self.log(f"\n⚠️ 任务已停止")
            
            self.log(f"\n创建完成，成功 {created_count}/{total} 个")
            self._refresh_browser_list()
            self._check_files()
            
        except Exception as e:
            self.log(f"创建窗口失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 恢复按钮状态
            self.btn_create_template.setEnabled(True)
            self.btn_create_default.setEnabled(True)
            self.btn_stop.setEnabled(False)

    
    def _stop_task(self):
        """停止当前任务"""
        self._stop_flag = True
        self.log("⚠️ 正在停止任务...")
        
        # 停止工作线程（如果存在）
        if hasattr(self, '_worker') and self._worker is not None:
            self._worker.stop()
        
        self.btn_stop.setEnabled(False)
    
    # ==================== Google专区功能 ====================
    
    def _action_get_sheerlink(self):
        """一键获取SheerLink"""
        selected_ids = self._get_selected_browser_ids()
        if not selected_ids:
            QMessageBox.warning(self, "提示", "请先在列表中勾选要处理的窗口")
            return
        
        # 获取全局并发数
        thread_count = self.thread_spinbox.value()
        
        msg = f"确定要对选中的 {len(selected_ids)} 个窗口执行 SheerID 提取吗？\n"
        msg += f"当前并发模式: {thread_count} 线程\n"
        if thread_count > 1:
            msg += "⚠️ 注意: 将同时打开多个浏览器窗口，请确保电脑资源充足。"
        
        reply = QMessageBox.question(
            self, '确认操作', msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"\n开始提取SheerLink，共 {len(selected_ids)} 个窗口，并发: {thread_count}...")
        
        # 禁用按钮
        self._stop_flag = False
        self.btn_stop.setEnabled(True)
        
        # 使用工作线程避免阻塞主界面
        from gui.worker_thread import WorkerThread
        
        self._worker = WorkerThread('sheerlink', ids=selected_ids, thread_count=thread_count)
        self._worker.log_signal.connect(self.log)
        self._worker.finished_signal.connect(self._on_sheerlink_finished)
        self._worker.start()
    
    def _on_sheerlink_finished(self, result: dict):
        """SheerLink任务完成回调"""
        self.btn_stop.setEnabled(False)
        self._refresh_browser_list()
        
        if self._stop_flag:
            self.log("\n⚠️ 任务已被用户停止")
        else:
            self.log(f"\n✅ SheerLink提取完成，成功 {result.get('count', 0)} 个")


    
    def _action_verify_sheerid(self):
        """批量验证SheerID Link"""
        selected_ids = self._get_selected_browser_ids()
        if not selected_ids:
            QMessageBox.warning(self, "提示", "请先在列表中勾选要处理的窗口")
            return
        
        # 弹出输入API Key对话框
        api_key, ok = QInputDialog.getText(
            self, "SheerID API Key", 
            "请输入SheerID验证API Key:\n(从 batch.1key.me 获取)",
            QLineEdit.EchoMode.Normal, ""
        )
        
        if not ok or not api_key.strip():
            QMessageBox.warning(self, "提示", "未输入API Key")
            return
        
        # 获取验证ID列表 (从数据库获取sheerid_link)
        verification_ids = []
        try:
            from core.database import DBManager
            for bid in selected_ids:
                link = DBManager.get_sheerid_link_by_browser(bid)
                if link:
                    import re
                    match = re.search(r'verificationId=([a-f0-9]+)', link)
                    if match:
                        verification_ids.append(match.group(1))
        except Exception as e:
            self.log(f"获取验证ID失败: {e}")
        
        if not verification_ids:
            QMessageBox.warning(self, "提示", "未找到可验证的SheerID链接\n请先执行'一键获取G-SheerLink'")
            return
        
        msg = f"确定要验证 {len(verification_ids)} 个SheerID链接吗？"
        reply = QMessageBox.question(
            self, '确认操作', msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"\n开始验证SheerID，共 {len(verification_ids)} 个...")
        
        self._stop_flag = False
        self.btn_stop.setEnabled(True)
        
        from gui.worker_thread import WorkerThread
        self._worker = WorkerThread('verify_sheerid', ids=verification_ids, api_key=api_key.strip())
        self._worker.log_signal.connect(self.log)
        self._worker.finished_signal.connect(self._on_task_finished)
        self._worker.start()
    
    def _action_bind_card(self):
        """一键绑卡订阅"""
        selected_ids = self._get_selected_browser_ids()
        if not selected_ids:
            QMessageBox.warning(self, "提示", "请先在列表中勾选要处理的窗口")
            return
        
        thread_count = self.thread_spinbox.value()
        
        msg = f"确定要对选中的 {len(selected_ids)} 个窗口执行绑卡订阅吗？\n"
        msg += f"当前并发模式: {thread_count} 线程\n"
        msg += "将使用默认测试卡进行绑定和订阅。"
        
        reply = QMessageBox.question(
            self, '确认操作', msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"\n开始绑卡订阅，共 {len(selected_ids)} 个窗口，并发: {thread_count}...")
        
        self._stop_flag = False
        self.btn_stop.setEnabled(True)
        
        from gui.worker_thread import WorkerThread
        self._worker = WorkerThread('bind_card', ids=selected_ids, thread_count=thread_count)
        self._worker.log_signal.connect(self.log)
        self._worker.finished_signal.connect(self._on_task_finished)
        self._worker.start()
    
    def _action_auto_all(self):
        """一键全自动处理"""
        selected_ids = self._get_selected_browser_ids()
        if not selected_ids:
            QMessageBox.warning(self, "提示", "请先在列表中勾选要处理的窗口")
            return
        
        thread_count = self.thread_spinbox.value()
        
        # 可选输入API Key
        api_key, ok = QInputDialog.getText(
            self, "SheerID API Key (可选)", 
            "请输入SheerID验证API Key:\n(留空则跳过验证步骤)",
            QLineEdit.EchoMode.Normal, ""
        )
        
        msg = f"确定要对选中的 {len(selected_ids)} 个窗口执行全自动处理吗？\n"
        msg += f"当前并发模式: {thread_count} 线程\n"
        msg += "流程: 提取SheerLink → 验证SheerID → 绑卡订阅"
        
        reply = QMessageBox.question(
            self, '确认操作', msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"\n开始全自动处理，共 {len(selected_ids)} 个窗口，并发: {thread_count}...")
        
        self._stop_flag = False
        self.btn_stop.setEnabled(True)
        
        from gui.worker_thread import WorkerThread
        self._worker = WorkerThread(
            'all_in_one', 
            ids=selected_ids, 
            thread_count=thread_count,
            api_key=api_key.strip() if api_key else ''
        )
        self._worker.log_signal.connect(self.log)
        self._worker.finished_signal.connect(self._on_task_finished)
        self._worker.start()
    
    def _on_task_finished(self, result: dict):
        """通用任务完成回调"""
        self.btn_stop.setEnabled(False)
        self._refresh_browser_list()
        
        task_type = result.get('type', '')
        count = result.get('count', 0)
        
        if self._stop_flag:
            self.log("\n⚠️ 任务已被用户停止")
        else:
            task_names = {
                'sheerlink': 'SheerLink提取',
                'verify_sheerid': 'SheerID验证',
                'bind_card': '绑卡订阅',
                'all_in_one': '全自动处理'
            }
            name = task_names.get(task_type, task_type)
            self.log(f"\n✅ {name}完成，成功 {count} 个")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
