"""
@file base_worker.py
@brief 基础工作线程类
@details 提供可复用的后台工作线程基类，支持日志信号、进度信号、停止控制等
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional, Callable
import time


class BaseWorker(QThread):
    """
    @class BaseWorker
    @brief 基础工作线程类
    @details 所有业务工作线程的基类，提供通用功能
    """
    
    # 日志信号
    log_signal = pyqtSignal(str)
    
    # 进度信号 (当前项, 总数, 消息)
    progress_signal = pyqtSignal(int, int, str)
    
    # 状态更新信号 (ID, 状态, 消息)
    status_signal = pyqtSignal(str, str, str)
    
    # 完成信号
    finished_signal = pyqtSignal()
    
    # 错误信号
    error_signal = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """
        @brief 初始化工作线程
        @param parent 父对象
        """
        super().__init__(parent)
        self._is_running = True
        self._is_paused = False
    
    @property
    def is_running(self) -> bool:
        """
        @brief 获取运行状态
        @return 是否正在运行
        """
        return self._is_running
    
    def stop(self):
        """
        @brief 停止工作线程
        """
        self._is_running = False
        self.log("正在停止任务...")
    
    def pause(self):
        """
        @brief 暂停工作线程
        """
        self._is_paused = True
        self.log("任务已暂停")
    
    def resume(self):
        """
        @brief 恢复工作线程
        """
        self._is_paused = False
        self.log("任务已恢复")
    
    def log(self, message: str):
        """
        @brief 发送日志信号
        @param message 日志消息
        """
        self.log_signal.emit(message)
    
    def update_progress(self, current: int, total: int, message: str = ""):
        """
        @brief 更新进度
        @param current 当前进度
        @param total 总数
        @param message 进度消息
        """
        self.progress_signal.emit(current, total, message)
    
    def update_status(self, item_id: str, status: str, message: str = ""):
        """
        @brief 更新项目状态
        @param item_id 项目ID
        @param status 状态
        @param message 状态消息
        """
        self.status_signal.emit(item_id, status, message)
    
    def msleep_interruptible(self, ms: int) -> bool:
        """
        @brief 可中断的睡眠
        @param ms 睡眠毫秒数
        @return 如果被中断返回False，否则返回True
        """
        interval = 100  # 每100ms检查一次
        elapsed = 0
        while elapsed < ms and self._is_running:
            # 处理暂停状态
            while self._is_paused and self._is_running:
                self.msleep(100)
            
            if not self._is_running:
                return False
            
            self.msleep(min(interval, ms - elapsed))
            elapsed += interval
        
        return self._is_running
    
    def run(self):
        """
        @brief 线程执行入口
        @details 子类需要重写此方法实现具体业务逻辑
        """
        raise NotImplementedError("子类必须实现run方法")
    
    def execute_with_retry(self, func: Callable, max_retries: int = 3, 
                           delay_ms: int = 1000, *args, **kwargs):
        """
        @brief 带重试的函数执行
        @param func 要执行的函数
        @param max_retries 最大重试次数
        @param delay_ms 重试间隔（毫秒）
        @param args 函数参数
        @param kwargs 函数关键字参数
        @return 函数执行结果
        """
        last_error = None
        for attempt in range(max_retries):
            if not self._is_running:
                return None
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                self.log(f"执行失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    if not self.msleep_interruptible(delay_ms):
                        return None
        
        raise last_error if last_error else Exception("未知错误")
