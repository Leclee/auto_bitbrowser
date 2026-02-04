"""
@file __init__.py
@brief Web管理模块
@details 提供账号、代理、卡片的Web管理界面（通用模块，不限于特定业务）
"""

from .server import run_server, APIHandler
from .task_manager import (
    TaskManager,
    TaskStatus,
    start_sheerlink_task,
    start_bindcard_task,
    start_auto_process_task,
    get_task_status,
    stop_task,
)

__all__ = [
    'run_server', 
    'APIHandler',
    'TaskManager',
    'TaskStatus',
    'start_sheerlink_task',
    'start_bindcard_task',
    'start_auto_process_task',
    'get_task_status',
    'stop_task',
]
