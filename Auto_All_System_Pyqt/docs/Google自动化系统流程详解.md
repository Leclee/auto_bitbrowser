# Google自动化系统流程详解

## 概述

本系统实现了Google学生账号的完全自动化处理流程，包括登录验证、资格检测、SheerID验证、绑卡订阅等完整链路。系统采用模块化设计，支持单步执行和一键全自动处理。

## 系统架构

```mermaid
graph TB
    A[用户界面] --> B[Google登录服务]
    A --> C[SheerLink提取服务] 
    A --> D[SheerID验证器]
    A --> E[绑卡订阅服务]
    A --> F[一键全自动服务]
    
    B --> G[Google认证核心]
    C --> G
    D --> H[SheerID API]
    E --> I[Google One API]
    F --> B
    F --> C
    F --> D
    F --> E
    
    J[比特浏览器API] --> B
    J --> C
    J --> E
    J --> F
    
    K[数据库管理] --> B
    K --> C  
    K --> D
    K --> E
    K --> F
```

## 核心模块说明

### 1. Google认证核心 (google_auth.py)

**主要功能：**
- 智能登录状态检测
- 统一的Google登录流程
- 2FA和辅助邮箱验证

**核心函数：**
- `get_login_state()`: 检测当前登录状态
- `google_login()`: 执行登录流程

### 2. Google登录服务 (google_login_service.py)

**主要功能：**
- 封装完整的登录服务
- 比特浏览器集成
- 批量登录状态检测

### 3. SheerLink提取服务 (sheerlink_service.py)

**主要功能：**
- Google One学生资格检测
- SheerID验证链接提取
- 账号状态分类管理

### 4. SheerID验证器 (sheerid_verifier.py)

**主要功能：**
- 批量SheerID验证
- API状态轮询
- CSRF token管理

### 5. 绑卡订阅服务 (bind_card_service.py)

**主要功能：**
- 自动绑定测试卡
- Google One订阅处理
- iframe支付表单操作

### 6. 一键全自动服务 (all_in_one_service.py)

**主要功能：**
- 整合所有处理流程
- 状态检测与流转
- 错误处理与重试

## 详细流程图

### 一键全自动处理流程

```mermaid
flowchart TD
    Start([开始一键处理]) --> GetBrowser[获取浏览器信息]
    GetBrowser --> GetAccount[获取账号信息]
    GetAccount --> GetCard[获取卡片信息]
    GetCard --> OpenBrowser[打开比特浏览器]
    
    OpenBrowser --> ConnectPW[连接Playwright]
    ConnectPW --> CheckLogin{检查登录状态}
    
    CheckLogin -->|未登录| DoLogin[执行登录流程]
    CheckLogin -->|已登录| CheckStatus[检测资格状态]
    
    DoLogin --> LoginSuccess{登录成功？}
    LoginSuccess -->|是| CheckStatus
    LoginSuccess -->|否| LoginFailed[登录失败]
    
    CheckStatus --> StatusResult{检测结果}
    
    StatusResult -->|已订阅+已解锁| Subscribed_AG[subscribed_antigravity]
    StatusResult -->|已订阅| Subscribed[subscribed]
    StatusResult -->|已验证未绑卡| Verified[verified]
    StatusResult -->|有资格待验证| LinkReady[link_ready]
    StatusResult -->|无资格| Ineligible[ineligible]
    
    Verified --> BindCard[绑卡订阅流程]
    BindCard --> BindResult{绑卡结果}
    BindResult -->|成功| Subscribed
    BindResult -->|失败| VerifiedFailed[verified状态保持]
    
    LinkReady --> HasAPIKey{有API Key？}
    HasAPIKey -->|是| ExtractVID[提取验证ID]
    HasAPIKey -->|否| LinkReadyEnd[link_ready状态结束]
    
    ExtractVID --> CallSheerAPI[调用SheerID API]
    CallSheerAPI --> APIResult{API验证结果}
    
    APIResult -->|成功| ReloadPage[重新加载页面]
    APIResult -->|失败| APIFailed[验证失败]
    
    ReloadPage --> RecheckStatus[重新检测状态]
    RecheckStatus --> NewStatus{新状态}
    
    NewStatus -->|verified| BindCard
    NewStatus -->|其他| StatusUpdated[状态已更新]
    
    Subscribed_AG --> End([处理完成])
    Subscribed --> End
    VerifiedFailed --> End
    LinkReadyEnd --> End
    APIFailed --> End
    StatusUpdated --> End
    Ineligible --> End
    LoginFailed --> End
```

### Google登录流程详解

```mermaid
flowchart TD
    StartLogin([开始登录]) --> CheckState[智能检测页面状态]
    
    CheckState --> StateResult{检测结果}
    
    StateResult -->|已登录| CheckEmail{邮箱匹配？}
    StateResult -->|未登录| FillEmail[填写邮箱]
    StateResult -->|未知状态| GoToLogin[跳转登录页]
    
    CheckEmail -->|匹配| LoginSuccess[登录成功]
    CheckEmail -->|不匹配| SwitchAccount[需要切换账号]
    
    GoToLogin --> CheckState
    
    FillEmail --> ClickNext[点击下一步]
    ClickNext --> WaitPassword[等待密码框]
    
    WaitPassword --> PasswordAppear{密码框出现？}
    PasswordAppear -->|是| FillPassword[填写密码]
    PasswordAppear -->|否-账号不存在| AccountNotFound[账号不存在]
    PasswordAppear -->|否-超时| PasswordTimeout[密码框超时]
    
    FillPassword --> ClickPasswordNext[点击密码下一步]
    ClickPasswordNext --> WaitResult[等待登录结果]
    
    WaitResult --> CheckVerification{需要验证？}
    
    CheckVerification -->|需要2FA| Handle2FA[处理2FA验证]
    CheckVerification -->|需要辅助邮箱| HandleBackup[处理辅助邮箱]
    CheckVerification -->|密码错误| PasswordError[密码错误]
    CheckVerification -->|登录成功| LoginSuccess
    CheckVerification -->|需要跳过弹窗| HandlePopup[处理弹窗]
    
    Handle2FA --> Generate2FA[生成2FA代码]
    Generate2FA --> Input2FA[输入2FA代码]
    Input2FA --> WaitResult
    
    HandleBackup --> InputBackup[输入辅助邮箱]
    InputBackup --> WaitResult
    
    HandlePopup --> ClickSkip[点击跳过按钮]
    ClickSkip --> WaitResult
    
    LoginSuccess --> End([登录流程结束])
    SwitchAccount --> End
    AccountNotFound --> End  
    PasswordTimeout --> End
    PasswordError --> End
```

### 资格检测流程

```mermaid
flowchart TD
    StartCheck([开始资格检测]) --> NavToPage[导航到Google One页面]
    NavToPage --> WaitLoad[等待页面加载]
    WaitLoad --> SetupListener[设置API监听器]
    
    SetupListener --> WaitElements[智能等待页面元素]
    WaitElements --> CheckElements{检测到的元素}
    
    CheckElements -->|Get Offer按钮| ClickOffer[点击Get Offer]
    CheckElements -->|Subscribed文字| AlreadySub[已订阅状态]
    CheckElements -->|Not Available| NotEligible[无资格状态]
    CheckElements -->|Loading/其他| ContinueWait[继续等待]
    
    ClickOffer --> WaitResponse[等待API响应]
    ContinueWait --> WaitElements
    
    WaitResponse --> APIResponse{API响应内容}
    
    APIResponse -->|包含SheerID链接| ExtractLink[提取验证链接]
    APIResponse -->|显示付款页面| ShowPayment[显示付款选项]
    APIResponse -->|错误响应| ErrorResponse[API错误]
    
    ExtractLink --> LinkReady[link_ready状态]
    ShowPayment --> Verified[verified状态]
    AlreadySub --> CheckAntigravity[检查Antigravity状态]
    NotEligible --> Ineligible[ineligible状态]
    ErrorResponse --> Error[error状态]
    
    CheckAntigravity --> AntigravityCheck{有Antigravity？}
    AntigravityCheck -->|是| SubscribedAG[subscribed_antigravity状态]
    AntigravityCheck -->|否| Subscribed[subscribed状态]
    
    LinkReady --> End([检测完成])
    Verified --> End
    Ineligible --> End
    Error --> End
    SubscribedAG --> End
    Subscribed --> End
```

### SheerID验证流程

```mermaid
flowchart TD
    StartVerify([开始SheerID验证]) --> GetCSRF[获取CSRF Token]
    GetCSRF --> CSRFResult{Token获取结果}
    
    CSRFResult -->|成功| PreparePayload[准备验证载荷]
    CSRFResult -->|失败| TryWithoutCSRF[尝试无Token验证]
    
    PreparePayload --> SendBatchRequest[发送批量验证请求]
    TryWithoutCSRF --> SendBatchRequest
    
    SendBatchRequest --> RequestResult{请求结果}
    
    RequestResult -->|成功| ParseSSE[解析SSE流]
    RequestResult -->|Token过期| RefreshToken[刷新Token]
    RequestResult -->|其他错误| RequestError[请求错误]
    
    RefreshToken --> SendBatchRequest
    
    ParseSSE --> SSEData{SSE数据类型}
    
    SSEData -->|pending + checkToken| StartPolling[开始轮询]
    SSEData -->|success| VerifySuccess[验证成功]
    SSEData -->|error| VerifyError[验证失败]
    
    StartPolling --> PollLoop[轮询状态检查]
    PollLoop --> PollResult{轮询结果}
    
    PollResult -->|success| VerifySuccess
    PollResult -->|error| VerifyError  
    PollResult -->|pending| PollContinue[继续轮询]
    PollResult -->|timeout| PollTimeout[轮询超时]
    
    PollContinue --> PollLoop
    
    VerifySuccess --> End([验证完成])
    VerifyError --> End
    RequestError --> End
    PollTimeout --> End
```

### 绑卡订阅流程

```mermaid
flowchart TD
    StartBind([开始绑卡流程]) --> GetCardInfo[获取卡片信息]
    GetCardInfo --> CardSource{卡片来源}
    
    CardSource -->|数据库| DBCard[从数据库获取]
    CardSource -->|参数传入| ParamCard[使用传入卡片]
    CardSource -->|无可用卡| NoCard[无可用卡片]
    
    DBCard --> FindOfferBtn[查找Get Offer按钮]
    ParamCard --> FindOfferBtn
    NoCard --> End([绑卡结束])
    
    FindOfferBtn --> OfferBtnResult{按钮状态}
    
    OfferBtnResult -->|找到按钮| ClickOfferBtn[点击Get Offer]
    OfferBtnResult -->|已在付款页| CheckPaymentPage[检查付款页面]
    
    ClickOfferBtn --> CheckPaymentPage
    
    CheckPaymentPage --> PaymentElements{页面元素检测}
    
    PaymentElements -->|Subscribe按钮| AlreadyBound[已绑卡直接订阅]
    PaymentElements -->|Add Card按钮| NeedAddCard[需要添加卡片]
    PaymentElements -->|未找到元素| PaymentError[付款页面错误]
    
    AlreadyBound --> ClickSubscribe[点击Subscribe]
    
    NeedAddCard --> ClickAddCard[点击Add Card]
    ClickAddCard --> WaitCardForm[等待卡片输入框]
    
    WaitCardForm --> CheckIframe{检测iframe结构}
    
    CheckIframe -->|双层iframe| UseInnerFrame[使用内层iframe]
    CheckIframe -->|单层iframe| UseOuterFrame[使用外层iframe]
    
    UseInnerFrame --> FillCardInfo[填写卡片信息]
    UseOuterFrame --> FillCardInfo
    
    FillCardInfo --> FillSteps[分步填写]
    FillSteps --> FillCardNumber[填写卡号]
    FillCardNumber --> FillExpiry[填写过期日期]
    FillExpiry --> FillCVV[填写CVV]
    
    FillCVV --> ClickSave[点击Save Card]
    ClickSave --> WaitSubscribeBtn[等待Subscribe按钮]
    
    WaitSubscribeBtn --> ClickSubscribe
    ClickSubscribe --> CheckSubscription[检查订阅状态]
    
    CheckSubscription --> SubResult{订阅结果}
    
    SubResult -->|检测到Subscribed| SubscribeSuccess[订阅成功]
    SubResult -->|未检测到但流程完成| BindComplete[绑卡完成]
    SubResult -->|检测异常| BindCompleteWithWarning[绑卡完成-状态检查异常]
    
    SubscribeSuccess --> UpdateDB[更新数据库状态]
    BindComplete --> UpdateDB
    BindCompleteWithWarning --> UpdateDB
    PaymentError --> End
    
    UpdateDB --> End
```

## 技术实现细节

### 1. 智能等待机制

系统使用Playwright的`.or()`方法实现智能等待：

```python
# 示例：智能等待多个可能的元素
avatar_button = page.get_by_role("button", name=re.compile(r"^Google (Account|帐号|账号)"))
avatar_link = page.get_by_role("link", name=re.compile(r"^Google (Account|帐号|账号)"))
email_input = page.locator('input[type="email"]')

combined = avatar_button.or_(avatar_link).or_(email_input)
await expect(combined).to_be_visible(timeout=timeout)
```

### 2. API拦截机制

通过监听网络请求获取SheerID链接：

```python
# 设置请求监听器
async def handle_request(request):
    if 'sheerid' in request.url and 'verify' in request.url:
        # 提取验证链接
        pass

page.on('request', handle_request)
```

### 3. iframe嵌套处理

绑卡流程中需要处理多层iframe：

```python
# 检测iframe结构
iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
inner_iframe = iframe_locator.frame_locator('iframe[name="hnyNZeIframe"]')

# 智能选择合适的iframe
if await inner_iframe.locator('input').count() > 0:
    active_iframe = inner_iframe
else:
    active_iframe = iframe_locator
```

### 4. 状态管理

系统定义了完整的状态转换：

```python
STATUS_PENDING = 'pending_check'          # ❔待检测
STATUS_NOT_LOGGED_IN = 'not_logged_in'    # 🔒未登录  
STATUS_INELIGIBLE = 'ineligible'          # ❌无资格
STATUS_LINK_READY = 'link_ready'          # 🔗待验证
STATUS_VERIFIED = 'verified'              # ✅已验证
STATUS_SUBSCRIBED = 'subscribed'          # 👑已订阅
STATUS_SUBSCRIBED_ANTIGRAVITY = 'subscribed_antigravity'  # 🌟已解锁
STATUS_ERROR = 'error'                    # ⚠️错误
```

### 5. 错误处理与重试

- 网络请求自动重试机制
- CSRF Token过期自动刷新  
- 页面加载超时处理
- 元素定位失败降级处理

### 6. 并发控制

- 支持多线程批量处理
- 线程池控制并发数量
- 停止信号检测机制
- 资源自动清理

## 配置说明

### 数据库配置

系统需要以下数据库表：
- `accounts`: 存储账号信息
- `cards`: 存储卡片信息  
- `settings`: 存储API密钥等配置
- `browser_info`: 存储浏览器窗口信息

### API配置

- **SheerID API Key**: 用于学生验证
- **比特浏览器API**: 用于浏览器控制
- **Google API**: 间接通过页面操作使用

### 超时配置

```python
DEFAULT_TIMEOUT = 15000  # 默认15秒
NAVIGATION_TIMEOUT = 30000  # 页面导航30秒
POLLING_TIMEOUT = 120000  # API轮询2分钟
```

## 状态码说明

| 状态码 | 显示名称 | 说明 | 后续操作 |
|--------|----------|------|----------|
| `pending_check` | ❔待检测 | 初始状态 | 执行检测 |
| `not_logged_in` | 🔒未登录 | 需要登录 | 执行登录 |
| `ineligible` | ❌无资格 | 无学生资格 | 无法继续 |
| `link_ready` | 🔗待验证 | 有验证链接 | SheerID验证 |
| `verified` | ✅已验证 | 验证通过 | 绑卡订阅 |
| `subscribed` | 👑已订阅 | 订阅成功 | 检查功能 |
| `subscribed_antigravity` | 🌟已解锁 | 完全激活 | 流程完成 |
| `error` | ⚠️错误 | 处理异常 | 重试或跳过 |

## 使用示例

### 单步使用

```python
# 1. 仅登录
from google.backend.google_login_service import login_google_account
success, status, msg = login_google_account("browser_id_123")

# 2. 仅提取SheerLink  
from google.backend.sheerlink_service import process_browser
success, msg = process_browser("browser_id_123")

# 3. 仅验证SheerID
from google.backend.sheerid_verifier import SheerIDVerifier
verifier = SheerIDVerifier("your_api_key")
results = verifier.verify_batch(["verification_id_123"])

# 4. 仅绑卡订阅
from google.backend.bind_card_service import process_bind_card  
success, msg = process_bind_card("browser_id_123")
```

### 一键全自动

```python
from google.backend.all_in_one_service import process_all_in_one

success, final_status, message = process_all_in_one(
    browser_id="browser_id_123",
    api_key="your_sheerid_api_key",  # 可选，为空则从数据库获取
    card_info=None,  # 可选，为空则从数据库获取
    log_callback=print  # 可选，日志回调函数
)

print(f"处理结果: {success}")
print(f"最终状态: {final_status}") 
print(f"消息: {message}")
```

## 注意事项

1. **浏览器兼容性**: 系统基于Chromium内核，确保比特浏览器版本兼容
2. **网络环境**: 需要稳定的网络连接，建议使用代理
3. **API限制**: SheerID API有频率限制，注意控制并发数量
4. **卡片信息**: 确保测试卡信息正确且有效
5. **状态同步**: 多线程处理时注意数据库状态同步
6. **日志记录**: 详细的日志有助于问题诊断和流程优化

## 故障排除

### 常见问题

1. **登录失败**
   - 检查账号密码是否正确
   - 确认2FA密钥有效性
   - 验证辅助邮箱设置

2. **资格检测超时**
   - 检查网络连接
   - 确认页面加载完成
   - 增加超时时间设置

3. **SheerID验证失败**
   - 验证API Key有效性
   - 检查CSRF Token获取
   - 确认验证ID格式正确

4. **绑卡失败**
   - 检查卡片信息完整性
   - 确认iframe结构变化
   - 验证页面元素定位

5. **状态异常**
   - 检查数据库连接
   - 确认状态更新逻辑
   - 验证并发处理机制

---

*最后更新: 2026-01-22*
