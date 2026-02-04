"""
@file server.py
@brief Web Admin 服务器
@details 提供账号、代理、卡片的Web管理界面（支持多业务扩展）
"""
import http.server
import socketserver
import json
import os
import sys
import time
import urllib.parse
import webbrowser
import threading
from typing import Dict, Any, List

# 获取当前目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 添加src目录到路径
_src_dir = os.path.dirname(CURRENT_DIR)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# 导入核心模块
from core.database import DBManager

# 配置路径
PORT = 8080
TEMPLATE_DIR = os.path.join(CURRENT_DIR, 'templates')
STATIC_DIR = os.path.join(CURRENT_DIR, 'static')


class APIHandler(http.server.SimpleHTTPRequestHandler):
    """
    @class APIHandler
    @brief HTTP请求处理器
    @details 处理Web管理界面的所有HTTP请求，支持RESTful API
    """
    
    # 业务类型配置（可扩展）
    BUSINESS_TYPES = {
        'google': {'name': 'Google', 'icon': '🔵', 'color': '#4285f4'},
        'facebook': {'name': 'Facebook', 'icon': '🔷', 'color': '#1877f2'},
        'twitter': {'name': 'Twitter/X', 'icon': '⬛', 'color': '#000000'},
        'microsoft': {'name': 'Microsoft', 'icon': '🟦', 'color': '#00a4ef'},
        'apple': {'name': 'Apple', 'icon': '⚪', 'color': '#555555'},
    }
    
    def log_message(self, format, *args):
        """静默日志"""
        pass
    
    def send_json(self, data: Any, status: int = 200):
        """发送JSON响应"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str, ensure_ascii=False).encode('utf-8'))
    
    def send_html(self, file_path: str):
        """发送HTML文件"""
        if not os.path.exists(file_path):
            self.send_error(404, "Page not found")
            return
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())

    def send_static(self, file_path: str):
        """发送静态文件"""
        if not os.path.exists(file_path):
            self.send_error(404)
            return
        
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
        }
        
        self.send_response(200)
        self.send_header('Content-type', content_types.get(ext, 'application/octet-stream'))
        # 开发模式禁用缓存，确保每次都加载最新文件
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        """处理GET请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        # 页面路由
        if path == '/' or path == '/index.html':
            self.send_html(os.path.join(TEMPLATE_DIR, 'index.html'))
            return
        
        # 静态文件
        if path.startswith('/static/'):
            file_path = os.path.join(CURRENT_DIR, path[1:])
            self.send_static(file_path)
            return
        
        # ==================== 系统API ====================
        if path == '/api/system/info':
            self.send_json({
                'version': '2.0.0',
                'business_types': self.BUSINESS_TYPES
            })
            return
        
        if path == '/api/system/stats':
            stats = {
                'accounts': DBManager.get_accounts_count_by_status(),
                'total_accounts': len(DBManager.get_all_accounts()),
                'total_proxies': len(DBManager.get_all_proxies()),
                'available_proxies': len(DBManager.get_available_proxies()),
                'total_cards': len(DBManager.get_all_cards()),
                'available_cards': len(DBManager.get_available_cards()),
            }
            self.send_json(stats)
            return
        
        # ==================== 账号API ====================
        if path == '/api/accounts':
            status_filter = query.get('status', [None])[0]
            business_filter = query.get('business', [None])[0]
            
            if status_filter:
                accounts = DBManager.get_accounts_by_status(status_filter)
            else:
                accounts = DBManager.get_all_accounts()
            
            # TODO: 当数据库支持business字段后，添加业务过滤
            self.send_json({'data': accounts, 'total': len(accounts)})
            return
        
        if path == '/api/accounts/stats':
            stats = DBManager.get_accounts_count_by_status()
            self.send_json(stats)
            return
        
        # ==================== 代理API ====================
        if path == '/api/proxies':
            proxies = DBManager.get_all_proxies()
            self.send_json({'data': proxies, 'total': len(proxies)})
            return
        
        if path == '/api/proxies/available':
            proxies = DBManager.get_available_proxies()
            self.send_json({'data': proxies, 'total': len(proxies)})
            return
        
        # ==================== 卡片API ====================
        if path == '/api/cards':
            cards = DBManager.get_all_cards()
            self.send_json({'data': cards, 'total': len(cards)})
            return
        
        if path == '/api/cards/available':
            cards = DBManager.get_available_cards()
            self.send_json({'data': cards, 'total': len(cards)})
            return
        
        # ==================== 设置API ====================
        if path == '/api/settings':
            settings = DBManager.get_all_settings()
            self.send_json(settings)
            return
        
        # ==================== SheerID API ====================
        if path == '/api/sheerid/status':
            try:
                api_key = DBManager.get_setting('sheerid_api_key', '')
                if not api_key:
                    self.send_json({'success': False, 'error': '请先配置 API Key'})
                    return
                
                from google.backend.sheerid_verifier import SheerIDVerifier
                verifier = SheerIDVerifier(api_key)
                status = verifier.get_system_status()
                self.send_json({'success': True, 'data': status})
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # 获取待验证账号列表
        if path == '/api/accounts/link_ready':
            try:
                accounts = DBManager.get_accounts_by_status('link_ready')
                # 提取验证链接中的 verificationId
                result = []
                import re
                for acc in accounts:
                    link = acc.get('verification_link', '')
                    vid = ''
                    if link:
                        match = re.search(r'verificationId=([a-fA-F0-9]+)', link)
                        if match:
                            vid = match.group(1)
                    result.append({
                        'email': acc.get('email', ''),
                        'verification_link': link,
                        'verification_id': vid,
                        'status': acc.get('status', ''),
                        'updated_at': acc.get('updated_at', '')
                    })
                self.send_json({'success': True, 'data': result, 'total': len(result)})
            except Exception as e:
                self.send_json({'success': False, 'error': str(e), 'data': []})
            return
        
        # ==================== 日志API ====================
        if path == '/api/logs':
            limit = int(query.get('limit', [100])[0])
            logs = DBManager.get_recent_logs(limit)
            self.send_json({'data': logs, 'total': len(logs)})
            return

        self.send_error(404, "API not found")

    def do_POST(self):
        """处理POST请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            params = json.loads(body.decode('utf-8')) if body else {}
        except json.JSONDecodeError:
            self.send_json({'success': False, 'error': 'Invalid JSON'}, 400)
            return
        
        # ==================== 账号操作 ====================
        if path == '/api/accounts/import':
            text = params.get('text', '')
            status = params.get('status', 'pending_check')
            separator = params.get('separator', '----')
            # business = params.get('business', 'google')  # 预留业务类型
            
            if not text.strip():
                self.send_json({'success': False, 'error': '请输入账号数据'}, 400)
                return
            
            success, errors, details = DBManager.import_accounts_from_text(text, separator, status)
            self.send_json({
                'success': True,
                'imported': success,
                'failed': errors,
                'errors': details[:10]
            })
            return
        
        if path == '/api/accounts/update':
            email = params.get('email')
            updates = params.get('updates', {})
            
            if not email:
                self.send_json({'success': False, 'error': '缺少邮箱'}, 400)
                return
            
            DBManager.upsert_account(
                email,
                password=updates.get('password'),
                recovery_email=updates.get('recovery_email'),
                secret_key=updates.get('secret_key'),
                status=updates.get('status'),
                message=updates.get('message')
            )
            self.send_json({'success': True})
            return
        
        if path == '/api/accounts/delete':
            emails = params.get('emails', [])
            if isinstance(emails, str):
                emails = [emails]
            
            deleted = 0
            for email in emails:
                try:
                    DBManager.delete_account(email)
                    deleted += 1
                except Exception:
                    pass
            
            self.send_json({'success': True, 'deleted': deleted})
            return
        
        if path == '/api/accounts/batch-status':
            # 批量修改账号状态
            emails = params.get('emails', [])
            status = params.get('status', '')
            message = params.get('message', None)
            
            if not emails:
                self.send_json({'success': False, 'error': '请选择账号'}, 400)
                return
            
            if not status:
                self.send_json({'success': False, 'error': '请选择状态'}, 400)
                return
            
            # 验证状态值
            valid_statuses = ['pending_check', 'link_ready', 'verified', 'subscribed', 
                            'subscribed_antigravity', 'ineligible', 'error']
            if status not in valid_statuses:
                self.send_json({'success': False, 'error': f'无效的状态: {status}'}, 400)
                return
            
            updated = DBManager.batch_update_status(emails, status, message)
            self.send_json({'success': True, 'updated': updated})
            return
        
        if path == '/api/accounts/export':
            emails = set(params.get('emails', []))
            fields = params.get('fields', ['email', 'password', 'recovery_email', 'secret_key'])
            separator = params.get('separator', '----')
            status_filter = params.get('status', '')  # 状态筛选
            include_exported = params.get('include_exported', True)  # 是否包含已导出的账号
            mark_exported = params.get('mark_exported', False)  # 是否标记为已导出
            
            # 根据状态获取账号
            if status_filter:
                # 特殊处理：subscribed 同时包含 subscribed_antigravity
                if status_filter == 'subscribed':
                    statuses = ['subscribed', 'subscribed_antigravity']
                    accounts = DBManager.get_accounts_by_statuses(statuses, include_exported)
                else:
                    # 使用新方法支持 include_exported 参数
                    accounts = DBManager.get_accounts_by_statuses([status_filter], include_exported)
            else:
                accounts = DBManager.get_all_accounts()
                # 手动过滤已导出的账号
                if not include_exported:
                    accounts = [acc for acc in accounts if not acc.get('is_exported')]
            
            lines = []
            exported_emails = []
            
            for acc in accounts:
                if not emails or acc['email'] in emails:
                    parts = [str(acc.get(f) or '') for f in fields]
                    lines.append(separator.join(parts))
                    exported_emails.append(acc['email'])
            
            # 如果需要标记为已导出
            if mark_exported and exported_emails:
                DBManager.batch_update_exported(exported_emails, 1)
            
            self.send_json({'success': True, 'data': '\n'.join(lines), 'count': len(lines)})
            return
        
        if path == '/api/accounts/sync-browsers':
            try:
                DBManager.import_from_browsers()
                self.send_json({'success': True, 'message': '同步任务已启动'})
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)}, 500)
            return
        
        # ==================== 代理操作 ====================
        if path == '/api/proxies/import':
            text = params.get('text', '')
            proxy_type = params.get('type', 'socks5')
            
            if not text.strip():
                self.send_json({'success': False, 'error': '请输入代理数据'}, 400)
                return
            
            success, errors, details = DBManager.import_proxies_from_text(text, proxy_type)
            self.send_json({
                'success': True,
                'imported': success,
                'failed': errors,
                'errors': details[:10]
            })
            return
        
        if path == '/api/proxies/delete':
            ids = params.get('ids', [])
            if isinstance(ids, int):
                ids = [ids]
            
            deleted = 0
            for pid in ids:
                try:
                    DBManager.delete_proxy(pid)
                    deleted += 1
                except Exception:
                    pass
            
            self.send_json({'success': True, 'deleted': deleted})
            return
        
        if path == '/api/proxies/clear':
            DBManager.clear_all_proxies()
            self.send_json({'success': True})
            return
        
        # ==================== 卡片操作 ====================
        if path == '/api/cards/import':
            text = params.get('text', '')
            max_usage = params.get('max_usage', 1)
            
            if not text.strip():
                self.send_json({'success': False, 'error': '请输入卡片数据'}, 400)
                return
            
            success, errors, details = DBManager.import_cards_from_text(text, max_usage)
            self.send_json({
                'success': True,
                'imported': success,
                'failed': errors,
                'errors': details[:10]
            })
            return
        
        if path == '/api/cards/delete':
            ids = params.get('ids', [])
            if isinstance(ids, int):
                ids = [ids]
            
            deleted = 0
            for cid in ids:
                try:
                    DBManager.delete_card(cid)
                    deleted += 1
                except Exception:
                    pass
            
            self.send_json({'success': True, 'deleted': deleted})
            return
        
        if path == '/api/cards/toggle':
            card_id = params.get('id')
            is_active = params.get('active', True)
            
            if card_id:
                DBManager.set_card_active(card_id, is_active)
                self.send_json({'success': True})
            else:
                self.send_json({'success': False, 'error': '缺少卡片ID'}, 400)
            return
        
        if path == '/api/cards/update':
            card_id = params.get('id')
            if not card_id:
                self.send_json({'success': False, 'error': '缺少卡片ID'}, 400)
                return
            
            try:
                success = DBManager.update_card(
                    card_id=card_id,
                    card_number=params.get('card_number'),
                    exp_month=params.get('exp_month'),
                    exp_year=params.get('exp_year'),
                    cvv=params.get('cvv'),
                    holder_name=params.get('holder_name'),
                    zip_code=params.get('zip_code'),
                    usage_count=params.get('usage_count'),
                    max_usage=params.get('max_usage'),
                    is_active=params.get('is_active')
                )
                if success:
                    self.send_json({'success': True, 'message': '卡片信息已更新'})
                else:
                    self.send_json({'success': False, 'error': '更新失败或无更改'})
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
        
        if path == '/api/cards/clear':
            DBManager.clear_all_cards()
            self.send_json({'success': True})
            return
        
        # ==================== 设置操作 ====================
        if path == '/api/settings/save':
            for key, value in params.items():
                DBManager.set_setting(key, str(value))
            
            # 如果修改了比特浏览器端口，重置API实例
            if 'bit_browser_port' in params:
                try:
                    from core.bit_api import reset_api
                    reset_api()
                except:
                    pass
            
            self.send_json({'success': True})
            return
        
        # ==================== SheerID 状态 (POST) ====================
        if path == '/api/sheerid/quota':
            try:
                import json as json_module
                
                # 优先从请求参数获取 API Key，否则从数据库获取
                api_key = params.get('api_key', '').strip()
                if not api_key:
                    api_key = DBManager.get_setting('sheerid_api_key', '')
                
                if not api_key:
                    self.send_json({
                        'success': False,
                        'error': '请先配置 API Key',
                        'current_quota': 0,
                        'available_slots': 0,
                        'active_jobs': 0
                    })
                    return
                
                # 调用 SheerID 验证器获取系统状态
                from google.backend.sheerid_verifier import SheerIDVerifier
                verifier = SheerIDVerifier(api_key)
                status = verifier.get_system_status()
                
                # 检查是否有错误
                if status.get('status') == 'error':
                    self.send_json({
                        'success': False,
                        'error': status.get('message', f"API错误: {status.get('code', 'unknown')}"),
                        'current_quota': 0,
                        'available_slots': 0,
                        'active_jobs': 0
                    })
                    return
                
                # 读取保存的配额信息（来自上次验证）
                saved_quota = 0
                quota_time = ''
                try:
                    quota_json = DBManager.get_setting('sheerid_quota', '{}')
                    quota_data = json_module.loads(quota_json)
                    saved_quota = quota_data.get('current_quota', 0)
                    quota_timestamp = DBManager.get_setting('sheerid_quota_time', '')
                    if quota_timestamp:
                        from datetime import datetime
                        dt = datetime.fromtimestamp(int(quota_timestamp))
                        quota_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
                
                # 返回系统状态 + 保存的配额信息
                result = {
                    'success': True,
                    'current_quota': saved_quota,
                    'quota_update_time': quota_time,
                    'available_slots': status.get('availableSlots', 0),
                    'active_jobs': status.get('activeJobs', 0),
                    'max_concurrent': status.get('maxConcurrent', 0),
                    'status': status.get('status', 'ok')
                }
                self.send_json(result)
            except Exception as e:
                self.send_json({
                    'success': False,
                    'error': str(e),
                    'current_quota': 0,
                    'available_slots': 0,
                    'active_jobs': 0
                })
            return
        
        # ==================== SheerID 验证 ====================
        if path == '/api/sheerid/verify':
            try:
                verification_ids = params.get('verification_ids', [])
                if not verification_ids:
                    self.send_json({'success': False, 'error': '请选择要验证的账号'})
                    return
                
                # 优先从请求参数获取 API Key，否则从数据库获取
                api_key = params.get('api_key', '').strip()
                if not api_key:
                    api_key = DBManager.get_setting('sheerid_api_key', '')
                if not api_key:
                    self.send_json({'success': False, 'error': '请先配置 API Key'})
                    return
                
                # 导入验证器
                from google.backend.sheerid_verifier import SheerIDVerifier
                import re
                
                verifier = SheerIDVerifier(api_key)
                
                # 记录验证日志
                DBManager.add_log('info', f'开始验证 {len(verification_ids)} 个账号')
                
                # 执行验证
                results = verifier.verify_batch(verification_ids)
                
                # 处理结果，更新数据库状态
                success_count = 0
                failed_count = 0
                result_details = []
                
                for vid, result in results.items():
                    status = result.get('currentStep', 'unknown')
                    message = result.get('message', '')
                    
                    detail = {
                        'verification_id': vid,
                        'status': status,
                        'message': message
                    }
                    
                    if status == 'success':
                        success_count += 1
                        # 更新数据库状态为 verified
                        DBManager.update_account_status_by_sheerid(vid, 'verified')
                        DBManager.add_log('info', f'验证成功: {vid[:20]}...')
                    else:
                        failed_count += 1
                        DBManager.add_log('warning', f'验证失败: {vid[:20]}... - {message}')
                    
                    result_details.append(detail)
                
                # 获取更新后的配额信息
                quota_info = verifier.quota_info
                
                self.send_json({
                    'success': True,
                    'total': len(verification_ids),
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'results': result_details,
                    'quota': quota_info
                })
                
                DBManager.add_log('info', f'验证完成: 成功 {success_count}, 失败 {failed_count}')
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== 数据导出 ====================
        if path == '/api/export/files':
            DBManager.export_to_files()
            self.send_json({'success': True, 'message': '已导出到data目录'})
            return
        
        # ==================== 一键全自动处理 ====================
        if path == '/api/auto/start':
            try:
                from google.backend.all_in_one_service import start_batch_task
                import uuid
                
                browser_ids = params.get('browser_ids', [])
                if not browser_ids:
                    self.send_json({'success': False, 'error': '请选择要处理的浏览器'})
                    return
                
                # 获取 API Key
                api_key = params.get('api_key', '').strip()
                if not api_key:
                    api_key = DBManager.get_setting('sheerid_api_key', '')
                
                # 获取卡片信息
                card_info = None
                card_id = params.get('card_id')
                if card_id:
                    cards = DBManager.get_all_cards()
                    for card in cards:
                        if str(card.get('id')) == str(card_id):
                            card_info = {
                                'id': card.get('id'),
                                'number': card.get('card_number', ''),
                                'exp_month': card.get('exp_month', ''),
                                'exp_year': card.get('exp_year', ''),
                                'cvv': card.get('cvv', ''),
                                'zip_code': card.get('zip_code', '14543'),
                            }
                            break
                
                # 生成任务ID
                task_id = str(uuid.uuid4())[:8]
                
                # 获取并发数
                thread_count = int(params.get('thread_count', 1))
                thread_count = max(1, min(thread_count, 10))  # 限制1-10
                
                # 启动任务
                status = start_batch_task(task_id, browser_ids, api_key, card_info, thread_count)
                
                DBManager.add_log('info', f'启动一键处理任务: {task_id}, 共 {len(browser_ids)} 个浏览器, 并发: {thread_count}')
                
                self.send_json({
                    'success': True,
                    'task_id': task_id,
                    'total': len(browser_ids),
                    'message': f'已启动任务，共 {len(browser_ids)} 个浏览器'
                })
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'success': False, 'error': str(e)})
            return
        
        if path == '/api/auto/status':
            try:
                from google.backend.all_in_one_service import get_batch_task_status
                
                task_id = params.get('task_id', '')
                if not task_id:
                    self.send_json({'success': False, 'error': '缺少 task_id'})
                    return
                
                status = get_batch_task_status(task_id)
                if status:
                    # 返回状态（返回所有日志，每条日志带索引）
                    logs_with_index = []
                    for idx, log_item in enumerate(status.get('logs', [])):
                        logs_with_index.append({
                            'idx': idx,
                            'time': log_item.get('time', 0),
                            'message': log_item.get('message', '')
                        })
                    
                    response = {
                        'success': True,
                        'task_id': status['task_id'],
                        'status': status['status'],
                        'total': status['total'],
                        'processed': status['processed'],
                        'current_browser': status.get('current_browser', ''),
                        'current_step': status.get('current_step', ''),
                        'current_step_status': status.get('current_step_status', ''),
                        'current_step_message': status.get('current_step_message', ''),
                        'stats': status['stats'],
                        'logs': logs_with_index[-100:],  # 返回最近100条带索引的日志
                        'log_total': len(status.get('logs', [])),  # 总日志数
                        'results': status['results'][-10:] if status['results'] else [],
                    }
                    self.send_json(response)
                else:
                    self.send_json({'success': False, 'error': '任务不存在'})
                    
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
        
        if path == '/api/auto/stop':
            try:
                from google.backend.all_in_one_service import stop_batch_task
                
                task_id = params.get('task_id', '')
                if not task_id:
                    self.send_json({'success': False, 'error': '缺少 task_id'})
                    return
                
                if stop_batch_task(task_id):
                    DBManager.add_log('warning', f'用户停止任务: {task_id}')
                    self.send_json({'success': True, 'message': '已发送停止请求'})
                else:
                    self.send_json({'success': False, 'error': '任务不存在'})
                    
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
        
        if path == '/api/auto/logs':
            try:
                from google.backend.all_in_one_service import get_batch_task_status
                
                task_id = params.get('task_id', '')
                offset = int(params.get('offset', 0))
                
                if not task_id:
                    self.send_json({'success': False, 'error': '缺少 task_id'})
                    return
                
                status = get_batch_task_status(task_id)
                if status:
                    logs = status.get('logs', [])
                    self.send_json({
                        'success': True,
                        'logs': logs[offset:] if offset < len(logs) else [],
                        'total': len(logs)
                    })
                else:
                    self.send_json({'success': False, 'error': '任务不存在'})
                    
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== 获取账号列表（用于一键处理）====================
        if path == '/api/accounts/for_process':
            try:
                accounts = DBManager.get_all_accounts()
                
                # 提取关键信息（不含敏感信息，但包含2FA密钥用于前端过滤）
                # 只返回已绑定浏览器窗口的账号
                account_list = []
                for acc in accounts:
                    browser_id = acc.get('browser_id', '')
                    if not browser_id:  # 跳过未绑定窗口的账号
                        continue
                    account_list.append({
                        'id': acc.get('id', ''),
                        'email': acc.get('email', ''),
                        'status': acc.get('status', 'pending'),
                        'browser_id': browser_id,
                        'updated_at': acc.get('updated_at', ''),
                        'twofa_key': acc.get('secret_key', ''),  # 用于前端筛选有2FA密钥的账号
                    })
                
                self.send_json({
                    'success': True,
                    'accounts': account_list,
                    'total': len(account_list)
                })
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== 获取已验证账号（用于绑卡）====================
        if path == '/api/accounts/verified':
            try:
                accounts = DBManager.get_accounts_by_status('verified')
                
                # 只返回已绑定浏览器窗口的账号
                account_list = []
                for acc in accounts:
                    browser_id = acc.get('browser_id', '')
                    if not browser_id:  # 跳过未绑定窗口的账号
                        continue
                    account_list.append({
                        'id': acc.get('id', ''),
                        'email': acc.get('email', ''),
                        'status': acc.get('status', 'verified'),
                        'browser_id': browser_id,
                        'updated_at': acc.get('updated_at', ''),
                    })
                
                self.send_json({
                    'success': True,
                    'accounts': account_list,
                    'total': len(account_list)
                })
                    
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== SheerLink 提取任务 ====================
        if path == '/api/sheerlink/start':
            try:
                from web.task_manager import start_sheerlink_task
                
                browser_ids = params.get('browser_ids', [])
                concurrency = int(params.get('concurrency', 1))
                
                if not browser_ids:
                    self.send_json({'success': False, 'error': '请选择要处理的账号'})
                    return
                
                task = start_sheerlink_task(browser_ids, concurrency)
                DBManager.add_log('info', f'启动 SheerLink 提取任务: {task.task_id}')
                
                self.send_json({
                    'success': True,
                    'task_id': task.task_id,
                    'total': len(browser_ids)
                })
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== 绑卡任务 ====================
        if path == '/api/bindcard/start':
            try:
                from web.task_manager import start_bindcard_task
                
                browser_ids = params.get('browser_ids', [])
                concurrency = int(params.get('concurrency', 1))
                
                if not browser_ids:
                    self.send_json({'success': False, 'error': '请选择要处理的账号'})
                    return
                
                task = start_bindcard_task(browser_ids, concurrency)
                DBManager.add_log('info', f'启动绑卡任务: {task.task_id}')
                
                self.send_json({
                    'success': True,
                    'task_id': task.task_id,
                    'total': len(browser_ids)
                })
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== 批量更改2FA任务 ====================
        if path == '/api/change2fa/start':
            try:
                from web.task_manager import start_change_2fa_task
                
                browser_ids = params.get('browser_ids', [])
                concurrency = int(params.get('concurrency', 1))
                
                if not browser_ids:
                    self.send_json({'success': False, 'error': '请选择要处理的账号'})
                    return
                
                # 从数据库获取完整账号信息
                accounts = []
                for browser_id in browser_ids:
                    account = DBManager.get_account_by_browser_id(browser_id)
                    if account:
                        accounts.append({
                            'browser_id': browser_id,
                            'email': account.get('email', ''),
                            'password': account.get('password', ''),
                            'twofa_key': account.get('twofa_key', ''),
                            'recovery_email': account.get('recovery_email', ''),
                        })
                
                if not accounts:
                    self.send_json({'success': False, 'error': '未找到有效账号'})
                    return
                
                task = start_change_2fa_task(accounts, concurrency)
                DBManager.add_log('info', f'启动批量更改2FA任务: {task.task_id}')
                
                self.send_json({
                    'success': True,
                    'task_id': task.task_id,
                    'total': len(accounts)
                })
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== 通用任务状态查询 ====================
        if path == '/api/task/status':
            try:
                from web.task_manager import get_task_status
                
                task_id = params.get('task_id', '')
                if not task_id:
                    self.send_json({'success': False, 'error': '缺少 task_id'})
                    return
                
                status = get_task_status(task_id)
                if status:
                    self.send_json({'success': True, **status})
                else:
                    self.send_json({'success': False, 'error': '任务不存在'})
                    
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
        
        # ==================== 通用任务停止 ====================
        if path == '/api/task/stop':
            try:
                from web.task_manager import stop_task
                
                task_id = params.get('task_id', '')
                if not task_id:
                    self.send_json({'success': False, 'error': '缺少 task_id'})
                    return
                
                if stop_task(task_id):
                    self.send_json({'success': True, 'message': '已发送停止请求'})
                else:
                    self.send_json({'success': False, 'error': '任务不存在'})
                    
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return
            
        self.send_json({'success': False, 'error': 'API not found'}, 404)


def run_server(port: int = 8080, auto_open: bool = True):
    """
    @brief 启动Web Admin服务器
    @param port 服务器端口
    @param auto_open 是否自动打开浏览器
    """
    # 确保目录存在
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    os.makedirs(os.path.join(STATIC_DIR, 'css'), exist_ok=True)
    os.makedirs(os.path.join(STATIC_DIR, 'js'), exist_ok=True)
    
    # 初始化数据库
    DBManager.init_db()
    
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", port), APIHandler) as httpd:
            print(f"╔══════════════════════════════════════════╗")
            print(f"║   🚀 Web Admin Server Started            ║")
            print(f"║   📍 http://localhost:{port:<5}              ║")
            print(f"║   💡 Press Ctrl+C to stop                ║")
            
            # 自动打开浏览器
            if auto_open:
                url = f"http://localhost:{port}"
                def open_browser():
                    time.sleep(0.5)  # 等待服务器完全启动
                    webbrowser.open(url)
                threading.Thread(target=open_browser, daemon=True).start()
                print(f"║   🌐 Opening browser automatically...    ║")
            print(f"╚══════════════════════════════════════════╝")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
    except OSError as e:
        print(f"❌ Port {port} error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Web Admin Server')
    parser.add_argument('-p', '--port', type=int, default=8080, help='Server port')
    args = parser.parse_args()
    run_server(args.port)
