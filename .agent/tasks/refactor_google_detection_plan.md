# Google 登录与资格检测重构计划

## 📋 概述

完全重构 Google 登录状态判断和资格状态判断方式，采用更可靠的检测机制：
1. **登录检测**：通过页面头像元素判断
2. **资格检测**：通过拦截 API 响应判断（消除文本检测的不稳定性）
3. **智能等待**：使用 Playwright Auto-waiting 机制，消除手动 sleep

---

## 🔐 Part 1: 登录状态检测重构

### 目标
访问 `https://accounts.google.com/` 后，通过检测左上角头像按钮判断登录状态。

### 检测逻辑
```python
# 已登录标志: 存在头像按钮
avatar_selector = 'a.gb_B[role="button"] img.gbii'

# 或者更宽松的选择器
avatar_selector = 'a[aria-label*="Google Account"]'
```

### 新函数设计
```python
async def check_google_login_by_avatar(page: Page, timeout: float = 10.0) -> bool:
    """
    通过检测头像按钮判断是否已登录
    @return True=已登录, False=未登录
    """
    try:
        # 导航到 Google 账号页面
        await page.goto("https://accounts.google.com/", wait_until="domcontentloaded")
        
        # 使用 Playwright 智能等待检测头像
        avatar_locator = page.locator('a[aria-label*="Google Account"] img')
        
        # expect 会自动重试直到条件满足或超时
        try:
            await expect(avatar_locator).to_be_visible(timeout=timeout * 1000)
            return True  # 头像可见 = 已登录
        except:
            return False  # 超时 = 未登录
    except Exception as e:
        return False
```

---

## 🎓 Part 2: 资格状态检测重构

### 目标
访问 `https://one.google.com/ai-student?g1_landing_page=75` 后：
1. 拦截 `GI6Jdd` API 响应判断订阅状态
2. 通过 `jsname` 属性判断验证状态

### API 响应解析
**请求标识**: `rpcids=GI6Jdd`

**响应格式**:
```
)]}'
170
[["wrb.fr","GI6Jdd","[[null,null,\"US\",null,null,\"2 TB\",null,\"0\",\"Antigravity\"]]",...]]
```

**状态判断逻辑**:
| 响应内容 | 状态 | 数据库状态 |
|---------|------|-----------|
| 含 "2 TB" + "Antigravity" | 已订阅+已解锁 | `subscribed_antigravity` |
| 含 "2 TB" 不含 "Antigravity" | 已订阅未解锁 | `subscribed` |
| 无响应或无 "2 TB" | 未订阅 | 继续检测页面元素 |

### 页面元素检测（如果未订阅）
| jsname 属性 | 含义 | 数据库状态 |
|------------|------|-----------|
| `jsname="hSRGPd"` | 有资格待验证 | `link_ready` |
| `jsname="V67aGc"` | 已验证未绑卡 | `verified` |
| 其他 | 无资格 | `ineligible` |

### 新函数设计
```python
async def check_google_one_status_v2(page: Page, timeout: float = 15.0) -> Tuple[str, Optional[str]]:
    """
    通过 API 拦截 + jsname 属性检测资格状态
    @return (status, sheerid_link)
            status: 'subscribed_antigravity' | 'subscribed' | 'verified' | 'link_ready' | 'ineligible'
    """
    api_response_data = None
    
    # 定义响应拦截器
    async def handle_response(response):
        nonlocal api_response_data
        if 'rpcids=GI6Jdd' in response.url:
            try:
                text = await response.text()
                api_response_data = text
            except:
                pass
    
    page.on("response", handle_response)
    
    try:
        # 导航到目标页面
        await page.goto(
            "https://one.google.com/ai-student?g1_landing_page=75",
            wait_until="domcontentloaded"
        )
        
        # 等待 API 响应或页面元素
        await page.wait_for_load_state("networkidle", timeout=timeout * 1000)
        
        # 分析 API 响应
        if api_response_data:
            if '2 TB' in api_response_data or '2TB' in api_response_data:
                if 'Antigravity' in api_response_data:
                    return 'subscribed_antigravity', None
                else:
                    return 'subscribed', None
        
        # 检测页面元素判断状态
        # 1. 检查 hSRGPd (有资格待验证)
        link_ready_locator = page.locator('[jsname="hSRGPd"]')
        if await link_ready_locator.count() > 0:
            # 提取 SheerID 链接
            sheerid_link = await _extract_sheerid_link(page)
            return 'link_ready', sheerid_link
        
        # 2. 检查 V67aGc (已验证未绑卡)
        verified_locator = page.locator('[jsname="V67aGc"]')
        if await verified_locator.count() > 0:
            return 'verified', None
        
        # 3. 其他情况 = 无资格
        return 'ineligible', None
        
    finally:
        page.remove_listener("response", handle_response)
```

---

## ⏱️ Part 3: 智能等待策略

### 替换规则
| 旧写法 | 新写法 |
|-------|--------|
| `await asyncio.sleep(3)` | `await page.wait_for_load_state("domcontentloaded")` |
| `await asyncio.sleep(5)` | `await page.wait_for_load_state("networkidle")` |
| 等待元素出现再操作 | 直接 `locator.click()` (自带等待) |
| 检查元素是否存在 | `await expect(locator).to_be_visible()` |
| 等待 API 响应 | `page.wait_for_response()` |

### Playwright 智能等待机制
```python
# 操作前自动检查 (Actionability Checks)
# - Attached: 元素存在于 DOM
# - Visible: 元素可见
# - Stable: 元素静止（无动画）
# - Receives Events: 未被遮挡
# - Enabled: 未禁用

# 直接操作，Playwright 自动等待
await page.locator('button.submit').click()

# 断言自动重试
await expect(page.locator('.success')).to_be_visible()
```

---

## 📁 文件修改清单

### 1. `google/backend/google_auth.py`
- [x] 新增 `check_google_login_by_avatar()` 函数
- [x] 新增 `check_google_one_status_v2()` 函数
- [x] 移除所有手动 `asyncio.sleep()` 调用
- [x] 更新 `ensure_google_login()` 使用新检测逻辑

### 2. `core/database.py`
- [x] 账号状态增加 `subscribed_antigravity` 类型

### 3. `gui/main_window.py`
- [x] 状态显示映射增加 `subscribed_antigravity`: '🌟已解锁'

### 4. 服务层调用更新
- `google/backend/sheerlink_service.py`
- `google/backend/bind_card_service.py`
- `google/backend/all_in_one_service.py`

---

## 🔄 执行步骤

1. **创建新的检测模块** `google/backend/google_detector.py`
2. **实现登录检测** `check_google_login_by_avatar()`
3. **实现资格检测** `check_google_one_status_v2()`
4. **更新数据库状态类型**
5. **更新 UI 状态显示**
6. **替换旧调用**
7. **测试验证**

---

## ✅ 验收标准

1. 登录检测准确率 > 99%
2. 资格检测准确率 > 99%
3. 无手动 sleep 调用
4. 所有状态正确映射到数据库
5. UI 正确显示所有状态类型
