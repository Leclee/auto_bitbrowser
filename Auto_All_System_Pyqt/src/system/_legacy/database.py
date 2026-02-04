"""
统一数据库管理模块
完全采用数据库存储，弃用txt文件导入

注意: 此文件为兼容层，实际模块已迁移至 src/core/database.py
新代码请使用: from core.database import DBManager
"""
import sqlite3
import os
import sys
import threading
import re
from datetime import datetime

# 数据目录路径
if getattr(sys, 'frozen', False):
    # 打包后，数据文件在 exe 同级目录
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 开发时，数据文件在 data/ 目录
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.join(os.path.dirname(SRC_DIR), 'data')

# 确保数据目录存在
os.makedirs(BASE_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "accounts.db")

lock = threading.Lock()


class DBManager:
    """统一数据库管理类"""
    
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_db():
        """初始化数据库，创建所有表"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            # ==================== 账号表 ====================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    email TEXT PRIMARY KEY,
                    password TEXT,
                    recovery_email TEXT,
                    secret_key TEXT,
                    verification_link TEXT,
                    browser_id TEXT,
                    status TEXT DEFAULT 'pending_check',
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 检查并添加新列（兼容旧数据库）
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'browser_id' not in columns:
                cursor.execute('ALTER TABLE accounts ADD COLUMN browser_id TEXT')
            if 'created_at' not in columns:
                # SQLite不允许带非常量默认值的ALTER TABLE，只能添加不带默认值的列
                cursor.execute('ALTER TABLE accounts ADD COLUMN created_at TIMESTAMP')
            
            # ==================== 代理表 ====================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proxies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy_type TEXT DEFAULT 'socks5',
                    host TEXT NOT NULL,
                    port TEXT NOT NULL,
                    username TEXT,
                    password TEXT,
                    remark TEXT,
                    is_used INTEGER DEFAULT 0,
                    used_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ==================== 卡片表 ====================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_number TEXT NOT NULL UNIQUE,
                    exp_month TEXT NOT NULL,
                    exp_year TEXT NOT NULL,
                    cvv TEXT NOT NULL,
                    holder_name TEXT,
                    billing_address TEXT,
                    remark TEXT,
                    usage_count INTEGER DEFAULT 0,
                    max_usage INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ==================== 系统设置表 ====================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ==================== 操作日志表 ====================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    target_email TEXT,
                    details TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
        print(f"[DB] 数据库初始化完成: {DB_PATH}")
    
    # ==================== 账号管理 ====================
    
    @staticmethod
    def _parse_account_line(line, separator='----'):
        """
        解析账号信息行
        格式: email----password----recovery_email----secret_key
        或包含链接: link----email----password----recovery_email----secret_key
        """
        if not line or not line.strip():
            return None
        
        line = line.strip()
        
        # 移除注释
        if '#' in line:
            line = line.split('#')[0].strip()
        
        if not line:
            return None
        
        # 识别HTTP链接
        link = None
        link_match = re.search(r'https?://[^\s]+', line)
        if link_match:
            link = link_match.group()
            line = line.replace(link, '').strip()
            # 清理可能残留的分隔符
            line = re.sub(r'^[-]+', '', line).strip()
        
        # 分割字段
        parts = line.split(separator)
        parts = [p.strip() for p in parts if p.strip()]
        
        result = {
            'email': None,
            'password': None,
            'recovery_email': None,
            'secret_key': None,
            'verification_link': link
        }
        
        # 智能识别字段
        emails = []
        secrets = []
        others = []
        
        for part in parts:
            if '@' in part and '.' in part:
                emails.append(part)
            elif re.match(r'^[A-Z0-9]{16,}$', part):
                secrets.append(part)
            else:
                others.append(part)
        
        # 分配字段
        if len(emails) >= 1:
            result['email'] = emails[0]
        if len(emails) >= 2:
            result['recovery_email'] = emails[1]
        if len(secrets) >= 1:
            result['secret_key'] = secrets[0]
        if len(others) >= 1:
            result['password'] = others[0]
        
        return result if result['email'] else None
    
    @staticmethod
    def import_accounts_from_text(text, separator='----', default_status='pending_check'):
        """
        从文本批量导入账号到数据库
        
        Args:
            text: 多行文本，每行一个账号
            separator: 分隔符
            default_status: 默认状态
            
        Returns:
            (success_count, error_count, errors)
        """
        lines = text.strip().split('\n')
        success_count = 0
        error_count = 0
        errors = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('分隔符='):
                continue
            
            account = DBManager._parse_account_line(line, separator)
            if account and account.get('email'):
                try:
                    DBManager.upsert_account(
                        email=account['email'],
                        password=account.get('password'),
                        recovery_email=account.get('recovery_email'),
                        secret_key=account.get('secret_key'),
                        link=account.get('verification_link'),
                        status=default_status
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Line {line_num}: {str(e)}")
            else:
                error_count += 1
                errors.append(f"Line {line_num}: 无法解析 - {line[:50]}")
        
        return success_count, error_count, errors
    
    @staticmethod
    def upsert_account(email, password=None, recovery_email=None, secret_key=None, 
                       link=None, browser_id=None, status=None, message=None):
        """插入或更新账号信息"""
        if not email:
            return
            
        try:
            with lock:
                conn = DBManager.get_connection()
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM accounts WHERE email = ?", (email,))
                exists = cursor.fetchone()
                
                if exists:
                    fields = []
                    values = []
                    if password is not None: fields.append("password = ?"); values.append(password)
                    if recovery_email is not None: fields.append("recovery_email = ?"); values.append(recovery_email)
                    if secret_key is not None: fields.append("secret_key = ?"); values.append(secret_key)
                    if link is not None: fields.append("verification_link = ?"); values.append(link)
                    if browser_id is not None: fields.append("browser_id = ?"); values.append(browser_id)
                    if status is not None: fields.append("status = ?"); values.append(status)
                    if message is not None: fields.append("message = ?"); values.append(message)
                    
                    if fields:
                        fields.append("updated_at = CURRENT_TIMESTAMP")
                        values.append(email)
                        sql = f"UPDATE accounts SET {', '.join(fields)} WHERE email = ?"
                        cursor.execute(sql, values)
                else:
                    cursor.execute('''
                        INSERT INTO accounts (email, password, recovery_email, secret_key, 
                                            verification_link, browser_id, status, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (email, password, recovery_email, secret_key, link, browser_id, 
                          status or 'pending_check', message))
                
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[DB ERROR] upsert_account: {e}")

    @staticmethod
    def update_status(email, status, message=None):
        """更新账号状态"""
        DBManager.upsert_account(email, status=status, message=message)
    
    @staticmethod
    def delete_account(email):
        """删除账号"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM accounts WHERE email = ?', (email,))
            conn.commit()
            conn.close()

    @staticmethod
    def get_accounts_by_status(status):
        """按状态获取账号"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE status = ?", (status,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_accounts_without_browser():
        """获取没有browser_id的账号"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE browser_id IS NULL OR browser_id = ''")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
            
    @staticmethod
    def get_all_accounts():
        """获取所有账号"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_accounts_count_by_status():
        """获取各状态账号统计"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM accounts 
                GROUP BY status
            """)
            rows = cursor.fetchall()
            conn.close()
            return {row['status']: row['count'] for row in rows}
    
    # ==================== 代理管理 ====================
    
    @staticmethod
    def import_proxies_from_text(text, proxy_type='socks5'):
        """
        从文本批量导入代理
        
        支持格式:
        - socks5://user:pass@host:port
        - host:port:user:pass
        - host:port
        
        Returns:
            (success_count, error_count, errors)
        """
        lines = text.strip().split('\n')
        success_count = 0
        error_count = 0
        errors = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            proxy = DBManager._parse_proxy_line(line)
            if proxy:
                try:
                    DBManager.add_proxy(
                        proxy_type=proxy.get('type', proxy_type),
                        host=proxy['host'],
                        port=proxy['port'],
                        username=proxy.get('username'),
                        password=proxy.get('password')
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Line {line_num}: {str(e)}")
            else:
                error_count += 1
                errors.append(f"Line {line_num}: 无法解析 - {line[:50]}")
        
        return success_count, error_count, errors
    
    @staticmethod
    def _parse_proxy_line(line):
        """解析代理行"""
        line = line.strip()
        
        # 格式1: socks5://user:pass@host:port
        match = re.match(r'^(socks5|http|https)://([^:]+):([^@]+)@([^:]+):(\d+)$', line)
        if match:
            return {
                'type': match.group(1),
                'username': match.group(2),
                'password': match.group(3),
                'host': match.group(4),
                'port': match.group(5)
            }
        
        # 格式2: host:port:user:pass
        parts = line.split(':')
        if len(parts) == 4:
            return {
                'type': 'socks5',
                'host': parts[0],
                'port': parts[1],
                'username': parts[2],
                'password': parts[3]
            }
        
        # 格式3: host:port
        if len(parts) == 2:
            return {
                'type': 'socks5',
                'host': parts[0],
                'port': parts[1],
                'username': None,
                'password': None
            }
        
        return None
    
    @staticmethod
    def add_proxy(proxy_type, host, port, username=None, password=None, remark=None):
        """添加代理"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO proxies (proxy_type, host, port, username, password, remark)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (proxy_type, host, port, username, password, remark))
            proxy_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return proxy_id
    
    @staticmethod
    def get_all_proxies():
        """获取所有代理"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM proxies ORDER BY id")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_available_proxies(limit=None):
        """获取可用代理（未被使用的）"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            sql = "SELECT * FROM proxies WHERE is_used = 0 ORDER BY id"
            if limit:
                sql += f" LIMIT {limit}"
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def mark_proxy_used(proxy_id, used_by_email):
        """标记代理已使用"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE proxies 
                SET is_used = 1, used_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (used_by_email, proxy_id))
            conn.commit()
            conn.close()
    
    @staticmethod
    def delete_proxy(proxy_id):
        """删除代理"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM proxies WHERE id = ?', (proxy_id,))
            conn.commit()
            conn.close()
    
    @staticmethod
    def clear_all_proxies():
        """清空所有代理"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM proxies')
            conn.commit()
            conn.close()
    
    # ==================== 卡片管理 ====================
    
    @staticmethod
    def import_cards_from_text(text, max_usage=1):
        """
        从文本批量导入卡片
        
        支持格式:
        - card_number exp_month exp_year cvv [holder_name]
        - card_number----exp_month----exp_year----cvv
        
        Returns:
            (success_count, error_count, errors)
        """
        lines = text.strip().split('\n')
        success_count = 0
        error_count = 0
        errors = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('分隔符='):
                continue
            
            card = DBManager._parse_card_line(line)
            if card:
                try:
                    DBManager.add_card(
                        card_number=card['number'],
                        exp_month=card['exp_month'],
                        exp_year=card['exp_year'],
                        cvv=card['cvv'],
                        holder_name=card.get('holder_name'),
                        max_usage=max_usage
                    )
                    success_count += 1
                except sqlite3.IntegrityError:
                    # 卡号已存在，跳过
                    error_count += 1
                    errors.append(f"Line {line_num}: 卡号已存在")
                except Exception as e:
                    error_count += 1
                    errors.append(f"Line {line_num}: {str(e)}")
            else:
                error_count += 1
                errors.append(f"Line {line_num}: 无法解析 - {line[:30]}")
        
        return success_count, error_count, errors
    
    @staticmethod
    def _parse_card_line(line):
        """解析卡片行"""
        line = line.strip()
        
        # 尝试空格分隔
        parts = line.split()
        if len(parts) >= 4:
            return {
                'number': parts[0].replace('-', '').replace(' ', ''),
                'exp_month': parts[1],
                'exp_year': parts[2],
                'cvv': parts[3],
                'holder_name': ' '.join(parts[4:]) if len(parts) > 4 else None
            }
        
        # 尝试 ---- 分隔
        parts = line.split('----')
        if len(parts) >= 4:
            return {
                'number': parts[0].replace('-', '').replace(' ', ''),
                'exp_month': parts[1],
                'exp_year': parts[2],
                'cvv': parts[3],
                'holder_name': parts[4] if len(parts) > 4 else None
            }
        
        return None
    
    @staticmethod
    def add_card(card_number, exp_month, exp_year, cvv, holder_name=None, 
                 billing_address=None, remark=None, max_usage=1):
        """添加卡片"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cards (card_number, exp_month, exp_year, cvv, 
                                  holder_name, billing_address, remark, max_usage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (card_number, exp_month, exp_year, cvv, holder_name, 
                  billing_address, remark, max_usage))
            card_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return card_id
    
    @staticmethod
    def get_all_cards():
        """获取所有卡片"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards ORDER BY id")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_available_cards():
        """获取可用卡片（使用次数未达上限且激活的）"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cards 
                WHERE is_active = 1 AND usage_count < max_usage
                ORDER BY usage_count ASC, id ASC
            """)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def increment_card_usage(card_id):
        """增加卡片使用次数"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cards 
                SET usage_count = usage_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (card_id,))
            conn.commit()
            conn.close()
    
    @staticmethod
    def delete_card(card_id):
        """删除卡片"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cards WHERE id = ?', (card_id,))
            conn.commit()
            conn.close()
    
    @staticmethod
    def clear_all_cards():
        """清空所有卡片"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cards')
            conn.commit()
            conn.close()
    
    @staticmethod
    def set_card_active(card_id, is_active):
        """设置卡片激活状态"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cards SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (1 if is_active else 0, card_id))
            conn.commit()
            conn.close()
    
    # ==================== 设置管理 ====================
    
    @staticmethod
    def get_setting(key, default=None):
        """获取设置值"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row['value'] if row else default
    
    @staticmethod
    def set_setting(key, value, description=None):
        """设置值"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (key, value, description))
            conn.commit()
            conn.close()
    
    @staticmethod
    def get_all_settings():
        """获取所有设置"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM settings")
            rows = cursor.fetchall()
            conn.close()
            return {row['key']: row['value'] for row in rows}
    
    # ==================== 操作日志 ====================
    
    @staticmethod
    def log_operation(operation_type, target_email=None, details=None, status='success'):
        """记录操作日志"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO operation_logs (operation_type, target_email, details, status)
                VALUES (?, ?, ?, ?)
            ''', (operation_type, target_email, details, status))
            conn.commit()
            conn.close()
    
    @staticmethod
    def get_recent_logs(limit=100):
        """获取最近的操作日志"""
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM operation_logs 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    # ==================== 导出功能（兼容旧版） ====================
    
    @staticmethod
    def export_to_files():
        """将数据库导出为传统文本文件，方便查看"""
        print("[DB] 开始导出数据库到文本文件...")
        
        files_map = {
            "link_ready": "sheerIDlink.txt",
            "verified": "已验证未绑卡.txt",
            "subscribed": "已绑卡号.txt",
            "ineligible": "无资格号.txt",
            "error": "超时或其他错误.txt"
        }
        
        pending_file = "有资格待验证号.txt"
        
        try:
            with lock:
                conn = DBManager.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM accounts")
                rows = cursor.fetchall()
                conn.close()
                
                data = {k: [] for k in files_map.keys()}
                pending_data = []
                
                for row in rows:
                    st = row['status']
                    if st in ('running', 'processing'):
                        continue
                    
                    email = row['email']
                    line_acc = email
                    if row['password']: line_acc += f"----{row['password']}"
                    if row['recovery_email']: line_acc += f"----{row['recovery_email']}"
                    if row['secret_key']: line_acc += f"----{row['secret_key']}"

                    if st == 'link_ready':
                        if row['verification_link']:
                            line_link = f"{row['verification_link']}----{line_acc}"
                            data['link_ready'].append(line_link)
                        pending_data.append(line_acc)
                    elif st in data:
                        data[st].append(line_acc)
                
                for status, filename in files_map.items():
                    target_path = os.path.join(BASE_DIR, filename)
                    lines = data[status]
                    with open(target_path, 'w', encoding='utf-8') as f:
                        for l in lines:
                            f.write(l + "\n")
                    print(f"[DB] 导出 {len(lines)} 条记录到 {filename}")
                
                pending_path = os.path.join(BASE_DIR, pending_file)
                with open(pending_path, 'w', encoding='utf-8') as f:
                    for l in pending_data:
                        f.write(l + "\n")
                print(f"[DB] 导出 {len(pending_data)} 条记录到 {pending_file}")
                
                print("[DB] 导出完成！")
        except Exception as e:
            print(f"[DB ERROR] export_to_files: {e}")
    
    # ==================== 浏览器同步（从比特浏览器导入账号） ====================
    
    @staticmethod
    def import_from_browsers():
        """从比特浏览器窗口导入账号"""
        import threading
        
        def _run_import():
            try:
                from create_window import get_browser_list, parse_account_line
                
                page = 0
                page_size = 50
                total_imported = 0
                total_updated = 0
                
                print(f"[DB] 开始从浏览器导入 (每页 {page_size} 条)...")
                
                while True:
                    try:
                        browser_list = get_browser_list(page=page, pageSize=page_size)
                    except Exception as e:
                        print(f"[DB] 获取浏览器列表失败(页{page}): {e}")
                        break
                        
                    if not browser_list or len(browser_list) == 0:
                        break
                    
                    current_imported = 0
                    current_updated = 0
                    
                    for browser in browser_list:
                        browser_id = browser.get('id', '')
                        remark = browser.get('remark', '').strip()
                        
                        if not remark or not browser_id:
                            continue
                        
                        parts = remark.split('----')
                        account = {}
                        
                        if len(parts) >= 1 and '@' in parts[0]:
                            account['email'] = parts[0].strip()
                            if len(parts) >= 2:
                                account['password'] = parts[1].strip()
                            for part in parts[2:]:
                                p = part.strip()
                                if not p:
                                    continue
                                if '@' in p and '.' in p:
                                    account['backup_email'] = p
                                else:
                                    account['2fa_secret'] = p
                        else:
                            account = parse_account_line(remark, '----')
                        
                        if account and account.get('email'):
                            email = account.get('email')
                            
                            try:
                                with lock:
                                    conn = DBManager.get_connection()
                                    cursor = conn.cursor()
                                    cursor.execute('SELECT browser_id, password, secret_key FROM accounts WHERE email = ?', (email,))
                                    row = cursor.fetchone()
                                    
                                    if row:
                                        updates = []
                                        values = []
                                        
                                        if not row[0]:
                                            updates.append("browser_id = ?")
                                            values.append(browser_id)
                                        
                                        if not row[1] and account.get('password'):
                                            updates.append("password = ?")
                                            values.append(account.get('password'))
                                            
                                        if not row[2] and account.get('2fa_secret'):
                                            updates.append("secret_key = ?")
                                            values.append(account.get('2fa_secret'))
                                        
                                        if updates:
                                            values.append(email)
                                            sql = f"UPDATE accounts SET {', '.join(updates)} WHERE email = ?"
                                            cursor.execute(sql, values)
                                            conn.commit()
                                            current_updated += 1
                                    else:
                                        cursor.execute('''
                                            INSERT INTO accounts (email, password, recovery_email, secret_key, 
                                                                verification_link, browser_id, status, message)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                        ''', (
                                            email, 
                                            account.get('password'), 
                                            account.get('backup_email'), 
                                            account.get('2fa_secret'), 
                                            None, 
                                            browser_id, 
                                            'pending_check', 
                                            None
                                        ))
                                        conn.commit()
                                        current_imported += 1
                                    
                                    conn.close()
                            except Exception as e:
                                print(f"[DB] 处理账号 {email} 出错: {e}")

                    total_imported += current_imported
                    total_updated += current_updated
                    print(f"[DB] 第 {page+1} 页处理完成: 新增 {current_imported}, 更新 {current_updated}")
                    
                    page += 1
                    import time
                    time.sleep(0.5)
                
                print(f"[DB] 浏览器导入完成! 新增 {total_imported}, 更新 {total_updated}")
                
            except Exception as e:
                print(f"[DB] 导入异常: {e}")
                import traceback
                traceback.print_exc()

        t = threading.Thread(target=_run_import, daemon=True)
        t.start()


# 初始化数据库（模块加载时自动执行）
# DBManager.init_db()  # 注释掉，由调用方显式初始化
