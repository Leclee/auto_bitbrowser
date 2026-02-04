# Web 服务架构图

## 1. 整体架构

```mermaid
graph TB
    subgraph "Web Frontend (browser)"
        HTML[index.html]
        JS[app.js]
        CSS[style.css]
    end
    
    subgraph "Web Server (server.py)"
        API[APIHandler]
        subgraph "API Endpoints"
            ACC_API["/api/accounts/*"]
            SHEER_API["/api/sheerlink/*"]
            BIND_API["/api/bindcard/*"]
            AUTO_API["/api/auto/*"]
            TASK_API["/api/task/*"]
        end
    end
    
    subgraph "Task Management"
        TM[task_manager.py<br/>_tasks Dict]
        AIO_TM[all_in_one_service.py<br/>_batch_task_status Dict]
    end
    
    subgraph "Backend Services (google/backend)"
        SLS[sheerlink_service.py]
        BCS[bind_card_service.py]
        AIOS[all_in_one_service.py]
        GA[google_auth.py]
        SV[sheerid_verifier.py]
    end
    
    subgraph "Core Modules"
        DB[(DBManager)]
        BIT[bit_api.py]
    end
    
    HTML --> JS
    JS --> API
    
    API --> ACC_API
    API --> SHEER_API
    API --> BIND_API
    API --> AUTO_API
    API --> TASK_API
    
    SHEER_API --> TM
    BIND_API --> TM
    AUTO_API --> AIO_TM
    TASK_API --> TM
    
    TM --> SLS
    TM --> BCS
    AIO_TM --> AIOS
    
    AIOS --> GA
    AIOS --> SV
    AIOS --> BCS
    SLS --> GA
    
    GA --> BIT
    BCS --> BIT
    SLS --> BIT
    
    SLS --> DB
    BCS --> DB
    AIOS --> DB
    API --> DB
```

## 2. 发现的问题

### 问题1: 两套任务管理机制不统一

```mermaid
graph LR
    subgraph "task_manager.py"
        TM_TASKS[_tasks: Dict]
        TM_GET[get_task_status]
        TM_STOP[stop_task]
    end
    
    subgraph "all_in_one_service.py"
        AIO_TASKS[_batch_task_status: Dict]
        AIO_GET[get_batch_task_status]
        AIO_STOP[stop_batch_task]
    end
    
    SHEER["/api/sheerlink/*"] --> TM_TASKS
    BIND["/api/bindcard/*"] --> TM_TASKS
    TASK["/api/task/*"] --> TM_TASKS
    
    AUTO["/api/auto/*"] --> AIO_TASKS
    
    TM_GET -.- TM_TASKS
    TM_STOP -.- TM_TASKS
    AIO_GET -.- AIO_TASKS
    AIO_STOP -.- AIO_TASKS
```

**问题**: 
- SheerLink/绑卡任务使用 `task_manager._tasks`
- 全自动处理任务使用 `all_in_one_service._batch_task_status`
- `/api/task/status` 只能查询前者，无法查询全自动任务

### 问题2: 返回类型不匹配

```python
# task_manager.py 第 171 行
def start_auto_process_task(...) -> TaskStatus:  # 声明返回 TaskStatus
    return start_batch_task(...)  # 实际返回 Dict ❌
```

### 问题3: API 端点混乱

| 功能 | 启动 | 状态 | 停止 |
|------|------|------|------|
| SheerLink | `/api/sheerlink/start` | `/api/task/status` | `/api/task/stop` |
| 绑卡 | `/api/bindcard/start` | `/api/task/status` | `/api/task/stop` |
| 全自动 | `/api/auto/start` | `/api/auto/status` | `/api/auto/stop` |

**问题**: 全自动处理使用独立的 API 路径，与其他任务不一致

## 3. 各功能调用流程

### 3.1 SheerLink 提取流程

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant API as server.py
    participant TM as task_manager
    participant SLS as sheerlink_service
    participant GA as google_auth
    participant BIT as bit_api
    participant DB as Database
    
    UI->>API: POST /api/sheerlink/start
    API->>TM: start_sheerlink_task(browser_ids)
    TM->>TM: create_task('sheerlink')
    TM->>SLS: extract_sheerlink_batch()
    
    loop 每个浏览器
        SLS->>BIT: openBrowser(browser_id)
        BIT-->>SLS: page
        SLS->>GA: check_google_one_status(page)
        GA-->>SLS: (status, sheer_link)
        SLS->>DB: update_account_status()
        SLS-->>TM: callback(browser_id, success, msg)
    end
    
    TM-->>API: task
    API-->>UI: {success, task_id}
    
    loop 轮询状态
        UI->>API: POST /api/task/status
        API->>TM: get_task_status(task_id)
        TM-->>API: status_dict
        API-->>UI: {status, logs, progress}
    end
```

### 3.2 绑卡订阅流程

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant API as server.py
    participant TM as task_manager
    participant BCS as bind_card_service
    participant BIT as bit_api
    participant DB as Database
    
    UI->>API: POST /api/bindcard/start
    API->>TM: start_bindcard_task(browser_ids)
    TM->>TM: create_task('bindcard')
    TM->>BCS: process_bind_card_batch()
    
    loop 每个浏览器
        BCS->>BIT: openBrowser(browser_id)
        BCS->>BCS: navigate_to_google_one()
        BCS->>BCS: click_get_offer()
        BCS->>BCS: enter_iframe_and_fill_card()
        BCS->>DB: update_account_status('subscribed')
        BCS-->>TM: callback(browser_id, success, msg)
    end
    
    TM-->>API: task
    API-->>UI: {success, task_id}
```

### 3.3 一键全自动处理流程

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant API as server.py
    participant AIO as all_in_one_service
    participant GA as google_auth
    participant SV as sheerid_verifier
    participant BCS as bind_card_service
    participant DB as Database
    
    UI->>API: POST /api/auto/start
    API->>AIO: start_batch_task(browser_ids)
    AIO->>AIO: 初始化 _batch_task_status
    
    loop 每个浏览器
        AIO->>AIO: process_all_in_one(browser_id)
        
        Note over AIO: Step 1: 检测登录
        AIO->>GA: get_login_state(page)
        
        alt 未登录
            Note over AIO: Step 2: 执行登录
            AIO->>GA: google_login(page, credentials)
        end
        
        Note over AIO: Step 3: 检测资格
        AIO->>GA: detect_eligibility_status(page)
        
        alt 状态为 link_ready
            Note over AIO: Step 4: SheerID验证
            AIO->>SV: verify(verification_id)
        end
        
        alt 状态为 verified
            Note over AIO: Step 5: 绑卡订阅
            AIO->>BCS: auto_bind_card(page)
        end
        
        AIO->>DB: update_account_status()
    end
    
    AIO-->>API: task_status
    API-->>UI: {success, task_id}
    
    loop 轮询状态
        UI->>API: POST /api/auto/status
        API->>AIO: get_batch_task_status(task_id)
        AIO-->>API: status_dict
        API-->>UI: {status, logs, stats}
    end
```

## 4. 建议修复方案

### 方案一: 统一任务管理（推荐）

将 `all_in_one_service` 的任务管理移到 `task_manager.py`:

```python
# task_manager.py
def start_auto_process_task(browser_ids, api_key, card_info) -> TaskStatus:
    from google.backend.all_in_one_service import process_all_in_one_batch
    
    task = TaskManager.create_task('auto', len(browser_ids))
    
    def run():
        process_all_in_one_batch(
            browser_ids, api_key, card_info,
            log_callback=task.add_log,
            batch_progress_callback=lambda i, t, s: task.add_result(s.browser_id, ...)
        )
    
    threading.Thread(target=run, daemon=True).start()
    return task
```

### 方案二: 统一 API 路由

```python
# server.py
if path == '/api/task/status':
    # 先查 task_manager
    status = get_task_status(task_id)
    if not status:
        # 再查 all_in_one_service
        status = get_batch_task_status(task_id)
    ...
```

## 5. 数据库状态流转

```mermaid
stateDiagram-v2
    [*] --> pending: 导入账号
    pending --> not_logged_in: 检测未登录
    pending --> link_ready: 检测到SheerID链接
    pending --> verified: 已验证未绑卡
    pending --> subscribed: 已绑卡
    pending --> ineligible: 无资格
    
    not_logged_in --> link_ready: 登录成功+检测
    not_logged_in --> verified: 登录成功+已验证
    not_logged_in --> ineligible: 登录成功+无资格
    
    link_ready --> verified: SheerID验证成功
    link_ready --> ineligible: 验证失败
    
    verified --> subscribed: 绑卡成功
    verified --> subscribed_antigravity: 绑卡成功(反重力)
    
    subscribed --> [*]
    subscribed_antigravity --> [*]
    ineligible --> [*]
```
