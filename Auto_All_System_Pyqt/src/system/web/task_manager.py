"""
@file task_manager.py
@brief Web 任务管理器
@details 提供通用的后台任务管理功能，支持 SheerLink 提取、绑卡、全自动处理等
"""
import threading
import time
import uuid
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field


# 全局任务状态存储
_tasks: Dict[str, 'TaskStatus'] = {}


@dataclass
class TaskStatus:
    """任务状态"""
    task_id: str
    task_type: str
    status: str = 'pending'  # pending, running, completed, stopped
    total: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    logs: List[Dict] = field(default_factory=list)
    results: List[Dict] = field(default_factory=list)
    stop_requested: bool = False
    start_time: float = 0
    end_time: float = 0
    
    def add_log(self, message: str, level: str = 'info'):
        """添加日志"""
        self.logs.append({
            'time': time.time(),
            'level': level,
            'message': message
        })
        # 限制日志数量
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]
    
    def add_result(self, item_id: str, success: bool, message: str):
        """添加结果"""
        self.processed += 1
        if success:
            self.success += 1
        else:
            self.failed += 1
        self.results.append({
            'item_id': item_id,
            'success': success,
            'message': message
        })
    
    def to_dict(self, include_all_logs: bool = False) -> Dict:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'status': self.status,
            'total': self.total,
            'processed': self.processed,
            'success_count': self.success,
            'failed_count': self.failed,
            'logs': self.logs if include_all_logs else self.logs[-20:],
            'results': self.results[-10:],
            'duration': (self.end_time or time.time()) - self.start_time if self.start_time else 0,
        }


class TaskManager:
    """任务管理器"""
    
    @staticmethod
    def create_task(task_type: str, total: int) -> TaskStatus:
        """创建任务"""
        task_id = f"{task_type}_{str(uuid.uuid4())[:8]}"
        task = TaskStatus(
            task_id=task_id,
            task_type=task_type,
            total=total,
            start_time=time.time()
        )
        _tasks[task_id] = task
        return task
    
    @staticmethod
    def get_task(task_id: str) -> Optional[TaskStatus]:
        """获取任务"""
        return _tasks.get(task_id)
    
    @staticmethod
    def stop_task(task_id: str) -> bool:
        """停止任务"""
        task = _tasks.get(task_id)
        if task:
            task.stop_requested = True
            return True
        return False
    
    @staticmethod
    def run_batch_task(
        task: TaskStatus,
        items: List[str],
        process_func: Callable,
        concurrency: int = 1,
        **kwargs
    ):
        """
        运行批量任务
        @param task 任务状态对象
        @param items 要处理的项目列表 (browser_ids)
        @param process_func 处理函数，签名: func(item_id, log_callback) -> (success, message)
        @param concurrency 并发数
        @param kwargs 传递给 process_func 的额外参数
        """
        def log_callback(msg: str):
            task.add_log(msg)
        
        def result_callback(item_id: str, success: bool, msg: str):
            task.add_result(item_id, success, msg)
        
        def stop_check() -> bool:
            return task.stop_requested
        
        def run():
            task.status = 'running'
            try:
                # 调用实际的批处理函数
                process_func(
                    items,
                    thread_count=concurrency,
                    callback=result_callback,
                    stop_check=stop_check,
                    log_callback=log_callback,
                    **kwargs
                )
            except Exception as e:
                task.add_log(f"任务异常: {e}", 'error')
            finally:
                task.status = 'stopped' if task.stop_requested else 'completed'
                task.end_time = time.time()
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return task


# ==================== 便捷函数 ====================

def start_sheerlink_task(browser_ids: List[str], concurrency: int = 1) -> TaskStatus:
    """启动 SheerLink 提取任务"""
    from google.backend.sheerlink_service import extract_sheerlink_batch
    
    task = TaskManager.create_task('sheerlink', len(browser_ids))
    TaskManager.run_batch_task(task, browser_ids, extract_sheerlink_batch, concurrency)
    return task


def start_bindcard_task(browser_ids: List[str], concurrency: int = 1) -> TaskStatus:
    """启动绑卡任务"""
    from google.backend.bind_card_service import process_bind_card_batch
    
    task = TaskManager.create_task('bindcard', len(browser_ids))
    TaskManager.run_batch_task(task, browser_ids, process_bind_card_batch, concurrency)
    return task


def start_auto_process_task(browser_ids: List[str], api_key: str = '', card_info: dict = None) -> Dict:
    """
    启动全自动处理任务
    注意: 全自动处理任务使用 all_in_one_service 自带的任务管理
    返回的是 Dict 而非 TaskStatus
    """
    from google.backend.all_in_one_service import start_batch_task
    
    task_id = f"auto_{str(uuid.uuid4())[:8]}"
    return start_batch_task(task_id, browser_ids, api_key, card_info)


def start_change_2fa_task(accounts: List[Dict], concurrency: int = 1) -> TaskStatus:
    """
    启动批量更改2FA任务
    @param accounts 账号列表 (包含 browser_id, email, password, twofa_key, recovery_email)
    @param concurrency 并发数
    """
    import asyncio
    from google.backend.change_2fa_service import process_change_2fa_batch
    
    task = TaskManager.create_task('change_2fa', len(accounts))
    
    def log_callback(msg: str):
        task.add_log(msg)
    
    def result_callback(result: Dict):
        task.add_result(
            result.get('email', 'unknown'),
            result.get('success', False),
            result.get('message', '')
        )
        # 额外存储新密钥信息
        if result.get('new_2fa_key'):
            task.results[-1]['new_2fa_key'] = result['new_2fa_key']
    
    def stop_check() -> bool:
        return task.stop_requested
    
    def run():
        task.status = 'running'
        try:
            # 运行异步批处理
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    process_change_2fa_batch(
                        accounts=accounts,
                        concurrency=concurrency,
                        log_callback=log_callback,
                        result_callback=result_callback,
                        stop_check=stop_check
                    )
                )
            finally:
                loop.close()
        except Exception as e:
            task.add_log(f"任务异常: {e}", 'error')
        finally:
            task.status = 'stopped' if task.stop_requested else 'completed'
            task.end_time = time.time()
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return task


def get_task_status(task_id: str) -> Optional[Dict]:
    """
    获取任务状态 (统一查询接口)
    自动识别任务类型并从对应的存储中获取
    """
    # 先查 task_manager 中的任务 (sheerlink, bindcard)
    task = TaskManager.get_task(task_id)
    if task:
        return task.to_dict()
    
    # 再查 all_in_one_service 中的任务 (auto)
    try:
        from google.backend.all_in_one_service import get_batch_task_status
        aio_status = get_batch_task_status(task_id)
        if aio_status:
            # 转换为统一格式
            return {
                'task_id': aio_status.get('task_id', task_id),
                'task_type': 'auto',
                'status': aio_status.get('status', 'unknown'),
                'total': aio_status.get('total', 0),
                'processed': aio_status.get('processed', 0),
                'success_count': sum([
                    aio_status.get('stats', {}).get('subscribed', 0),
                    aio_status.get('stats', {}).get('subscribed_antigravity', 0),
                    aio_status.get('stats', {}).get('verified', 0),
                ]),
                'failed_count': sum([
                    aio_status.get('stats', {}).get('ineligible', 0),
                    aio_status.get('stats', {}).get('error', 0),
                ]),
                'logs': aio_status.get('logs', [])[-20:],
                'results': aio_status.get('results', [])[-10:],
                'stats': aio_status.get('stats', {}),
                'current_step': aio_status.get('current_step', ''),
                'current_browser': aio_status.get('current_browser', ''),
            }
    except ImportError:
        pass
    
    return None


def stop_task(task_id: str) -> bool:
    """
    停止任务 (统一停止接口)
    自动识别任务类型并调用对应的停止方法
    """
    # 先尝试停止 task_manager 中的任务
    if TaskManager.stop_task(task_id):
        return True
    
    # 再尝试停止 all_in_one_service 中的任务
    try:
        from google.backend.all_in_one_service import stop_batch_task
        return stop_batch_task(task_id)
    except ImportError:
        pass
    
    return False
