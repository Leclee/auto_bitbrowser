from database import DBManager

DBManager.init_db()

class AccountManager:
    @staticmethod
    def _parse(line):
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
        """保存到 link_ready 状态（有资格待验证已提取链接）"""
        print(f"[AM] save_link 调用, line: {line[:100] if line else 'None'}...")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='link_ready')
            DBManager.export_to_files()
        else:
            print(f"[AM] save_link: 无法解析邮箱，跳过")

    @staticmethod
    def move_to_verified(line):
        """移动到 verified 状态（已验证未绑卡）- 保存完整字段"""
        print(f"[AM] move_to_verified 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            # 使用 upsert 而不是 update_status，确保保存所有字段
            DBManager.upsert_account(email, pwd, rec, sec, link, status='verified')
            DBManager.export_to_files()

    @staticmethod
    def move_to_ineligible(line):
        """移动到 ineligible 状态（无资格）"""
        print(f"[AM] move_to_ineligible 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='ineligible')
            DBManager.export_to_files()
        else:
            print(f"[AM] move_to_ineligible: 无法解析邮箱，跳过")

    @staticmethod
    def move_to_error(line):
        """移动到 error 状态（超时或其他错误）"""
        print(f"[AM] move_to_error 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='error')
            DBManager.export_to_files()
        else:
            print(f"[AM] move_to_error: 无法解析邮箱，跳过")

    @staticmethod
    def move_to_subscribed(line):
        """移动到 subscribed 状态（已绑卡订阅）"""
        print(f"[AM] move_to_subscribed 调用")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='subscribed')
            DBManager.export_to_files()
            
    @staticmethod
    def remove_from_file_unsafe(file_key, line_or_email):
        # No-op with DB approach, handled by status update
        pass
