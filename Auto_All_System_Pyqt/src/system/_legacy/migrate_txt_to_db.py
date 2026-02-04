import os
import sys
from database import DBManager
from account_manager import AccountManager

# 确保路径正确
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)

FILES_MAP = {
    "link": ("sheerIDlink.txt", "link_ready"),
    "verified": ("已验证未绑卡.txt", "verified"),
    "subscribed": ("已绑卡号.txt", "subscribed"),
    "ineligible": ("无资格号.txt", "ineligible"),
    "error": ("超时或其他错误.txt", "error"),
    "pending": ("有资格待验证号.txt", "pending")
}

def migrate():
    print("开始从文本文件迁移数据到数据库...")
    DBManager.init_db()
    
    total_count = 0
    
    for key, (filename, status) in FILES_MAP.items():
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            print(f"文件不存在，跳过: {filename}")
            continue
            
        print(f"正在处理: {filename} (状态: {status})...")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            
            count = 0
            for line in lines:
                # 使用 AccountManager 的解析逻辑
                email, pwd, rec, sec, link = AccountManager._parse(line)
                if email:
                    # 插入数据库
                    DBManager.upsert_account(email, pwd, rec, sec, link, status=status)
                    count += 1
            
            print(f"  -> 成功导入 {count} 条数据")
            total_count += count
            
        except Exception as e:
            print(f"  -> 处理失败: {e}")

    print("-" * 30)
    print(f"迁移完成! 共导入 {total_count} 个账号。")
    print("现在正在重新导出以验证...")
    DBManager.export_to_files()
    print("验证导出完成。")

if __name__ == "__main__":
    migrate()
