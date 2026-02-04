"""
@file main.py
@brief 程序主入口
@details Auto_All_System_Pyqt 应用程序入口点
"""
import sys
import os
import threading

# 确保src目录在路径中
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# 确保_legacy目录也在路径中（兼容旧模块）
LEGACY_DIR = os.path.join(SRC_DIR, '_legacy')
if LEGACY_DIR not in sys.path:
    sys.path.insert(0, LEGACY_DIR)

# 初始化核心模块
try:
    from core.database import DBManager
except ImportError:
    from database import DBManager

DBManager.init_db()

# 全局Web服务器线程和httpd实例
_web_server_thread = None
_web_server_httpd = None


def start_web_server(port=8080):
    """
    @brief 在后台线程启动Web服务器
    @param port 服务器端口
    @return 是否成功启动
    """
    global _web_server_thread, _web_server_httpd
    
    if _web_server_thread and _web_server_thread.is_alive():
        print("[Web服务器] 已在运行中")
        return True
    
    def _run_server():
        global _web_server_httpd
        try:
            # 导入server模块
            import socketserver
            
            # 添加web目录到路径
            web_dir = os.path.join(SRC_DIR, 'web')
            if web_dir not in sys.path:
                sys.path.insert(0, web_dir)
            
            from web.server import APIHandler, TEMPLATE_DIR, STATIC_DIR
            
            # 确保目录存在
            os.makedirs(TEMPLATE_DIR, exist_ok=True)
            os.makedirs(os.path.join(STATIC_DIR, 'css'), exist_ok=True)
            os.makedirs(os.path.join(STATIC_DIR, 'js'), exist_ok=True)
            
            socketserver.TCPServer.allow_reuse_address = True
            _web_server_httpd = socketserver.TCPServer(("", port), APIHandler)
            
            print(f"╔══════════════════════════════════════════╗")
            print(f"║   🚀 Web Admin Server Started            ║")
            print(f"║   📍 http://localhost:{port:<5}              ║")
            print(f"╚══════════════════════════════════════════╝")
            
            _web_server_httpd.serve_forever()
            
        except Exception as e:
            print(f"[Web服务器] 启动失败: {e}")
            import traceback
            traceback.print_exc()
    
    try:
        _web_server_thread = threading.Thread(target=_run_server, daemon=True)
        _web_server_thread.start()
        
        # 等待一小段时间确保启动
        import time
        time.sleep(0.5)
        
        if _web_server_thread.is_alive():
            print(f"[Web服务器] 已启动，端口: {port}")
            return True
        else:
            print("[Web服务器] 启动失败")
            return False
        
    except Exception as e:
        print(f"[Web服务器] 启动失败: {e}")
        return False


def stop_web_server():
    """
    @brief 停止Web服务器
    """
    global _web_server_thread, _web_server_httpd
    
    if _web_server_httpd:
        try:
            _web_server_httpd.shutdown()
            print("[Web服务器] 已停止")
        except Exception as e:
            print(f"[Web服务器] 停止失败: {e}")
        _web_server_httpd = None
    _web_server_thread = None


def is_web_server_running():
    """
    @brief 检查Web服务器是否在运行
    @return 是否运行中
    """
    global _web_server_thread
    return _web_server_thread and _web_server_thread.is_alive()


def run_gui():
    """
    @brief 运行主GUI界面
    @details Web 服务器需要手动点击按钮启动
    """
    from PyQt6.QtWidgets import QApplication
    
    # 使用新的主窗口
    try:
        from gui.main_window import MainWindow
    except ImportError:
        # 回退到旧版
        try:
            from google.frontend import BrowserWindowCreatorGUI as MainWindow
        except ImportError:
            from create_window_gui import BrowserWindowCreatorGUI as MainWindow
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    # GUI 退出时停止 Web 服务器（如果有）
    exit_code = app.exec()
    if is_web_server_running():
        stop_web_server()
    sys.exit(exit_code)


def run_web_admin(port=8080):
    """
    @brief 运行Web管理界面
    @param port 服务器端口
    """
    try:
        from web.server import run_server
    except ImportError:
        try:
            from web_admin.server import run_server
        except ImportError:
            print("[警告] web_admin 模块导入失败: No module named 'web_admin'")
            return
    
    run_server(port)


def main():
    """
    @brief 主函数
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto All System PyQt')
    parser.add_argument('--web', action='store_true', help='启动Web管理界面')
    parser.add_argument('--port', type=int, default=8080, help='Web服务器端口')
    
    args = parser.parse_args()
    
    if args.web:
        run_web_admin(args.port)
    else:
        run_gui()


if __name__ == '__main__':
    main()


