"""
@file account_manager.py
@brief Google账号状态管理模块
@details 提供账号在不同状态之间转换的功能（只更新数据库，不导出txt）
"""
import sys
import os

# 添加src目录到路径以支持导入core模块
_src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# 尝试从core导入，失败则从旧位置导入
try:
    from core.database import DBManager
except ImportError:
    from database import DBManager

# 确保数据库已初始化
DBManager.init_db()


class AccountManager:
    """
    @class AccountManager
    @brief 账号状态管理器
    @details 管理Google账号在各个状态之间的转换（只更新数据库）
    """
    
    @staticmethod
    def _parse(line):
        """
        @brief 解析账号信息行
        @param line 账号信息行（格式: link----email----password----recovery----secret）
        @return (email, password, recovery, secret, link) 元组
        """
        parts = [p.strip() for p in line.split('----') if p.strip()]
        link = None
        email = None
        pwd = None
        rec = None
        sec = None
        
        # Check URL
        if parts and "http" in parts[0]:
            link = parts[0]
            parts = parts[1:]
            
        # Find email
        for i, p in enumerate(parts):
            if '@' in p and '.' in p:
                email = p
                if i+1 < len(parts): pwd = parts[i+1]
                if i+2 < len(parts): rec = parts[i+2]
                if i+3 < len(parts): sec = parts[i+3]
                break
        
        return email, pwd, rec, sec, link

    @staticmethod
    def save_link(line):
        """
        @brief 保存到 link_ready 状态（有资格待验证已提取链接）
        @param line 账号信息行
        """
        print(f"[AM] save_link 调用, line: {line[:100] if line else 'None'}...")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='link_ready')
        else:
            print(f"[AM] save_link: 无法解析邮箱，跳过")

    @staticmethod
    def move_to_verified(line):
        """
        @brief 移动到 verified 状态（已验证未绑卡）
        @param line 账号信息行
        """
        print(f"[AM] move_to_verified 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='verified')

    @staticmethod
    def move_to_ineligible(line):
        """
        @brief 移动到 ineligible 状态（无资格）
        @param line 账号信息行
        """
        print(f"[AM] move_to_ineligible 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='ineligible')
        else:
            print(f"[AM] move_to_ineligible: 无法解析邮箱，跳过")

    @staticmethod
    def move_to_error(line):
        """
        @brief 移动到 error 状态（超时或其他错误）
        @param line 账号信息行
        """
        print(f"[AM] move_to_error 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='error')
        else:
            print(f"[AM] move_to_error: 无法解析邮箱，跳过")

    @staticmethod
    def move_to_subscribed(line):
        """
        @brief 移动到 subscribed 状态（已绑卡订阅）
        @param line 账号信息行
        """
        print(f"[AM] move_to_subscribed 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='subscribed')
            
    @staticmethod
    def remove_from_file_unsafe(file_key, line_or_email):
        """
        @brief 从文件中移除（兼容旧接口，现在是空操作）
        @param file_key 文件键
        @param line_or_email 行内容或邮箱
        """
        # No-op with DB approach, handled by status update
        pass

