"""
@file database.py
@brief 统一数据库管理模块
@details 完全采用数据库存储，提供账号、代理、卡片等数据的统一管理
"""
import sqlite3
import os
import sys
import threading
import re
from datetime import datetime

# 数据目录路径 - 使用配置模块的路径
try:
    from .config import Config
    BASE_DIR = Config.DATA_DIR
    DB_PATH = Config.DB_PATH
except ImportError:
    # 兼容直接运行
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        SRC_DIR = os.path.dirname(os.path.abspath(__file__))
        BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(SRC_DIR)), 'data')
    DB_PATH = os.path.join(BASE_DIR, "accounts.db")

# 确保数据目录存在
os.makedirs(BASE_DIR, exist_ok=True)

lock = threading.Lock()


class DBManager:
    """
    @class DBManager
    @brief 统一数据库管理类
    @details 提供账号、代理、卡片、设置等数据的CRUD操作
    """
    
    @staticmethod
    def get_connection():
        """
        @brief 获取数据库连接
        @return sqlite3连接对象
        """
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_db():
        """
        @brief 初始化数据库，创建所有表
        """
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
                cursor.execute('ALTER TABLE accounts ADD COLUMN created_at TIMESTAMP')
            if 'is_exported' not in columns:
                cursor.execute('ALTER TABLE accounts ADD COLUMN is_exported INTEGER DEFAULT 0')
            
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
                    zip_code TEXT,
                    billing_address TEXT,
                    remark TEXT,
                    usage_count INTEGER DEFAULT 0,
                    max_usage INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 检查并添加zip_code列（兼容旧数据库）
            cursor.execute("PRAGMA table_info(cards)")
            card_columns = [col[1] for col in cursor.fetchall()]
            if 'zip_code' not in card_columns:
                cursor.execute('ALTER TABLE cards ADD COLUMN zip_code TEXT')
            
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
        @brief 解析账号信息行
        @param line 账号信息行
        @param separator 分隔符
        @return 解析后的账号字典，失败返回None
        @details 支持格式:
                 - email----password (2段)
                 - email----password----recovery_email (3段，第3段含@)
                 - email----password----secret_key (3段，第3段不含@)
                 - email----password----recovery_email----secret_key (4段)
                 - link----email----password----... (带链接前缀)
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
            # 移除链接后的前导分隔符
            if separator and line.startswith(separator):
                line = line[len(separator):].strip()
        
        # 确保分隔符有效（处理用户输入）
        if not separator or separator == '':
            separator = '----'
        
        # 分割字段
        parts = line.split(separator)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) < 2:
            return None
        
        result = {
            'email': None,
            'password': None,
            'recovery_email': None,
            'secret_key': None,
            'verification_link': link
        }
        
        # 第一个字段：邮箱
        if '@' in parts[0] and '.' in parts[0]:
            result['email'] = parts[0]
        else:
            return None  # 第一个字段必须是邮箱
        
        # 第二个字段：密码
        if len(parts) >= 2:
            result['password'] = parts[1]
        
        # 第三个字段：智能识别（根据是否包含@判断是辅助邮箱还是2FA秘钥）
        if len(parts) >= 3:
            third_field = parts[2]
            if '@' in third_field and '.' in third_field:
                # 包含@，是辅助邮箱
                result['recovery_email'] = third_field
            else:
                # 不包含@，是2FA秘钥（通常是大写字母+数字的组合）
                result['secret_key'] = third_field
        
        # 第四个字段：如果有，则根据第三个字段来判断
        if len(parts) >= 4:
            fourth_field = parts[3]
            if result['recovery_email'] is None:
                # 第三个是秘钥，第四个应该是辅助邮箱或其他
                if '@' in fourth_field and '.' in fourth_field:
                    result['recovery_email'] = fourth_field
            else:
                # 第三个是辅助邮箱，第四个应该是秘钥
                result['secret_key'] = fourth_field
        
        return result if result['email'] else None
    
    @staticmethod
    def import_accounts_from_text(text, separator='----', default_status='pending_check'):
        """
        @brief 从文本批量导入账号到数据库
        @param text 多行文本，每行一个账号
        @param separator 分隔符
        @param default_status 默认状态
        @return (success_count, error_count, errors)
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
        """
        @brief 插入或更新账号信息
        @param email 邮箱（主键）
        @param password 密码
        @param recovery_email 辅助邮箱
        @param secret_key 2FA密钥
        @param link 验证链接
        @param browser_id 浏览器窗口ID
        @param status 账号状态
        @param message 状态消息
        """
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
        """
        @brief 更新账号状态
        @param email 邮箱
        @param status 新状态
        @param message 状态消息
        """
        DBManager.upsert_account(email, status=status, message=message)
    
    @staticmethod
    def delete_account(email):
        """
        @brief 删除账号
        @param email 邮箱
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM accounts WHERE email = ?', (email,))
            conn.commit()
            conn.close()

    @staticmethod
    def get_accounts_by_status(status):
        """
        @brief 按状态获取账号
        @param status 状态筛选条件
        @return 账号列表
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE status = ?", (status,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_accounts_without_browser():
        """
        @brief 获取没有browser_id且状态为pending_check的账号
        @return 账号列表
        @note 只返回待检查状态的账号，已处理完成的账号不会重复创建窗口
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            # 只获取状态为 pending_check 且没有 browser_id 的账号
            cursor.execute("""
                SELECT * FROM accounts 
                WHERE (browser_id IS NULL OR browser_id = '')
                AND status = 'pending_check'
            """)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def batch_update_status(emails: list, status: str, message: str = None):
        """
        @brief 批量更新账号状态
        @param emails 邮箱列表
        @param status 新状态
        @param message 状态消息（可选）
        @return 成功更新的数量
        """
        if not emails:
            return 0
        
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            updated = 0
            for email in emails:
                try:
                    if message:
                        cursor.execute("""
                            UPDATE accounts 
                            SET status = ?, message = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE email = ?
                        """, (status, message, email))
                    else:
                        cursor.execute("""
                            UPDATE accounts 
                            SET status = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE email = ?
                        """, (status, email))
                    updated += cursor.rowcount
                except Exception:
                    pass
            
            conn.commit()
            conn.close()
            return updated
            
    @staticmethod
    def get_all_accounts():
        """
        @brief 获取所有账号
        @return 账号列表
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def update_account_browser_id(email: str, browser_id: str):
        """
        @brief 更新账号的浏览器窗口ID
        @param email 邮箱
        @param browser_id 浏览器窗口ID
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE accounts 
                SET browser_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE email = ?
            """, (browser_id, email))
            conn.commit()
            conn.close()
    
    @staticmethod
    def get_accounts_count_by_status():
        """
        @brief 获取各状态账号统计
        @return 状态统计字典
        """
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
    
    @staticmethod
    def get_sheerid_link_by_browser(browser_id: str) -> str:
        """
        @brief 根据browser_id获取SheerID验证链接
        @param browser_id 浏览器窗口ID
        @return 验证链接或空字符串
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT verification_link FROM accounts 
                WHERE browser_id = ?
            """, (browser_id,))
            row = cursor.fetchone()
            conn.close()
            return row['verification_link'] if row and row['verification_link'] else ''
    
    @staticmethod
    def update_sheerid_link(email: str, link: str):
        """
        @brief 更新账号的SheerID验证链接
        @param email 邮箱
        @param link 验证链接
        """
        DBManager.upsert_account(email, link=link)
    
    @staticmethod
    def update_account_status(email: str, status: str, message: str = None):
        """
        @brief 更新账号状态
        @param email 邮箱
        @param status 新状态
        @param message 状态消息
        """
        DBManager.upsert_account(email, status=status, message=message)
    
    @staticmethod
    def update_account_status_by_sheerid(verification_id: str, status: str):
        """
        @brief 根据SheerID验证ID更新账号状态
        @param verification_id SheerID验证ID
        @param status 新状态
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            # 查找包含此验证ID的账号
            cursor.execute("""
                UPDATE accounts 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE verification_link LIKE ?
            """, (status, f'%{verification_id}%'))
            conn.commit()
            conn.close()
    
    @staticmethod
    def update_account_2fa_key(email: str, new_2fa_key: str):
        """
        @brief 更新账号的2FA密钥
        @param email 邮箱
        @param new_2fa_key 新的2FA密钥
        """
        DBManager.upsert_account(email, secret_key=new_2fa_key)
    
    @staticmethod
    def get_account_by_browser_id(browser_id: str) -> dict:
        """
        @brief 根据浏览器窗口ID获取账号信息
        @param browser_id 浏览器窗口ID
        @return 账号字典 或 None
        """
        if not browser_id:
            return None
        
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, password, recovery_email, secret_key, 
                       verification_link, browser_id, status, message
                FROM accounts 
                WHERE browser_id = ?
            """, (browser_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'email': row['email'],
                    'password': row['password'],
                    'recovery_email': row['recovery_email'],
                    'twofa_key': row['secret_key'],  # 使用 twofa_key 作为别名
                    'verification_link': row['verification_link'],
                    'browser_id': row['browser_id'],
                    'status': row['status'],
                    'message': row['message']
                }
            return None
    
    # ==================== 代理管理 ====================
    
    @staticmethod
    def import_proxies_from_text(text, proxy_type='socks5'):
        """
        @brief 从文本批量导入代理
        @param text 多行代理文本
        @param proxy_type 代理类型
        @return (success_count, error_count, errors)
        @details 支持格式:
                 - socks5://user:pass@host:port
                 - host:port:user:pass
                 - host:port
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
        """
        @brief 解析代理行
        @param line 代理配置行
        @return 代理配置字典
        @details 支持多种格式:
            1. socks5://user:pass@host:port (协议前缀格式)
            2. host:port@user:pass (@ 分隔格式)
            3. host:port:user:pass (冒号分隔格式)
            4. host:port (无认证格式)
        """
        line = line.strip()
        if not line:
            return None
        
        # 格式1: socks5://user:pass@host:port (协议前缀格式)
        match = re.match(r'^(socks5|http|https)://([^:]+):([^@]+)@([^:]+):(\d+)$', line)
        if match:
            return {
                'type': match.group(1),
                'username': match.group(2),
                'password': match.group(3),
                'host': match.group(4),
                'port': match.group(5)
            }
        
        # 格式2: host:port@user:pass (@ 分隔用户名密码)
        # 例如: gate-hk.kookeey.info:1000@4366769-30f7750d:51399134-US-80198377-20m
        if '@' in line:
            at_parts = line.split('@', 1)  # 只分割第一个 @
            if len(at_parts) == 2:
                host_port = at_parts[0]
                user_pass = at_parts[1]
                
                # 解析 host:port
                hp_match = re.match(r'^([^:]+):(\d+)$', host_port)
                if hp_match:
                    host = hp_match.group(1)
                    port = hp_match.group(2)
                    
                    # 解析 user:pass (密码可能包含冒号，所以只分割第一个冒号)
                    if ':' in user_pass:
                        up_parts = user_pass.split(':', 1)
                        username = up_parts[0]
                        password = up_parts[1]
                    else:
                        username = user_pass
                        password = None
                    
                    return {
                        'type': 'socks5',
                        'host': host,
                        'port': port,
                        'username': username,
                        'password': password
                    }
        
        # 格式3: host:port:user:pass (冒号分隔格式)
        parts = line.split(':')
        if len(parts) == 4:
            return {
                'type': 'socks5',
                'host': parts[0],
                'port': parts[1],
                'username': parts[2],
                'password': parts[3]
            }
        
        # 格式4: host:port (无认证格式)
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
        """
        @brief 添加代理
        @return 代理ID
        """
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
        """
        @brief 获取所有代理
        @return 代理列表
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM proxies ORDER BY id")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_available_proxies(limit=None):
        """
        @brief 获取可用代理（未被使用的）
        @param limit 限制数量
        @return 代理列表
        """
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
        """
        @brief 标记代理已使用
        @param proxy_id 代理ID
        @param used_by_email 使用者邮箱
        """
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
        """
        @brief 删除代理
        @param proxy_id 代理ID
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM proxies WHERE id = ?', (proxy_id,))
            conn.commit()
            conn.close()
    
    @staticmethod
    def clear_all_proxies():
        """
        @brief 清空所有代理
        """
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
        @brief 从文本批量导入卡片
        @param text 多行卡片文本
        @param max_usage 最大使用次数
        @return (success_count, error_count, errors)
        @details 支持格式:
                 - card_number exp_month exp_year cvv [holder_name]
                 - card_number----exp_month----exp_year----cvv
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
                        zip_code=card.get('zip_code'),
                        max_usage=max_usage
                    )
                    success_count += 1
                except sqlite3.IntegrityError:
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
        """
        @brief 解析卡片行
        @param line 卡片配置行
        @return 卡片配置字典
        @details 支持格式（空格分隔）：
                 - 卡号 月 年 CVV
                 - 卡号 月 年 CVV 持卡人
                 - 卡号 月 年 CVV 邮编（纯数字）
                 - 卡号 月 年 CVV 持卡人 邮编
                 智能识别：纯数字=邮编，含字母=持卡人
        """
        line = line.strip()
        
        result = {
            'number': None,
            'exp_month': None,
            'exp_year': None,
            'cvv': None,
            'holder_name': None,
            'zip_code': None
        }
        
        # 尝试空格分隔
        parts = line.split()
        if len(parts) < 4:
            # 尝试 ---- 分隔
            parts = line.split('----')
        
        if len(parts) < 4:
            return None
        
        # 前4个字段是固定的：卡号、月、年、CVV
        result['number'] = parts[0].replace('-', '').replace(' ', '')
        result['exp_month'] = parts[1]
        result['exp_year'] = parts[2]
        result['cvv'] = parts[3]
        
        # 处理第5、6个字段（可能是持卡人、邮编或两者都有）
        if len(parts) >= 5:
            fifth = parts[4]
            # 判断第5个字段是持卡人还是邮编
            if fifth.isdigit():
                # 纯数字，是邮编
                result['zip_code'] = fifth
            else:
                # 含字母，是持卡人
                # 如果持卡人名字有多个单词，需要合并
                if len(parts) >= 6 and parts[-1].isdigit():
                    # 最后一项是邮编，中间都是持卡人名字
                    result['holder_name'] = ' '.join(parts[4:-1])
                    result['zip_code'] = parts[-1]
                else:
                    # 没有邮编，剩下的都是持卡人名字
                    result['holder_name'] = ' '.join(parts[4:])
        
        return result
    
    @staticmethod
    def add_card(card_number, exp_month, exp_year, cvv, holder_name=None, 
                 billing_address=None, remark=None, max_usage=1, zip_code=None):
        """
        @brief 添加卡片
        @return 卡片ID
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cards (card_number, exp_month, exp_year, cvv, 
                                  holder_name, zip_code, billing_address, remark, max_usage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (card_number, exp_month, exp_year, cvv, holder_name, 
                  zip_code, billing_address, remark, max_usage))
            card_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return card_id
    
    @staticmethod
    def get_all_cards():
        """
        @brief 获取所有卡片
        @return 卡片列表
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards ORDER BY id")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_available_cards():
        """
        @brief 获取可用卡片（使用次数未达上限且激活的）
        @return 卡片列表
        """
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
        """
        @brief 增加卡片使用次数
        @param card_id 卡片ID
        @return 更新后的使用次数
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cards 
                SET usage_count = usage_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (card_id,))
            conn.commit()
            
            # 查询更新后的使用次数
            cursor.execute('SELECT usage_count, max_usage FROM cards WHERE id = ?', (card_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0], row[1]  # (usage_count, max_usage)
            return None, None
    
    @staticmethod
    def delete_card(card_id):
        """
        @brief 删除卡片
        @param card_id 卡片ID
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cards WHERE id = ?', (card_id,))
            conn.commit()
            conn.close()
    
    @staticmethod
    def clear_all_cards():
        """
        @brief 清空所有卡片
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cards')
            conn.commit()
            conn.close()
    
    @staticmethod
    def set_card_active(card_id, is_active):
        """
        @brief 设置卡片激活状态
        @param card_id 卡片ID
        @param is_active 是否激活
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cards SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (1 if is_active else 0, card_id))
            conn.commit()
            conn.close()
    
    @staticmethod
    def update_card(card_id, card_number=None, exp_month=None, exp_year=None, 
                   cvv=None, holder_name=None, zip_code=None, usage_count=None, 
                   max_usage=None, is_active=None):
        """
        @brief 更新卡片信息
        @param card_id 卡片ID
        @param card_number 卡号
        @param exp_month 过期月份
        @param exp_year 过期年份
        @param cvv CVV
        @param holder_name 持卡人姓名
        @param zip_code 邮编
        @param usage_count 使用次数
        @param max_usage 最大使用次数
        @param is_active 是否激活
        @return 是否更新成功
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            # 构建动态更新语句
            updates = []
            params = []
            
            if card_number is not None:
                updates.append("card_number = ?")
                params.append(card_number)
            if exp_month is not None:
                updates.append("exp_month = ?")
                params.append(exp_month)
            if exp_year is not None:
                updates.append("exp_year = ?")
                params.append(exp_year)
            if cvv is not None:
                updates.append("cvv = ?")
                params.append(cvv)
            if holder_name is not None:
                updates.append("holder_name = ?")
                params.append(holder_name)
            if zip_code is not None:
                updates.append("zip_code = ?")
                params.append(zip_code)
            if usage_count is not None:
                updates.append("usage_count = ?")
                params.append(int(usage_count))
            if max_usage is not None:
                updates.append("max_usage = ?")
                params.append(int(max_usage))
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if is_active else 0)
            
            if not updates:
                conn.close()
                return False
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(card_id)
            
            sql = f"UPDATE cards SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return affected > 0
    
    # ==================== 设置管理 ====================
    
    @staticmethod
    def get_setting(key, default=None):
        """
        @brief 获取设置值
        @param key 设置键
        @param default 默认值
        @return 设置值
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row['value'] if row else default
    
    @staticmethod
    def set_setting(key, value, description=None):
        """
        @brief 设置值
        @param key 设置键
        @param value 设置值
        @param description 描述
        """
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
        """
        @brief 获取所有设置
        @return 设置字典
        """
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
        """
        @brief 记录操作日志
        @param operation_type 操作类型
        @param target_email 目标邮箱
        @param details 详情
        @param status 状态
        """
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
        """
        @brief 获取最近的操作日志
        @param limit 限制条数
        @return 日志列表
        """
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
        """
        @brief 将数据库导出为传统文本文件，方便查看
        """
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
        """
        @brief 从比特浏览器窗口导入账号
        """
        import threading
        
        def _run_import():
            try:
                # 延迟导入避免循环依赖
                try:
                    from ..google.backend.create_window import get_browser_list, parse_account_line
                except ImportError:
                    # 兼容旧路径
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
                                        
                                        # 总是更新 browser_id（比特浏览器是权威来源）
                                        if row[0] != browser_id:
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
                                            sql = f"UPDATE accounts SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE email = ?"
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
    
    # ==================== 系统设置管理 ====================
    
    @staticmethod
    def get_setting(key: str, default: str = None) -> str:
        """
        @brief 获取设置值
        @param key 设置键名
        @param default 默认值
        @return 设置值
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row['value'] if row else default
    
    @staticmethod
    def set_setting(key: str, value: str, description: str = None):
        """
        @brief 设置值
        @param key 设置键名
        @param value 设置值
        @param description 描述
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value, description))
            conn.commit()
            conn.close()
    
    @staticmethod
    def get_all_settings() -> dict:
        """
        @brief 获取所有设置
        @return 设置字典
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT key, value, description FROM settings")
            rows = cursor.fetchall()
            conn.close()
            return {row['key']: row['value'] for row in rows}
    
    @staticmethod
    def delete_setting(key: str):
        """
        @brief 删除设置
        @param key 设置键名
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
            conn.commit()
            conn.close()
    
    # ==================== 操作日志管理 ====================
    
    @staticmethod
    def add_log(operation_type: str, target_email: str = None, details: str = None, status: str = 'success'):
        """
        @brief 添加操作日志
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO operation_logs (operation_type, target_email, details, status)
                VALUES (?, ?, ?, ?)
            """, (operation_type, target_email, details, status))
            conn.commit()
            conn.close()
    
    @staticmethod
    def get_recent_logs(limit: int = 100) -> list:
        """
        @brief 获取最近日志
        """
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
    
    # ==================== 导出状态管理 ====================
    
    @staticmethod
    def batch_update_exported(emails: list, is_exported: int = 1):
        """
        @brief 批量更新账号导出状态
        @param emails 邮箱列表
        @param is_exported 导出状态（1=已导出，0=未导出）
        @return 更新的数量
        """
        if not emails:
            return 0
        
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            updated = 0
            for email in emails:
                try:
                    cursor.execute("""
                        UPDATE accounts 
                        SET is_exported = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE email = ?
                    """, (is_exported, email))
                    updated += cursor.rowcount
                except Exception:
                    pass
            
            conn.commit()
            conn.close()
            return updated
    
    @staticmethod
    def get_accounts_by_statuses(statuses: list, include_exported: bool = True):
        """
        @brief 按多个状态获取账号
        @param statuses 状态列表
        @param include_exported 是否包含已导出的账号
        @return 账号列表
        """
        if not statuses:
            return []
        
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            placeholders = ','.join(['?' for _ in statuses])
            sql = f"SELECT * FROM accounts WHERE status IN ({placeholders})"
            params = list(statuses)
            
            if not include_exported:
                sql += " AND (is_exported IS NULL OR is_exported = 0)"
            
            sql += " ORDER BY updated_at DESC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

