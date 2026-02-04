# _legacy 目录说明

此目录包含重构前的原始Python文件，保留供参考和兼容性。

## 文件迁移状态

| 文件名 | 说明 | 新位置 | 状态 |
|--------|------|--------|------|
| `account_manager.py` | 账号状态管理 | `google/backend/account_manager.py` | ✅ 已迁移 |
| `auto_all_in_one_gui.py` | 一键全自动GUI | - | ⏳ 待迁移 |
| `auto_bind_card.py` | 自动绑卡逻辑 | - | ⏳ 待迁移 |
| `bind_card_gui.py` | 绑卡GUI | `google/frontend/bind_card_gui.py` | ✅ 已迁移 |
| `bit_api.py` | 比特浏览器简化API | `core/bit_api.py` | ✅ 已迁移 |
| `bit_playwright.py` | Playwright封装 | `core/bit_playwright.py` | ✅ 已迁移 |
| `bitbrowser_api.py` | 比特浏览器完整API | `core/bitbrowser_api.py` | ✅ 已迁移 |
| `create_window.py` | 浏览器窗口创建 | - | ⏳ 待迁移 |
| `create_window_gui.py` | 主窗口GUI | `gui/main_window.py` | ✅ 已迁移（框架） |
| `database.py` | 数据库管理 | `core/database.py` | ✅ 已迁移 |
| `migrate_txt_to_db.py` | TXT迁移工具 | - | 🗑️ 不再需要 |
| `run_playwright_google.py` | Google自动化 | `google/backend/google_auth.py` | ✅ 部分迁移 |
| `sheerid_gui.py` | SheerID验证GUI | `google/frontend/sheerid_gui.py` | ✅ 已迁移 |
| `sheerid_verifier.py` | SheerID验证器 | `google/backend/sheerid_verifier.py` | ✅ 已迁移 |

## 新增模块

| 模块 | 位置 | 说明 |
|------|------|------|
| `google_auth.py` | `google/backend/` | Google登录状态检测 |
| `google_login_service.py` | `google/backend/` | Google登录服务 |
| `base_window.py` | `gui/` | GUI基础窗口类（公共模块） |
| `main_window.py` | `gui/` | 主窗口框架（多业务） |

## 注意事项

1. 已迁移的模块**仍保留在此目录**，供旧代码兼容使用
2. 新代码应**优先使用新位置**的模块
3. 重构完全完成后，可以考虑删除此目录

---
*最后更新: 2026-01-21*
