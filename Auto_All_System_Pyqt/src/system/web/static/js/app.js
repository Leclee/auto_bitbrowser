/**
 * Auto All System - Web Admin JavaScript
 * @description 现代化管理界面的前端逻辑
 */

// ==================== 全局状态 ====================
const state = {
    currentPage: 'dashboard',
    accounts: [],
    proxies: [],
    cards: [],
    logs: [],
    stats: {},
    quota: {},
    selectedAccounts: new Set(),
    selectedProxies: new Set(),
    selectedCards: new Set(),
    showSecrets: true,  // 默认显示密码/密钥
    sidebarCollapsed: false,  // 侧边栏折叠状态
};

// 自动处理状态
const autoState = {
    accounts: [],
    selectedAccounts: new Set(),
    taskId: null,
    isRunning: false,
    pollInterval: null,
    stats: {
        total: 0,
        processed: 0,
        success: 0,
        failed: 0,
    },
    logs: [],
    lastLogIndex: 0,  // 跟踪已显示的日志索引
};

// ==================== API 封装 ====================
const api = {
    baseUrl: '',
    
    async request(endpoint, options = {}) {
        try {
            const response = await fetch(this.baseUrl + endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                },
                ...options,
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            
            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    },
    
    get(endpoint) {
        return this.request(endpoint);
    },
    
    post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
};

// ==================== 页面初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSidebar();
    initSecrets();
    loadDashboard();
    
    // 定时刷新
    setInterval(() => {
        if (state.currentPage === 'dashboard') {
            loadStats();
        }
    }, 30000);
});

// 初始化密码显示状态
function initSecrets() {
    // 同步 API Key 输入框类型与 showSecrets 状态
    const apiKeyInput = document.getElementById('setting-sheerid_api_key');
    if (apiKeyInput) {
        apiKeyInput.type = state.showSecrets ? 'text' : 'password';
    }
}

// ==================== 侧边栏 ====================
function initSidebar() {
    console.log('[Sidebar] Initializing...');
    // 从 localStorage 恢复折叠状态
    const collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (collapsed) {
        state.sidebarCollapsed = true;
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            sidebar.classList.add('collapsed');
            document.body.classList.add('sidebar-collapsed');
            console.log('[Sidebar] Restored collapsed state');
        }
    }
}

function toggleSidebar() {
    console.log('[Sidebar] Toggle clicked, current state:', state.sidebarCollapsed);
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) {
        console.error('[Sidebar] Sidebar element not found!');
        return;
    }
    
    state.sidebarCollapsed = !state.sidebarCollapsed;
    console.log('[Sidebar] New state:', state.sidebarCollapsed);
    
    if (state.sidebarCollapsed) {
        sidebar.classList.add('collapsed');
        document.body.classList.add('sidebar-collapsed');
    } else {
        sidebar.classList.remove('collapsed');
        document.body.classList.remove('sidebar-collapsed');
    }
    
    // 保存状态到 localStorage
    localStorage.setItem('sidebarCollapsed', state.sidebarCollapsed);
    console.log('[Sidebar] State saved to localStorage');
}

// ==================== 导航 ====================
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-page]');
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            navigateTo(page);
        });
    });
}

function navigateTo(page) {
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    // 更新页面显示
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });
    
    // 更新标题
    const titles = {
        'dashboard': '仪表盘',
        'accounts': '账号管理',
        'proxies': '代理管理',
        'cards': '卡片管理',
        'logs': '操作日志',
        'settings': '系统设置',
        'sheerlink': '获取 G-SheerLink',
        'verification': '批量验证 SheerID',
        'bind-card': '一键绑卡订阅',
        'auto-process': '一键全自动处理',
    };
    document.getElementById('page-title').textContent = titles[page] || page;
    
    state.currentPage = page;
    
    // 加载页面数据
    switch (page) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'accounts':
            loadAccounts();
            break;
        case 'proxies':
            loadProxies();
            break;
        case 'cards':
            loadCards();
            break;
        case 'logs':
            loadLogs();
            break;
        case 'settings':
            loadSettings();
            break;
        case 'sheerlink':
            initSheerLinkPage();
            break;
        case 'verification':
            loadVerificationAccounts();
            break;
        case 'bind-card':
            initBindCardPage();
            break;
        case 'auto-process':
            initAutoProcessPage();
            break;
        case 'change-2fa':
            initChange2FAPage();
            break;
    }
}

// ==================== Dashboard ====================
async function loadDashboard() {
    await loadStats();
}

async function loadStats() {
    try {
        const stats = await api.get('/api/system/stats');
        state.stats = stats;
        
        // 更新统计卡片
        document.getElementById('stat-accounts').textContent = stats.total_accounts || 0;
        document.getElementById('stat-verified').textContent = 
            (stats.accounts?.verified || 0) + (stats.accounts?.subscribed || 0);
        document.getElementById('stat-proxies').textContent = stats.available_proxies || 0;
        document.getElementById('stat-cards').textContent = stats.available_cards || 0;
        
        // 更新侧边栏徽章
        document.getElementById('accounts-count').textContent = stats.total_accounts || 0;
        document.getElementById('proxies-count').textContent = stats.total_proxies || 0;
        document.getElementById('cards-count').textContent = stats.total_cards || 0;
        document.getElementById('verification-count').textContent = stats.accounts?.link_ready || 0;
        
        // 更新状态分布条
        updateStatusBars(stats.accounts || {});
        
    } catch (error) {
        showToast('加载统计数据失败', 'error');
    }
}

function updateStatusBars(accountStats) {
    const container = document.getElementById('status-bars');
    const total = Object.values(accountStats).reduce((a, b) => a + b, 0) || 1;
    
    const statusConfig = {
        'pending_check': { label: '待检查', color: '#fbbf24' },
        'link_ready': { label: '链接就绪', color: '#60a5fa' },
        'verified': { label: '已验证', color: '#34d399' },
        'subscribed': { label: '已订阅', color: '#a78bfa' },
        'ineligible': { label: '无资格', color: '#f87171' },
        'error': { label: '错误', color: '#ef4444' },
    };
    
    container.innerHTML = Object.entries(statusConfig).map(([key, config]) => {
        const count = accountStats[key] || 0;
        const percent = Math.round((count / total) * 100);
        
        return `
            <div class="status-bar-item">
                <span class="status-bar-label">${config.label}</span>
                <div class="status-bar-track">
                    <div class="status-bar-fill" style="width: ${percent}%; background: ${config.color};"></div>
                </div>
                <span class="status-bar-value">${count}</span>
            </div>
        `;
    }).join('');
}

// ==================== Accounts ====================
async function loadAccounts() {
    try {
        const status = document.getElementById('filter-status')?.value || '';
        const url = status ? `/api/accounts?status=${status}` : '/api/accounts';
        const result = await api.get(url);
        state.accounts = result.data || [];
        renderAccountsTable();
    } catch (error) {
        showToast('加载账号失败', 'error');
    }
}

function renderAccountsTable() {
    const tbody = document.getElementById('accounts-table-body');
    const searchTerm = document.getElementById('search-accounts')?.value?.toLowerCase() || '';
    
    const filtered = state.accounts.filter(acc => 
        acc.email?.toLowerCase().includes(searchTerm)
    );
    
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    暂无数据
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = filtered.map(acc => {
        const pwdDisplay = state.showSecrets ? (acc.password || '-') : (acc.password ? '••••••••' : '-');
        const secretDisplay = state.showSecrets ? (acc.secret_key || '-') : (acc.secret_key ? '••••••' : '-');
        const isExported = acc.is_exported ? true : false;
        
        return `
        <tr>
            <td>
                <input type="checkbox" class="account-checkbox" data-email="${acc.email}"
                       ${state.selectedAccounts.has(acc.email) ? 'checked' : ''}
                       onchange="toggleAccountSelection('${acc.email}')">
            </td>
            <td>
                <span class="email-cell" onclick="copyToClipboard('${acc.email}')" 
                      style="cursor: pointer;" title="点击复制">
                    ${acc.email || '-'}
                </span>
            </td>
            <td class="password-cell">
                <span onclick="copyToClipboard('${acc.password || ''}')" 
                      style="cursor: pointer;" title="点击复制">
                    ${pwdDisplay}
                </span>
            </td>
            <td>${acc.recovery_email || '-'}</td>
            <td class="password-cell">
                <span onclick="copyToClipboard('${acc.secret_key || ''}')" 
                      style="cursor: pointer;" title="点击复制">
                    ${secretDisplay}
                </span>
            </td>
            <td>
                <span class="status-tag ${acc.status || 'pending_check'}">
                    ${getStatusLabel(acc.status)}
                </span>
            </td>
            <td>
                <span class="status-tag ${isExported ? 'exported' : 'not-exported'}">
                    ${isExported ? '✅已导出' : '⏳未导出'}
                </span>
            </td>
            <td>${formatDate(acc.updated_at)}</td>
            <td>
                <button class="btn btn-ghost btn-icon-only" onclick="deleteAccount('${acc.email}')" title="删除">
                    🗑️
                </button>
            </td>
        </tr>
    `;
    }).join('');
}

function filterAccounts() {
    loadAccounts();
}

function searchAccounts() {
    renderAccountsTable();
}

function toggleAccountSelection(email) {
    if (state.selectedAccounts.has(email)) {
        state.selectedAccounts.delete(email);
    } else {
        state.selectedAccounts.add(email);
    }
}

function toggleSelectAll(type) {
    const checkbox = document.getElementById(`select-all-${type}`);
    const items = type === 'accounts' ? state.accounts : 
                  type === 'proxies' ? state.proxies : state.cards;
    const selected = type === 'accounts' ? state.selectedAccounts :
                     type === 'proxies' ? state.selectedProxies : state.selectedCards;
    
    selected.clear();
    
    if (checkbox.checked) {
        items.forEach(item => {
            const key = type === 'accounts' ? item.email : item.id;
            selected.add(key);
        });
    }
    
    // 重新渲染表格
    if (type === 'accounts') renderAccountsTable();
    else if (type === 'proxies') renderProxiesTable();
    else if (type === 'cards') renderCardsTable();
}

async function importAccounts() {
    const text = document.getElementById('import-accounts-text').value;
    const separator = document.getElementById('import-accounts-separator').value;
    const status = document.getElementById('import-accounts-status').value;
    
    if (!text.trim()) {
        showToast('请输入账号数据', 'warning');
        return;
    }
    
    try {
        const result = await api.post('/api/accounts/import', {
            text, separator, status
        });
        
        showToast(`成功导入 ${result.imported} 个账号`, 'success');
        closeModal();
        loadAccounts();
        loadStats();
        
        // 清空输入
        document.getElementById('import-accounts-text').value = '';
        
    } catch (error) {
        showToast(`导入失败: ${error.message}`, 'error');
    }
}

async function deleteAccount(email) {
    if (!confirm(`确定删除账号 ${email}？`)) return;
    
    try {
        await api.post('/api/accounts/delete', { emails: [email] });
        showToast('删除成功', 'success');
        loadAccounts();
        loadStats();
    } catch (error) {
        showToast(`删除失败: ${error.message}`, 'error');
    }
}

async function deleteSelectedAccounts() {
    if (state.selectedAccounts.size === 0) {
        showToast('请先选择账号', 'warning');
        return;
    }
    
    if (!confirm(`确定删除选中的 ${state.selectedAccounts.size} 个账号？`)) return;
    
    try {
        await api.post('/api/accounts/delete', { 
            emails: Array.from(state.selectedAccounts) 
        });
        showToast('删除成功', 'success');
        state.selectedAccounts.clear();
        loadAccounts();
        loadStats();
    } catch (error) {
        showToast(`删除失败: ${error.message}`, 'error');
    }
}

// 打开批量修改状态弹窗
function openBatchStatusModal() {
    if (state.selectedAccounts.size === 0) {
        showToast('请先选择账号', 'warning');
        return;
    }
    
    // 更新弹窗中的选中数量
    const countEl = document.getElementById('batch-status-count');
    if (countEl) {
        countEl.textContent = state.selectedAccounts.size;
    }
    
    // 重置选择框
    const selectEl = document.getElementById('batch-status-select');
    if (selectEl) {
        selectEl.value = '';
    }
    
    showModal('batch-status');
}

// 批量修改账号状态
async function batchUpdateStatus() {
    if (state.selectedAccounts.size === 0) {
        showToast('请先选择账号', 'warning');
        return;
    }
    
    const status = document.getElementById('batch-status-select')?.value;
    if (!status) {
        showToast('请选择状态', 'warning');
        return;
    }
    
    try {
        const result = await api.post('/api/accounts/batch-status', {
            emails: Array.from(state.selectedAccounts),
            status: status
        });
        
        showToast(`成功修改 ${result.updated} 个账号状态`, 'success');
        state.selectedAccounts.clear();
        closeModal();
        loadAccounts();
        loadStats();
    } catch (error) {
        showToast(`修改失败: ${error.message}`, 'error');
    }
}

async function exportAccounts() {
    // 获取筛选条件
    const statusFilter = document.getElementById('export-accounts-status')?.value || '';
    const separator = document.getElementById('export-accounts-separator')?.value || '----';
    const includeExported = document.getElementById('export-include-exported')?.checked ?? true;
    const markExported = document.getElementById('export-mark-exported')?.checked ?? true;
    
    // 获取要导出的字段
    const fields = ['email']; // 邮箱始终导出
    if (document.getElementById('export-field-password')?.checked) fields.push('password');
    if (document.getElementById('export-field-recovery')?.checked) fields.push('recovery_email');
    if (document.getElementById('export-field-secret')?.checked) fields.push('secret_key');
    if (document.getElementById('export-field-link')?.checked) fields.push('verification_link');
    if (document.getElementById('export-field-status')?.checked) fields.push('status');
    
    try {
        const result = await api.post('/api/accounts/export', {
            fields,
            separator,
            status: statusFilter,
            include_exported: includeExported,
            mark_exported: markExported
        });
        
        // 创建下载
        const blob = new Blob([result.data], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const statusSuffix = statusFilter ? `_${statusFilter}` : '';
        a.download = `accounts_export${statusSuffix}_${new Date().toISOString().slice(0,10)}.txt`;
        a.click();
        URL.revokeObjectURL(url);
        
        closeModal();
        showToast(`导出 ${result.count} 个账号`, 'success');
        
        // 如果标记了已导出，刷新账号列表
        if (markExported && result.count > 0) {
            loadAccounts();
        }
    } catch (error) {
        showToast(`导出失败: ${error.message}`, 'error');
    }
}

// ==================== Proxies ====================
async function loadProxies() {
    try {
        const result = await api.get('/api/proxies');
        state.proxies = result.data || [];
        renderProxiesTable();
    } catch (error) {
        showToast('加载代理失败', 'error');
    }
}

function renderProxiesTable() {
    const tbody = document.getElementById('proxies-table-body');
    const searchTerm = document.getElementById('search-proxies')?.value?.toLowerCase() || '';
    
    const filtered = state.proxies.filter(p => 
        p.host?.toLowerCase().includes(searchTerm)
    );
    
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    暂无数据
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = filtered.map(p => `
        <tr>
            <td>
                <input type="checkbox" class="proxy-checkbox" data-id="${p.id}"
                       ${state.selectedProxies.has(p.id) ? 'checked' : ''}
                       onchange="toggleProxySelection(${p.id})">
            </td>
            <td><span class="status-tag">${p.proxy_type || 'socks5'}</span></td>
            <td>${p.host}</td>
            <td>${p.port}</td>
            <td>${p.username || '-'}</td>
            <td>
                <span class="status-tag ${p.is_used ? 'used' : 'available'}">
                    ${p.is_used ? '已使用' : '可用'}
                </span>
            </td>
            <td>${p.used_by || '-'}</td>
            <td>
                <button class="btn btn-ghost btn-icon-only" onclick="deleteProxy(${p.id})" title="删除">
                    🗑️
                </button>
            </td>
        </tr>
    `).join('');
}

function searchProxies() {
    renderProxiesTable();
}

function toggleProxySelection(id) {
    if (state.selectedProxies.has(id)) {
        state.selectedProxies.delete(id);
    } else {
        state.selectedProxies.add(id);
    }
}

async function importProxies() {
    const text = document.getElementById('import-proxies-text').value;
    const type = document.getElementById('import-proxies-type').value;
    
    if (!text.trim()) {
        showToast('请输入代理数据', 'warning');
        return;
    }
    
    try {
        const result = await api.post('/api/proxies/import', { text, type });
        showToast(`成功导入 ${result.imported} 个代理`, 'success');
        closeModal();
        loadProxies();
        loadStats();
        document.getElementById('import-proxies-text').value = '';
    } catch (error) {
        showToast(`导入失败: ${error.message}`, 'error');
    }
}

async function deleteProxy(id) {
    if (!confirm('确定删除该代理？')) return;
    
    try {
        await api.post('/api/proxies/delete', { ids: [id] });
        showToast('删除成功', 'success');
        loadProxies();
        loadStats();
    } catch (error) {
        showToast(`删除失败: ${error.message}`, 'error');
    }
}

async function clearProxies() {
    if (!confirm('确定清空所有代理？此操作不可恢复！')) return;
    
    try {
        await api.post('/api/proxies/clear', {});
        showToast('已清空所有代理', 'success');
        loadProxies();
        loadStats();
    } catch (error) {
        showToast(`清空失败: ${error.message}`, 'error');
    }
}

// ==================== Cards ====================
async function loadCards() {
    try {
        const result = await api.get('/api/cards');
        state.cards = result.data || [];
        renderCardsTable();
    } catch (error) {
        showToast('加载卡片失败', 'error');
    }
}

function renderCardsTable() {
    const tbody = document.getElementById('cards-table-body');
    const searchTerm = document.getElementById('search-cards')?.value?.toLowerCase() || '';
    
    const filtered = state.cards.filter(c => 
        c.card_number?.toLowerCase().includes(searchTerm)
    );
    
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    暂无数据
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = filtered.map(c => {
        const cardDisplay = state.showSecrets ? 
            c.card_number : 
            (c.card_number ? c.card_number.slice(0, 4) + ' •••• •••• ' + c.card_number.slice(-4) : '-');
        const cvvDisplay = state.showSecrets ? (c.cvv || '-') : '•••';
        const isExhausted = c.usage_count >= c.max_usage;
        
        return `
            <tr>
                <td>
                    <input type="checkbox" class="card-checkbox" data-id="${c.id}"
                           ${state.selectedCards.has(c.id) ? 'checked' : ''}
                           onchange="toggleCardSelection(${c.id})">
                </td>
                <td>
                    <span onclick="copyToClipboard('${c.card_number}')" 
                          style="cursor: pointer; font-family: monospace;" title="点击复制">
                        ${cardDisplay}
                    </span>
                </td>
                <td>${c.exp_month}/${c.exp_year}</td>
                <td class="password-cell">
                    <span onclick="copyToClipboard('${c.cvv || ''}')" 
                          style="cursor: pointer;" title="点击复制">
                        ${cvvDisplay}
                    </span>
                </td>
                <td>${c.holder_name || '-'}</td>
                <td>${c.zip_code || '-'}</td>
                <td>${c.usage_count}/${c.max_usage}</td>
                <td>
                    <span class="status-tag ${c.is_active ? (isExhausted ? 'inactive' : 'active') : 'inactive'}">
                        ${c.is_active ? (isExhausted ? '已用尽' : '可用') : '已禁用'}
                    </span>
                </td>
                <td>
                    <button class="btn btn-ghost btn-icon-only" onclick="editCard(${c.id})" title="编辑">
                        ✏️
                    </button>
                    <button class="btn btn-ghost btn-icon-only" onclick="toggleCard(${c.id}, ${!c.is_active})" 
                            title="${c.is_active ? '禁用' : '启用'}">
                        ${c.is_active ? '🔒' : '🔓'}
                    </button>
                    <button class="btn btn-ghost btn-icon-only" onclick="deleteCard(${c.id})" title="删除">
                        🗑️
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function searchCards() {
    renderCardsTable();
}

function toggleCardSelection(id) {
    if (state.selectedCards.has(id)) {
        state.selectedCards.delete(id);
    } else {
        state.selectedCards.add(id);
    }
}

async function importCards() {
    const text = document.getElementById('import-cards-text').value;
    const maxUsage = parseInt(document.getElementById('import-cards-max-usage').value) || 1;
    
    if (!text.trim()) {
        showToast('请输入卡片数据', 'warning');
        return;
    }
    
    try {
        const result = await api.post('/api/cards/import', { text, max_usage: maxUsage });
        showToast(`成功导入 ${result.imported} 张卡片`, 'success');
        closeModal();
        loadCards();
        loadStats();
        document.getElementById('import-cards-text').value = '';
    } catch (error) {
        showToast(`导入失败: ${error.message}`, 'error');
    }
}

async function toggleCard(id, active) {
    try {
        await api.post('/api/cards/toggle', { id, active });
        showToast(active ? '卡片已启用' : '卡片已禁用', 'success');
        loadCards();
    } catch (error) {
        showToast(`操作失败: ${error.message}`, 'error');
    }
}

async function deleteCard(id) {
    if (!confirm('确定删除该卡片？')) return;
    
    try {
        await api.post('/api/cards/delete', { ids: [id] });
        showToast('删除成功', 'success');
        loadCards();
        loadStats();
    } catch (error) {
        showToast(`删除失败: ${error.message}`, 'error');
    }
}

async function clearCards() {
    if (!confirm('确定清空所有卡片？此操作不可恢复！')) return;
    
    try {
        await api.post('/api/cards/clear', {});
        showToast('已清空所有卡片', 'success');
        loadCards();
        loadStats();
    } catch (error) {
        showToast(`清空失败: ${error.message}`, 'error');
    }
}

// 编辑卡片
function editCard(id) {
    const card = state.cards.find(c => c.id === id);
    if (!card) {
        showToast('卡片不存在', 'error');
        return;
    }
    
    // 填充表单
    document.getElementById('edit-card-id').value = card.id;
    document.getElementById('edit-card-number').value = card.card_number || '';
    document.getElementById('edit-card-exp-month').value = card.exp_month || '';
    document.getElementById('edit-card-exp-year').value = card.exp_year || '';
    document.getElementById('edit-card-cvv').value = card.cvv || '';
    document.getElementById('edit-card-holder').value = card.holder_name || '';
    document.getElementById('edit-card-zip').value = card.zip_code || '';
    document.getElementById('edit-card-usage').value = card.usage_count || 0;
    document.getElementById('edit-card-max-usage').value = card.max_usage || 1;
    document.getElementById('edit-card-active').checked = card.is_active ? true : false;
    
    showModal('edit-card');
}

// 保存卡片编辑
async function saveCardEdit() {
    const id = document.getElementById('edit-card-id').value;
    
    const data = {
        id: parseInt(id),
        card_number: document.getElementById('edit-card-number').value.trim(),
        exp_month: document.getElementById('edit-card-exp-month').value.trim(),
        exp_year: document.getElementById('edit-card-exp-year').value.trim(),
        cvv: document.getElementById('edit-card-cvv').value.trim(),
        holder_name: document.getElementById('edit-card-holder').value.trim() || null,
        zip_code: document.getElementById('edit-card-zip').value.trim() || null,
        usage_count: parseInt(document.getElementById('edit-card-usage').value) || 0,
        max_usage: parseInt(document.getElementById('edit-card-max-usage').value) || 1,
        is_active: document.getElementById('edit-card-active').checked
    };
    
    // 验证必填字段
    if (!data.card_number || !data.exp_month || !data.exp_year || !data.cvv) {
        showToast('请填写卡号、有效期和CVV', 'warning');
        return;
    }
    
    try {
        const result = await api.post('/api/cards/update', data);
        if (result.success) {
            showToast('卡片信息已更新', 'success');
            closeModal();
            loadCards();
        } else {
            showToast(result.error || '更新失败', 'error');
        }
    } catch (error) {
        showToast(`更新失败: ${error.message}`, 'error');
    }
}

// ==================== Logs ====================
async function loadLogs() {
    try {
        const result = await api.get('/api/logs?limit=100');
        state.logs = result.data || [];
        renderLogs();
    } catch (error) {
        showToast('加载日志失败', 'error');
    }
}

function renderLogs() {
    const container = document.getElementById('logs-list');
    
    if (state.logs.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">暂无日志</div>';
        return;
    }
    
    container.innerHTML = state.logs.map(log => `
        <div class="log-item">
            <span class="log-time">${formatDate(log.created_at)}</span>
            <span class="log-type ${log.operation_type}">${log.operation_type}</span>
            <span class="log-content">
                ${log.target_email ? `[${log.target_email}] ` : ''}${log.details || ''}
            </span>
        </div>
    `).join('');
}

// ==================== Settings ====================
async function loadSettings() {
    console.log('[Settings] Loading settings...');
    try {
        const settings = await api.get('/api/settings');
        console.log('[Settings] Loaded:', settings);
        
        // 填充设置表单
        Object.entries(settings).forEach(([key, value]) => {
            const input = document.getElementById(`setting-${key}`);
            if (input) {
                input.value = value || '';
            }
        });
        
        // 如果有 API Key，自动刷新配额
        const apiKey = document.getElementById('setting-sheerid_api_key')?.value?.trim();
        if (apiKey) {
            console.log('[Settings] API Key found, refreshing quota...');
            // 延迟一下确保DOM更新
            setTimeout(() => refreshQuota(), 100);
        }
    } catch (error) {
        console.error('[Settings] Load failed:', error);
        showToast('加载设置失败', 'error');
    }
}

async function saveSettings() {
    const settings = {};
    
    document.querySelectorAll('[id^="setting-"]').forEach(input => {
        const key = input.id.replace('setting-', '');
        settings[key] = input.value;
    });
    
    try {
        await api.post('/api/settings/save', settings);
        showToast('设置已保存', 'success');
    } catch (error) {
        showToast(`保存失败: ${error.message}`, 'error');
    }
}

// ==================== 系统状态管理 ====================
async function refreshQuota() {
    console.log('[Status] Refresh clicked');
    const statusEl = document.getElementById('quota-status');
    const statusTextEl = document.getElementById('quota-status-text');
    const apiKeyInput = document.getElementById('setting-sheerid_api_key');
    
    // 获取输入框中的 API Key
    const apiKey = apiKeyInput?.value?.trim() || '';
    console.log('[Status] API Key length:', apiKey.length);
    
    if (!apiKey) {
        statusEl.className = 'quota-status error';
        statusTextEl.textContent = '请先输入 API Key';
        showToast('请先输入 API Key', 'warning');
        return;
    }
    
    // 显示加载状态
    statusEl.className = 'quota-status';
    statusTextEl.textContent = '正在获取系统状态...';
    
    try {
        console.log('[Status] Sending request...');
        // 传递 API Key 到后端
        const result = await api.post('/api/sheerid/quota', { api_key: apiKey });
        console.log('[Status] Response:', JSON.stringify(result));
        state.quota = result;
        
        if (!result.success) {
            throw new Error(result.error || '获取状态失败');
        }
        
        // 更新状态显示
        const quota = result.current_quota || 0;
        const available = result.available_slots || 0;
        const active = result.active_jobs || 0;
        
        document.getElementById('quota-remaining').textContent = quota || '--';
        document.getElementById('quota-available').textContent = available;
        document.getElementById('quota-active').textContent = active;
        
        // 更新进度条（显示配额占比，假设最大1000）
        const maxQuota = 1000;
        const percent = quota > 0 ? Math.min(Math.round((quota / maxQuota) * 100), 100) : 0;
        document.getElementById('quota-progress-bar').style.width = `${percent}%`;
        
        // 更新状态
        statusEl.className = 'quota-status online';
        let statusText = `系统在线`;
        if (result.quota_update_time) {
            statusText += ` | 配额更新: ${result.quota_update_time}`;
        }
        statusTextEl.textContent = statusText;
        
        // 根据配额设置进度条颜色
        const progressBar = document.getElementById('quota-progress-bar');
        if (quota < 20) {
            progressBar.style.background = 'linear-gradient(90deg, var(--danger), #f87171)';
        } else if (quota < 100) {
            progressBar.style.background = 'linear-gradient(90deg, var(--warning), #fbbf24)';
        } else {
            progressBar.style.background = 'linear-gradient(90deg, var(--success), var(--primary))';
        }
        
        showToast('状态已更新', 'success');
        
    } catch (error) {
        console.error('[Status] Error:', error);
        statusEl.className = 'quota-status error';
        statusTextEl.textContent = error.message || '获取状态失败，请检查 API Key';
        
        // 显示占位符
        document.getElementById('quota-remaining').textContent = '--';
        document.getElementById('quota-available').textContent = '--';
        document.getElementById('quota-active').textContent = '--';
        document.getElementById('quota-progress-bar').style.width = '0%';
        
        showToast(error.message || '获取状态失败', 'error');
    }
}

// ==================== 快速操作 ====================
async function syncBrowsers() {
    try {
        const result = await api.post('/api/accounts/sync-browsers', {});
        showToast(result.message || '同步任务已启动', 'success');
    } catch (error) {
        showToast(`同步失败: ${error.message}`, 'error');
    }
}

async function exportFiles() {
    try {
        const result = await api.post('/api/export/files', {});
        showToast(result.message || '导出成功', 'success');
    } catch (error) {
        showToast(`导出失败: ${error.message}`, 'error');
    }
}

function toggleSecrets() {
    state.showSecrets = !state.showSecrets;
    
    // 更新按钮文字和图标
    const icon = document.getElementById('toggle-secrets-icon');
    const text = document.getElementById('toggle-secrets-text');
    
    if (state.showSecrets) {
        icon.textContent = '👁️';
        text.textContent = '隐藏密码';
    } else {
        icon.textContent = '🙈';
        text.textContent = '显示密码';
    }
    
    // 切换设置页面中密码类型输入框
    const apiKeyInput = document.getElementById('setting-sheerid_api_key');
    if (apiKeyInput) {
        apiKeyInput.type = state.showSecrets ? 'text' : 'password';
    }
    
    // 刷新当前页面的表格
    if (state.currentPage === 'accounts') {
        renderAccountsTable();
    } else if (state.currentPage === 'cards') {
        renderCardsTable();
    }
}

function refreshData() {
    switch (state.currentPage) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'accounts':
            loadAccounts();
            break;
        case 'proxies':
            loadProxies();
            break;
        case 'cards':
            loadCards();
            break;
        case 'logs':
            loadLogs();
            break;
    }
    showToast('数据已刷新', 'info');
}

// ==================== Modal ====================
function showModal(name) {
    const modal = document.getElementById(`modal-${name}`);
    const overlay = document.getElementById('modal-overlay');
    
    if (modal && overlay) {
        modal.classList.add('active');
        overlay.classList.add('active');
    }
}

function closeModal() {
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
    document.getElementById('modal-overlay').classList.remove('active');
}

// ESC 关闭模态框
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// ==================== Toast ====================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️',
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    // 自动移除
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==================== 工具函数 ====================
function getStatusLabel(status) {
    const labels = {
        'pending_check': '待检查',
        'link_ready': '链接就绪',
        'verified': '已验证',
        'subscribed': '已订阅',
        'subscribed_antigravity': '已解锁AG',
        'ineligible': '无资格',
        'error': '错误',
        'running': '运行中',
        'processing': '处理中',
    };
    return labels[status] || status || '未知';
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function copyToClipboard(text) {
    if (!text) return;
    
    navigator.clipboard.writeText(text).then(() => {
        showToast('已复制到剪贴板', 'success');
    }).catch(() => {
        // Fallback
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('已复制到剪贴板', 'success');
    });
}

// ==================== 键盘快捷键 ====================
document.addEventListener('keydown', (e) => {
    // Ctrl+R 刷新数据
    if (e.ctrlKey && e.key === 'r') {
        e.preventDefault();
        refreshData();
    }
    
    // 数字键快速导航
    if (e.altKey) {
        switch (e.key) {
            case '1': navigateTo('dashboard'); break;
            case '2': navigateTo('accounts'); break;
            case '3': navigateTo('proxies'); break;
            case '4': navigateTo('cards'); break;
            case '5': navigateTo('logs'); break;
            case '6': navigateTo('settings'); break;
            case '7': navigateTo('verification'); break;
        }
    }
});

// ==================== Verification Page ====================
// 验证页面状态
const verifyState = {
    accounts: [],
    selectedIds: new Set(),
    isVerifying: false,
    successCount: 0,
    failedCount: 0,
};

// 加载待验证账号
async function loadVerificationAccounts() {
    console.log('[Verification] Loading accounts...');
    
    try {
        const result = await api.get('/api/accounts/link_ready');
        verifyState.accounts = result.data || [];
        
        // 更新统计
        document.getElementById('verify-total').textContent = verifyState.accounts.length;
        document.getElementById('verification-count').textContent = verifyState.accounts.length;
        
        // 渲染列表
        renderVerificationList();
        
        // 重置选择
        verifyState.selectedIds.clear();
        updateVerifySelectedCount();
        
    } catch (error) {
        console.error('[Verification] Error:', error);
        showToast(`加载失败: ${error.message}`, 'error');
    }
}

// 渲染验证列表
function renderVerificationList() {
    const container = document.getElementById('verification-list');
    const emptyState = document.getElementById('verification-empty');
    
    if (!verifyState.accounts.length) {
        emptyState.style.display = 'flex';
        return;
    }
    
    emptyState.style.display = 'none';
    
    const html = verifyState.accounts.map(acc => {
        const isSelected = verifyState.selectedIds.has(acc.verification_id);
        return `
            <div class="verification-item ${isSelected ? 'selected' : ''}" 
                 id="verify-item-${acc.verification_id}"
                 data-vid="${acc.verification_id}">
                <input type="checkbox" class="verify-checkbox" 
                       ${isSelected ? 'checked' : ''}
                       onchange="toggleVerifySelect('${acc.verification_id}', this)">
                <div class="verify-info">
                    <div class="verify-email">${escapeHtml(acc.email)}</div>
                    <div class="verify-link" title="${escapeHtml(acc.verification_link)}">
                        ${acc.verification_id ? `ID: ${acc.verification_id.substring(0, 24)}...` : '无验证ID'}
                    </div>
                </div>
                <div class="verify-status" id="verify-status-${acc.verification_id}">
                    <span class="verify-status-icon">⏳</span>
                    <span class="verify-status-text">待验证</span>
                </div>
            </div>
        `;
    }).join('');
    
    // 保留空状态元素，只更新列表内容
    container.innerHTML = html + '<div class="empty-state" id="verification-empty" style="display:none;"><span class="empty-icon">📭</span><p>暂无待验证的账号</p><p class="empty-hint">账号状态为"待验证"时会显示在这里</p></div>';
}

// 切换单个选择
function toggleVerifySelect(vid, checkbox) {
    // 直接读取 checkbox 的当前状态（浏览器在 onchange 前已更新）
    const item = document.getElementById(`verify-item-${vid}`);
    const cb = checkbox || item?.querySelector('.verify-checkbox');
    const isChecked = cb?.checked ?? false;
    
    if (isChecked) {
        verifyState.selectedIds.add(vid);
        item?.classList.add('selected');
    } else {
        verifyState.selectedIds.delete(vid);
        item?.classList.remove('selected');
    }
    
    // 更新全选复选框状态
    updateVerifySelectAllState();
    updateVerifySelectedCount();
}

// 更新全选复选框状态
function updateVerifySelectAllState() {
    const selectAllCb = document.getElementById('verify-select-all');
    if (!selectAllCb) return;
    
    const totalWithId = verifyState.accounts.filter(acc => acc.verification_id).length;
    const selectedCount = verifyState.selectedIds.size;
    
    selectAllCb.checked = totalWithId > 0 && selectedCount === totalWithId;
    selectAllCb.indeterminate = selectedCount > 0 && selectedCount < totalWithId;
}

// 全选/取消全选
function toggleVerifySelectAll() {
    const checkbox = document.getElementById('verify-select-all');
    const isChecked = checkbox.checked;
    
    // 清空选中状态
    verifyState.selectedIds.clear();
    
    // 如果是全选，添加所有有效账号
    if (isChecked) {
        verifyState.accounts.forEach(acc => {
            if (acc.verification_id) {
                verifyState.selectedIds.add(acc.verification_id);
            }
        });
    }
    
    // 同步更新所有复选框和样式
    verifyState.accounts.forEach(acc => {
        if (acc.verification_id) {
            const item = document.getElementById(`verify-item-${acc.verification_id}`);
            const cb = item?.querySelector('.verify-checkbox');
            if (cb) cb.checked = isChecked;
            if (item) item.classList.toggle('selected', isChecked);
        }
    });
    
    updateVerifySelectedCount();
}

// 更新选中数量
function updateVerifySelectedCount() {
    document.getElementById('verify-selected').textContent = verifyState.selectedIds.size;
}

// 开始验证
async function startVerification() {
    if (verifyState.selectedIds.size === 0) {
        showToast('请先选择要验证的账号', 'warning');
        return;
    }
    
    if (verifyState.isVerifying) {
        showToast('验证正在进行中...', 'warning');
        return;
    }
    
    // 确认
    if (!confirm(`确定要验证选中的 ${verifyState.selectedIds.size} 个账号吗？`)) {
        return;
    }
    
    verifyState.isVerifying = true;
    verifyState.successCount = 0;
    verifyState.failedCount = 0;
    
    // 更新 UI
    document.getElementById('btn-start-verify').style.display = 'none';
    document.getElementById('btn-stop-verify').style.display = 'inline-flex';
    document.getElementById('verification-progress').style.display = 'block';
    
    const total = verifyState.selectedIds.size;
    updateProgress(0, total, '正在提交验证请求...');
    
    // 标记选中的账号为"验证中"
    verifyState.selectedIds.forEach(vid => {
        updateItemStatus(vid, 'verifying', '🔄', '验证中...');
    });
    
    addVerifyLog('info', `开始验证 ${total} 个账号...`);
    
    try {
        const verificationIds = Array.from(verifyState.selectedIds);
        
        // 获取 API Key
        const apiKey = document.getElementById('setting-sheerid_api_key')?.value?.trim() || '';
        if (!apiKey) {
            throw new Error('请先在系统设置中配置 API Key');
        }
        
        // 调用验证 API
        const result = await api.post('/api/sheerid/verify', {
            verification_ids: verificationIds,
            api_key: apiKey
        });
        
        if (result.success) {
            verifyState.successCount = result.success_count || 0;
            verifyState.failedCount = result.failed_count || 0;
            
            // 更新每个账号的状态
            (result.results || []).forEach(r => {
                if (r.status === 'success') {
                    updateItemStatus(r.verification_id, 'success', '✅', '验证成功');
                    addVerifyLog('success', `${r.verification_id.substring(0, 20)}... 验证成功`);
                } else {
                    updateItemStatus(r.verification_id, 'failed', '❌', r.message || '验证失败');
                    addVerifyLog('error', `${r.verification_id.substring(0, 20)}... 失败: ${r.message}`);
                }
            });
            
            // 更新配额信息
            if (result.quota) {
                addVerifyLog('info', `配额更新: 剩余 ${result.quota.current_quota}`);
            }
            
            updateProgress(total, total, '验证完成');
            showToast(`验证完成: 成功 ${verifyState.successCount}, 失败 ${verifyState.failedCount}`, 
                      verifyState.failedCount > 0 ? 'warning' : 'success');
        } else {
            throw new Error(result.error || '验证失败');
        }
        
    } catch (error) {
        console.error('[Verification] Error:', error);
        addVerifyLog('error', `验证出错: ${error.message}`);
        showToast(`验证失败: ${error.message}`, 'error');
        
        // 标记所有为失败
        verifyState.selectedIds.forEach(vid => {
            updateItemStatus(vid, 'failed', '❌', error.message);
        });
    }
    
    // 完成后更新 UI
    finishVerification();
}

// 停止验证 (注意：当前实现是同步的，此功能预留)
function stopVerification() {
    addVerifyLog('warning', '用户请求停止验证...');
    verifyState.isVerifying = false;
    finishVerification();
}

// 完成验证
function finishVerification() {
    verifyState.isVerifying = false;
    
    document.getElementById('btn-start-verify').style.display = 'inline-flex';
    document.getElementById('btn-stop-verify').style.display = 'none';
    
    document.getElementById('verify-success').textContent = verifyState.successCount;
    document.getElementById('verify-failed').textContent = verifyState.failedCount;
    
    addVerifyLog('info', `验证结束: 成功 ${verifyState.successCount}, 失败 ${verifyState.failedCount}`);
    
    // 3秒后刷新列表（移除已验证成功的）
    setTimeout(() => {
        loadVerificationAccounts();
    }, 3000);
}

// 更新进度条
function updateProgress(current, total, status) {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;
    document.getElementById('progress-bar').style.width = `${percent}%`;
    document.getElementById('progress-text').textContent = `${current} / ${total}`;
    document.getElementById('progress-status').textContent = status;
}

// 更新单个账号状态
function updateItemStatus(vid, statusClass, icon, text) {
    const item = document.getElementById(`verify-item-${vid}`);
    if (item) {
        item.classList.remove('verifying', 'success', 'failed');
        item.classList.add(statusClass);
    }
    
    const statusEl = document.getElementById(`verify-status-${vid}`);
    if (statusEl) {
        statusEl.innerHTML = `
            <span class="verify-status-icon">${icon}</span>
            <span class="verify-status-text">${text}</span>
        `;
    }
}

// 添加验证日志
function addVerifyLog(type, message) {
    const logContainer = document.getElementById('verification-log');
    const placeholder = logContainer.querySelector('.log-placeholder');
    if (placeholder) {
        placeholder.remove();
    }
    
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-message ${type}">${escapeHtml(message)}</span>
    `;
    
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// 清空验证日志
function clearVerificationLog() {
    const logContainer = document.getElementById('verification-log');
    logContainer.innerHTML = '<div class="log-placeholder">验证日志将显示在这里...</div>';
}

// HTML 转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 一键全自动处理 ====================

// 初始化自动处理页面
function initAutoProcessPage() {
    console.log('[AutoProcess] Initializing page...');
    updateAutoStats();
    
    // 自动加载账号列表
    loadAutoAccounts();
    
    // 如果有正在运行的任务，恢复轮询
    if (autoState.taskId && autoState.isRunning) {
        startPolling();
    }
}

// 加载账号列表
async function loadAutoAccounts() {
    console.log('[AutoProcess] Loading accounts...');
    
    try {
        const result = await api.post('/api/accounts/for_process', {});
        
        if (result.success) {
            autoState.accounts = result.accounts || [];
            autoState.selectedAccounts.clear();
            
            renderAccountList();
            showToast(`已加载 ${autoState.accounts.length} 个账号`, 'success');
        } else {
            throw new Error(result.error || '加载失败');
        }
    } catch (error) {
        console.error('[AutoProcess] Load accounts failed:', error);
        showToast(`加载失败: ${error.message}`, 'error');
    }
}

// 渲染账号列表
function renderAccountList() {
    const container = document.getElementById('browser-list');
    
    if (autoState.accounts.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📭</span>
                <p>暂无账号，请先在账号管理页面导入</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = autoState.accounts.map(account => {
        const isSelected = autoState.selectedAccounts.has(account.browser_id);
        const statusClass = account.status || 'pending';
        const displayStatus = account.processStatus || statusClass;
        
        return `
            <div class="browser-item ${isSelected ? 'selected' : ''} ${getStatusClass(displayStatus)}" 
                 data-id="${account.browser_id}" data-email="${account.email}"
                 onclick="toggleAccountSelect('${account.browser_id}')">
                <input type="checkbox" class="browser-checkbox" 
                       ${isSelected ? 'checked' : ''} 
                       onclick="event.stopPropagation(); toggleAccountSelect('${account.browser_id}')">
                <div class="browser-info">
                    <div class="browser-email">${escapeHtml(account.email)}</div>
                    <div class="browser-id">窗口: ${account.browser_id ? account.browser_id.substring(0, 16) + '...' : '未绑定'}</div>
                </div>
                <span class="browser-status ${getStatusClass(displayStatus)}" id="account-status-${account.browser_id}">
                    ${getStatusText(displayStatus)}
                </span>
            </div>
        `;
    }).join('');
    
    updateAutoSelectedCount();
}

// 获取状态对应的CSS类
function getStatusClass(status) {
    const classMap = {
        'subscribed': 'success',
        'subscribed_antigravity': 'success',
        'verified': 'success',
        'link_ready': 'processing',
        'pending': 'pending',
        'processing': 'processing',
        'not_logged_in': 'failed',
        'ineligible': 'failed',
        'error': 'failed',
    };
    return classMap[status] || 'pending';
}

// 获取状态文本
function getStatusText(status) {
    const texts = {
        'pending': '待处理',
        'pending_check': '待检测',
        'processing': '处理中...',
        'success': '成功',
        'failed': '失败',
        'subscribed': '👑已订阅',
        'subscribed_antigravity': '🌟已解锁',
        'verified': '✅已验证',
        'link_ready': '🔗待验证',
        'ineligible': '❌无资格',
        'not_logged_in': '🔒未登录',
        'error': '⚠️错误',
    };
    return texts[status] || status;
}

// 切换账号选择
function toggleAccountSelect(browserId) {
    if (autoState.isRunning) {
        showToast('任务运行中，无法修改选择', 'warning');
        return;
    }
    
    if (!browserId) {
        showToast('该账号未绑定浏览器窗口', 'warning');
        return;
    }
    
    if (autoState.selectedAccounts.has(browserId)) {
        autoState.selectedAccounts.delete(browserId);
    } else {
        autoState.selectedAccounts.add(browserId);
    }
    
    // 更新 UI
    const item = document.querySelector(`.browser-item[data-id="${browserId}"]`);
    if (item) {
        item.classList.toggle('selected', autoState.selectedAccounts.has(browserId));
        const checkbox = item.querySelector('.browser-checkbox');
        if (checkbox) {
            checkbox.checked = autoState.selectedAccounts.has(browserId);
        }
    }
    
    updateAutoSelectedCount();
}

// 全选/取消全选
function toggleAutoSelectAll() {
    if (autoState.isRunning) {
        showToast('任务运行中，无法修改选择', 'warning');
        return;
    }
    
    const selectAllCheckbox = document.getElementById('auto-select-all');
    const isChecked = selectAllCheckbox.checked;
    
    if (isChecked) {
        // 只选择有 browser_id 的账号
        autoState.accounts.forEach(acc => {
            if (acc.browser_id) {
                autoState.selectedAccounts.add(acc.browser_id);
            }
        });
    } else {
        autoState.selectedAccounts.clear();
    }
    
    renderAccountList();
}

// 更新选中数量
function updateAutoSelectedCount() {
    document.getElementById('auto-selected-count').textContent = autoState.selectedAccounts.size;
    
    // 更新全选复选框状态
    const selectAllCheckbox = document.getElementById('auto-select-all');
    if (selectAllCheckbox) {
        const selectableCount = autoState.accounts.filter(a => a.browser_id).length;
        selectAllCheckbox.checked = selectableCount > 0 && 
                                     autoState.selectedAccounts.size === selectableCount;
    }
}

// 更新统计
function updateAutoStats() {
    document.getElementById('auto-total').textContent = autoState.stats.total;
    document.getElementById('auto-processed').textContent = autoState.stats.processed;
    document.getElementById('auto-success').textContent = autoState.stats.success;
    document.getElementById('auto-failed').textContent = autoState.stats.failed;
}

// 开始自动处理
async function startAutoProcess() {
    if (autoState.selectedAccounts.size === 0) {
        showToast('请先选择要处理的账号', 'warning');
        return;
    }
    
    if (autoState.isRunning) {
        showToast('已有任务在运行中', 'warning');
        return;
    }
    
    // 确认
    if (!confirm(`确定要处理选中的 ${autoState.selectedAccounts.size} 个账号吗？\n\n流程: 登录 → 资格检测 → SheerID验证 → 绑卡订阅`)) {
        return;
    }
    
    const browserIds = Array.from(autoState.selectedAccounts);
    
    // 获取 API Key
    const apiKey = document.getElementById('setting-sheerid_api_key')?.value?.trim() || '';
    
    // 获取并发数
    const threadCount = parseInt(document.getElementById('auto-concurrency')?.value || '1', 10);
    
    // 重置状态
    autoState.stats = {
        total: browserIds.length,
        processed: 0,
        success: 0,
        failed: 0,
    };
    autoState.logs = [];
    autoState.lastLogIndex = 0;
    
    // 更新 UI
    updateAutoStats();
    document.getElementById('btn-start-auto').style.display = 'none';
    document.getElementById('btn-stop-auto').style.display = 'inline-flex';
    document.getElementById('auto-progress-section').style.display = 'block';
    document.getElementById('auto-results-panel').style.display = 'none';
    
    clearAutoLog();
    addAutoLog('info', `开始处理 ${browserIds.length} 个账号，并发数: ${threadCount}...`);
    
    // 标记所有选中的账号为待处理
    browserIds.forEach(id => {
        updateAccountStatus(id, 'pending');
    });
    
    try {
        const result = await api.post('/api/auto/start', {
            browser_ids: browserIds,
            api_key: apiKey,
            thread_count: threadCount,
        });
        
        if (result.success) {
            autoState.taskId = result.task_id;
            autoState.isRunning = true;
            
            addAutoLog('success', `任务已启动: ${result.task_id}`);
            showToast('任务已启动', 'success');
            
            // 开始轮询状态
            startPolling();
        } else {
            throw new Error(result.error || '启动失败');
        }
    } catch (error) {
        console.error('[AutoProcess] Start failed:', error);
        addAutoLog('error', `启动失败: ${error.message}`);
        showToast(`启动失败: ${error.message}`, 'error');
        finishAutoProcess();
    }
}

// 停止自动处理
async function stopAutoProcess() {
    if (!autoState.taskId) {
        return;
    }
    
    try {
        const result = await api.post('/api/auto/stop', {
            task_id: autoState.taskId,
        });
        
        if (result.success) {
            addAutoLog('warning', '已发送停止请求...');
            showToast('正在停止...', 'info');
        }
    } catch (error) {
        console.error('[AutoProcess] Stop failed:', error);
        showToast(`停止失败: ${error.message}`, 'error');
    }
}

// 开始轮询状态
function startPolling() {
    if (autoState.pollInterval) {
        clearInterval(autoState.pollInterval);
    }
    
    autoState.pollInterval = setInterval(pollTaskStatus, 1500);
    pollTaskStatus(); // 立即执行一次
}

// 停止轮询
function stopPolling() {
    if (autoState.pollInterval) {
        clearInterval(autoState.pollInterval);
        autoState.pollInterval = null;
    }
}

// 轮询任务状态
async function pollTaskStatus() {
    if (!autoState.taskId) {
        stopPolling();
        return;
    }
    
    try {
        const result = await api.post('/api/auto/status', {
            task_id: autoState.taskId,
        });
        
        if (result.success) {
            // 更新统计
            autoState.stats.total = result.total;
            autoState.stats.processed = result.processed;
            
            const stats = result.stats || {};
            // 只有订阅成功才算成功
            autoState.stats.success = (stats.subscribed || 0) + (stats.subscribed_antigravity || 0);
            // verified（验证成功但绑卡失败）、link_ready（有链接但未验证）也算失败
            autoState.stats.failed = (stats.error || 0) + (stats.not_logged_in || 0) + (stats.ineligible || 0) + (stats.verified || 0) + (stats.link_ready || 0);
            
            updateAutoStats();
            
            // 更新进度条
            const percent = result.total > 0 ? Math.round((result.processed / result.total) * 100) : 0;
            document.getElementById('auto-progress-bar').style.width = `${percent}%`;
            document.getElementById('auto-progress-text').textContent = `${result.processed} / ${result.total}`;
            
            // 更新当前任务
            document.getElementById('current-browser').textContent = result.current_browser || '-';
            
            // 构建步骤显示文本（包含状态和消息）
            const stepStatus = result.current_step_status || '';
            const stepMessage = result.current_step_message || '';
            const stepName = result.current_step || '-';
            
            // 状态图标映射
            const statusIcon = {
                'running': '🔄',
                'success': '✅',
                'error': '❌',
                'warning': '⚠️',
                'retry': '🔁',
            }[stepStatus] || '';
            
            // 显示格式: [图标] 步骤名 - 消息
            let stepText = stepName;
            if (statusIcon) {
                stepText = `${statusIcon} ${stepName}`;
            }
            if (stepMessage) {
                stepText += ` - ${stepMessage}`;
            }
            document.getElementById('current-step').textContent = stepText;
            
            // 处理日志（使用日志索引去重）
            const logs = result.logs || [];
            for (const log of logs) {
                // 只处理索引大于上次处理的日志
                if (log.idx >= autoState.lastLogIndex) {
                    const time = new Date(log.time * 1000).toLocaleTimeString('zh-CN');
                    addAutoLog('info', log.message, time);
                    autoState.lastLogIndex = log.idx + 1;
                }
            }
            
            // 处理结果，更新账号状态
            (result.results || []).forEach(r => {
                const status = r.final_status || 'error';
                updateAccountStatus(r.browser_id, status);
            });
            
            // 检查是否完成
            if (result.status === 'completed' || result.status === 'stopped') {
                finishAutoProcess();
                
                if (result.status === 'completed') {
                    addAutoLog('success', '🎉 所有任务已完成！');
                    showToast('处理完成！', 'success');
                } else {
                    addAutoLog('warning', '⏹️ 任务已停止');
                    showToast('任务已停止', 'warning');
                }
                
                // 显示结果面板
                renderAutoResults(result.results || []);
            }
        }
    } catch (error) {
        console.error('[AutoProcess] Poll failed:', error);
    }
}

// 更新账号状态
function updateAccountStatus(browserId, status) {
    const item = document.querySelector(`.browser-item[data-id="${browserId}"]`);
    if (item) {
        // 移除旧状态类
        item.classList.remove('pending', 'processing', 'success', 'failed');
        
        // 添加新状态类
        const statusClass = getStatusClass(status);
        item.classList.add(statusClass);
        
        // 更新状态文本
        const statusEl = document.getElementById(`account-status-${browserId}`);
        if (statusEl) {
            statusEl.className = `browser-status ${statusClass}`;
            statusEl.textContent = getStatusText(status);
        }
    }
}

// 完成自动处理
function finishAutoProcess() {
    autoState.isRunning = false;
    stopPolling();
    
    document.getElementById('btn-start-auto').style.display = 'inline-flex';
    document.getElementById('btn-stop-auto').style.display = 'none';
}

// 渲染处理结果
function renderAutoResults(results) {
    const panel = document.getElementById('auto-results-panel');
    const grid = document.getElementById('auto-results-grid');
    
    if (results.length === 0) {
        panel.style.display = 'none';
        return;
    }
    
    panel.style.display = 'block';
    
    grid.innerHTML = results.map(r => {
        const isSuccess = ['subscribed', 'subscribed_antigravity', 'verified'].includes(r.final_status);
        const statusClass = isSuccess ? 'success' : 'failed';
        
        // 生成步骤列表
        const stepsHtml = (r.step_history || []).slice(-5).map(step => {
            const stepClass = step.status === 'success' ? 'completed' : (step.status === 'error' ? 'failed' : '');
            return `<div class="result-step ${stepClass}">${step.step_display || step.step}</div>`;
        }).join('');
        
        return `
            <div class="result-card ${statusClass}">
                <div class="result-email">${escapeHtml(r.email || r.browser_id)}</div>
                <div class="result-status">${getStatusText(r.final_status)}</div>
                <div class="result-steps">${stepsHtml}</div>
            </div>
        `;
    }).join('');
}

// 添加自动处理日志
function addAutoLog(type, message, time = null) {
    const logContainer = document.getElementById('auto-log');
    
    // 移除空状态
    const emptyEl = logContainer.querySelector('.log-empty');
    if (emptyEl) {
        emptyEl.remove();
    }
    
    const timeStr = time || new Date().toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
    
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `<span class="log-time">${timeStr}</span>${escapeHtml(message)}`;
    
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
    
    // 限制日志数量
    while (logContainer.children.length > 200) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// 清空自动处理日志
function clearAutoLog() {
    const logContainer = document.getElementById('auto-log');
    logContainer.innerHTML = '<div class="log-empty">等待开始...</div>';
}

// ==================== SheerLink 提取功能 ====================

const sheerlinkState = {
    accounts: [],
    selectedAccounts: new Set(),
    taskId: null,
    isRunning: false,
    pollInterval: null,
    stats: { 
        total: 0, 
        processed: 0, 
        link_ready: 0,    // 待验证
        verified: 0,      // 已验证未绑卡
        subscribed: 0,    // 已绑卡
        ineligible: 0,    // 无资格
        error: 0          // 错误
    },
    lastLogIndex: 0,  // 跟踪已显示的日志索引
};

function initSheerLinkPage() {
    console.log('[SheerLink] Initializing page...');
    loadSheerLinkAccounts();
}

async function loadSheerLinkAccounts() {
    try {
        const result = await api.post('/api/accounts/for_process', {});
        if (result.success) {
            sheerlinkState.accounts = result.accounts || [];
            sheerlinkState.selectedAccounts.clear();
            renderSheerLinkList();
        }
    } catch (error) {
        console.error('[SheerLink] Load failed:', error);
        showToast(`加载失败: ${error.message}`, 'error');
    }
}

function renderSheerLinkList() {
    const container = document.getElementById('sheerlink-list');
    
    if (sheerlinkState.accounts.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">📭</span><p>暂无账号</p></div>';
        return;
    }
    
    container.innerHTML = sheerlinkState.accounts.map(acc => {
        const isSelected = sheerlinkState.selectedAccounts.has(acc.browser_id);
        const statusClass = getStatusClass(acc.status);
        
        return `
            <div class="browser-item ${isSelected ? 'selected' : ''} ${statusClass}" 
                 data-id="${acc.browser_id}" onclick="toggleSheerLinkSelect('${acc.browser_id}')">
                <input type="checkbox" class="browser-checkbox" ${isSelected ? 'checked' : ''} 
                       onclick="event.stopPropagation(); toggleSheerLinkSelect('${acc.browser_id}')">
                <div class="browser-info">
                    <div class="browser-email">${escapeHtml(acc.email)}</div>
                    <div class="browser-id">窗口: ${acc.browser_id ? acc.browser_id.substring(0, 16) + '...' : '未绑定'}</div>
                </div>
                <span class="browser-status ${statusClass}">${getStatusText(acc.status)}</span>
            </div>
        `;
    }).join('');
    
    updateSheerLinkSelectedCount();
}

function toggleSheerLinkSelect(browserId) {
    if (!browserId || sheerlinkState.isRunning) return;
    
    if (sheerlinkState.selectedAccounts.has(browserId)) {
        sheerlinkState.selectedAccounts.delete(browserId);
    } else {
        sheerlinkState.selectedAccounts.add(browserId);
    }
    renderSheerLinkList();
}

function toggleSheerLinkSelectAll() {
    if (sheerlinkState.isRunning) return;
    
    const isChecked = document.getElementById('sheerlink-select-all').checked;
    if (isChecked) {
        sheerlinkState.accounts.forEach(acc => {
            if (acc.browser_id) sheerlinkState.selectedAccounts.add(acc.browser_id);
        });
    } else {
        sheerlinkState.selectedAccounts.clear();
    }
    renderSheerLinkList();
}

function updateSheerLinkSelectedCount() {
    document.getElementById('sheerlink-selected-count').textContent = sheerlinkState.selectedAccounts.size;
}

async function startSheerLinkProcess() {
    if (sheerlinkState.selectedAccounts.size === 0) {
        showToast('请先选择要处理的账号', 'warning');
        return;
    }
    
    if (!confirm(`确定要提取选中的 ${sheerlinkState.selectedAccounts.size} 个账号的 SheerLink 吗？`)) {
        return;
    }
    
    const browserIds = Array.from(sheerlinkState.selectedAccounts);
    const concurrency = parseInt(document.getElementById('sheerlink-concurrency').value) || 1;
    
    sheerlinkState.stats = { 
        total: browserIds.length, 
        processed: 0, 
        link_ready: 0, 
        verified: 0, 
        subscribed: 0, 
        ineligible: 0, 
        error: 0 
    };
    sheerlinkState.lastLogIndex = 0;  // 重置日志索引
    sheerlinkState.isRunning = true;
    
    document.getElementById('btn-start-sheerlink').style.display = 'none';
    document.getElementById('btn-stop-sheerlink').style.display = 'inline-flex';
    document.getElementById('sheerlink-progress-section').style.display = 'block';
    
    clearSheerLinkLog();
    addSheerLinkLog('info', `开始提取 ${browserIds.length} 个账号，并发: ${concurrency}`);
    
    try {
        const result = await api.post('/api/sheerlink/start', {
            browser_ids: browserIds,
            concurrency: concurrency,
        });
        
        if (result.success) {
            sheerlinkState.taskId = result.task_id;
            startSheerLinkPolling();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        addSheerLinkLog('error', `启动失败: ${error.message}`);
        finishSheerLinkProcess();
    }
}

function stopSheerLinkProcess() {
    if (sheerlinkState.taskId) {
        api.post('/api/task/stop', { task_id: sheerlinkState.taskId });
        addSheerLinkLog('warning', '正在停止...');
    }
}

function startSheerLinkPolling() {
    sheerlinkState.pollInterval = setInterval(pollSheerLinkStatus, 1500);
}

async function pollSheerLinkStatus() {
    if (!sheerlinkState.taskId) return;
    
    try {
        const result = await api.post('/api/task/status', { task_id: sheerlinkState.taskId });
        
        if (result.success) {
            // 解析详细状态 - 从 results 中统计
            const stats = { 
                total: result.total,
                processed: result.processed,
                link_ready: 0, 
                verified: 0, 
                subscribed: 0, 
                ineligible: 0, 
                error: 0 
            };
            
            // 遍历结果统计各状态
            (result.results || []).forEach(r => {
                const msg = (r.message || '').toLowerCase();
                if (msg.includes('link found') || msg.includes('待验证') || msg.includes('link_ready')) {
                    stats.link_ready++;
                } else if (msg.includes('verified') || msg.includes('已验证') || msg.includes('get offer')) {
                    stats.verified++;
                } else if (msg.includes('subscribed') || msg.includes('已绑卡') || msg.includes('已订阅')) {
                    stats.subscribed++;
                } else if (msg.includes('ineligible') || msg.includes('无资格') || msg.includes('not available') || msg.includes('不符合')) {
                    stats.ineligible++;
                } else if (!r.success) {
                    stats.error++;
                }
            });
            
            sheerlinkState.stats = stats;
            updateSheerLinkStats();
            
            const percent = result.total > 0 ? Math.round((result.processed / result.total) * 100) : 0;
            document.getElementById('sheerlink-progress-bar').style.width = `${percent}%`;
            document.getElementById('sheerlink-progress-text').textContent = `${result.processed} / ${result.total}`;
            
            // 只添加新的日志（避免重复）
            const logs = result.logs || [];
            for (let i = sheerlinkState.lastLogIndex; i < logs.length; i++) {
                addSheerLinkLog('info', logs[i].message);
            }
            sheerlinkState.lastLogIndex = logs.length;
            
            if (result.status === 'completed') {
                finishSheerLinkProcess();
                showToast('SheerLink 提取完成!', 'success');
            }
        }
    } catch (error) {
        console.error('[SheerLink] Poll failed:', error);
    }
}

function finishSheerLinkProcess() {
    sheerlinkState.isRunning = false;
    clearInterval(sheerlinkState.pollInterval);
    
    document.getElementById('btn-start-sheerlink').style.display = 'inline-flex';
    document.getElementById('btn-stop-sheerlink').style.display = 'none';
    
    loadSheerLinkAccounts();
}

function updateSheerLinkStats() {
    const s = sheerlinkState.stats;
    document.getElementById('sheerlink-total').textContent = s.total;
    document.getElementById('sheerlink-processed').textContent = s.processed;
    document.getElementById('sheerlink-link-ready').textContent = s.link_ready;
    document.getElementById('sheerlink-verified').textContent = s.verified;
    document.getElementById('sheerlink-subscribed').textContent = s.subscribed;
    document.getElementById('sheerlink-ineligible').textContent = s.ineligible;
    document.getElementById('sheerlink-error').textContent = s.error;
}

function addSheerLinkLog(type, message) {
    const logContainer = document.getElementById('sheerlink-log');
    const emptyEl = logContainer.querySelector('.log-empty');
    if (emptyEl) emptyEl.remove();
    
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `<span class="log-time">${time}</span>${escapeHtml(message)}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function clearSheerLinkLog() {
    document.getElementById('sheerlink-log').innerHTML = '<div class="log-empty">等待开始...</div>';
}

// ==================== 绑卡订阅功能 ====================

const bindcardState = {
    accounts: [],
    selectedAccounts: new Set(),
    taskId: null,
    isRunning: false,
    pollInterval: null,
    stats: { total: 0, processed: 0, success: 0, failed: 0 },
    lastLogIndex: 0,  // 跟踪已显示的日志索引
};

function initBindCardPage() {
    console.log('[BindCard] Initializing page...');
    loadBindCardAccounts();
}

async function loadBindCardAccounts() {
    try {
        const result = await api.post('/api/accounts/verified', {});
        if (result.success) {
            bindcardState.accounts = result.accounts || [];
            bindcardState.selectedAccounts.clear();
            renderBindCardList();
        }
    } catch (error) {
        console.error('[BindCard] Load failed:', error);
        showToast(`加载失败: ${error.message}`, 'error');
    }
}

function renderBindCardList() {
    const container = document.getElementById('bindcard-list');
    
    if (bindcardState.accounts.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">📭</span><p>暂无已验证账号</p></div>';
        return;
    }
    
    container.innerHTML = bindcardState.accounts.map(acc => {
        const isSelected = bindcardState.selectedAccounts.has(acc.browser_id);
        
        return `
            <div class="browser-item ${isSelected ? 'selected' : ''}" 
                 data-id="${acc.browser_id}" onclick="toggleBindCardSelect('${acc.browser_id}')">
                <input type="checkbox" class="browser-checkbox" ${isSelected ? 'checked' : ''} 
                       onclick="event.stopPropagation(); toggleBindCardSelect('${acc.browser_id}')">
                <div class="browser-info">
                    <div class="browser-email">${escapeHtml(acc.email)}</div>
                    <div class="browser-id">窗口: ${acc.browser_id ? acc.browser_id.substring(0, 16) + '...' : '未绑定'}</div>
                </div>
                <span class="browser-status success">✅已验证</span>
            </div>
        `;
    }).join('');
    
    updateBindCardSelectedCount();
}

function toggleBindCardSelect(browserId) {
    if (!browserId || bindcardState.isRunning) return;
    
    if (bindcardState.selectedAccounts.has(browserId)) {
        bindcardState.selectedAccounts.delete(browserId);
    } else {
        bindcardState.selectedAccounts.add(browserId);
    }
    renderBindCardList();
}

function toggleBindCardSelectAll() {
    if (bindcardState.isRunning) return;
    
    const isChecked = document.getElementById('bindcard-select-all').checked;
    if (isChecked) {
        bindcardState.accounts.forEach(acc => {
            if (acc.browser_id) bindcardState.selectedAccounts.add(acc.browser_id);
        });
    } else {
        bindcardState.selectedAccounts.clear();
    }
    renderBindCardList();
}

function updateBindCardSelectedCount() {
    document.getElementById('bindcard-selected-count').textContent = bindcardState.selectedAccounts.size;
}

async function startBindCardProcess() {
    if (bindcardState.selectedAccounts.size === 0) {
        showToast('请先选择要处理的账号', 'warning');
        return;
    }
    
    if (!confirm(`确定要为选中的 ${bindcardState.selectedAccounts.size} 个账号绑卡订阅吗？`)) {
        return;
    }
    
    const browserIds = Array.from(bindcardState.selectedAccounts);
    const concurrency = parseInt(document.getElementById('bindcard-concurrency').value) || 1;
    
    bindcardState.stats = { total: browserIds.length, processed: 0, success: 0, failed: 0 };
    bindcardState.lastLogIndex = 0;  // 重置日志索引
    bindcardState.isRunning = true;
    
    document.getElementById('btn-start-bindcard').style.display = 'none';
    document.getElementById('btn-stop-bindcard').style.display = 'inline-flex';
    document.getElementById('bindcard-progress-section').style.display = 'block';
    
    clearBindCardLog();
    addBindCardLog('info', `开始绑卡 ${browserIds.length} 个账号，并发: ${concurrency}`);
    
    try {
        const result = await api.post('/api/bindcard/start', {
            browser_ids: browserIds,
            concurrency: concurrency,
        });
        
        if (result.success) {
            bindcardState.taskId = result.task_id;
            startBindCardPolling();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        addBindCardLog('error', `启动失败: ${error.message}`);
        finishBindCardProcess();
    }
}

function stopBindCardProcess() {
    if (bindcardState.taskId) {
        api.post('/api/task/stop', { task_id: bindcardState.taskId });
        addBindCardLog('warning', '正在停止...');
    }
}

function startBindCardPolling() {
    bindcardState.pollInterval = setInterval(pollBindCardStatus, 1500);
}

async function pollBindCardStatus() {
    if (!bindcardState.taskId) return;
    
    try {
        const result = await api.post('/api/task/status', { task_id: bindcardState.taskId });
        
        if (result.success) {
            bindcardState.stats = {
                total: result.total,
                processed: result.processed,
                success: result.success_count,
                failed: result.failed_count,
            };
            
            updateBindCardStats();
            
            const percent = result.total > 0 ? Math.round((result.processed / result.total) * 100) : 0;
            document.getElementById('bindcard-progress-bar').style.width = `${percent}%`;
            document.getElementById('bindcard-progress-text').textContent = `${result.processed} / ${result.total}`;
            
            // 只添加新的日志（避免重复）
            const logs = result.logs || [];
            for (let i = bindcardState.lastLogIndex; i < logs.length; i++) {
                addBindCardLog('info', logs[i].message);
            }
            bindcardState.lastLogIndex = logs.length;
            
            if (result.status === 'completed') {
                finishBindCardProcess();
                showToast('绑卡完成!', 'success');
            }
        }
    } catch (error) {
        console.error('[BindCard] Poll failed:', error);
    }
}

function finishBindCardProcess() {
    bindcardState.isRunning = false;
    clearInterval(bindcardState.pollInterval);
    
    document.getElementById('btn-start-bindcard').style.display = 'inline-flex';
    document.getElementById('btn-stop-bindcard').style.display = 'none';
    
    loadBindCardAccounts();
}

function updateBindCardStats() {
    document.getElementById('bindcard-total').textContent = bindcardState.stats.total;
    document.getElementById('bindcard-processed').textContent = bindcardState.stats.processed;
    document.getElementById('bindcard-success').textContent = bindcardState.stats.success;
    document.getElementById('bindcard-failed').textContent = bindcardState.stats.failed;
}

function addBindCardLog(type, message) {
    const logContainer = document.getElementById('bindcard-log');
    const emptyEl = logContainer.querySelector('.log-empty');
    if (emptyEl) emptyEl.remove();
    
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `<span class="log-time">${time}</span>${escapeHtml(message)}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function clearBindCardLog() {
    document.getElementById('bindcard-log').innerHTML = '<div class="log-empty">等待开始...</div>';
}


// ==================== 批量更改2FA功能 ====================

const change2faState = {
    accounts: [],
    selectedAccounts: new Set(),
    taskId: null,
    isRunning: false,
    pollInterval: null,
    stats: { total: 0, processed: 0, success: 0, failed: 0 },
    lastLogIndex: 0,  // 跟踪已处理的日志索引
};

function initChange2FAPage() {
    console.log('[Change2FA] Initializing page...');
    loadChange2FAAccounts();
}

async function loadChange2FAAccounts() {
    try {
        // 获取有2FA密钥的账号
        const result = await api.post('/api/accounts/for_process', {});
        if (result.success) {
            // 过滤出有2FA密钥的账号
            change2faState.accounts = (result.accounts || []).filter(acc => acc.twofa_key && acc.twofa_key.length > 0);
            change2faState.selectedAccounts.clear();
            renderChange2FAList();
        }
    } catch (error) {
        console.error('[Change2FA] Load failed:', error);
        showToast(`加载失败: ${error.message}`, 'error');
    }
}

function renderChange2FAList() {
    const container = document.getElementById('change2fa-list');
    
    if (change2faState.accounts.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">📭</span><p>暂无有2FA密钥的账号</p></div>';
        return;
    }
    
    container.innerHTML = change2faState.accounts.map(acc => {
        const isSelected = change2faState.selectedAccounts.has(acc.browser_id);
        const statusClass = getStatusClass(acc.status);
        
        return `
            <div class="browser-item ${isSelected ? 'selected' : ''} ${statusClass}" 
                 data-id="${acc.browser_id}" onclick="toggleChange2FASelect('${acc.browser_id}')">
                <input type="checkbox" class="browser-checkbox" ${isSelected ? 'checked' : ''} 
                       onclick="event.stopPropagation(); toggleChange2FASelect('${acc.browser_id}')">
                <div class="browser-info">
                    <div class="browser-email">${escapeHtml(acc.email)}</div>
                    <div class="browser-id">2FA: ${acc.twofa_key ? acc.twofa_key.substring(0, 8) + '...' : '无'}</div>
                </div>
                <span class="browser-status ${statusClass}">${getStatusText(acc.status)}</span>
            </div>
        `;
    }).join('');
    
    updateChange2FASelectedCount();
}

function toggleChange2FASelect(browserId) {
    if (!browserId || change2faState.isRunning) return;
    
    if (change2faState.selectedAccounts.has(browserId)) {
        change2faState.selectedAccounts.delete(browserId);
    } else {
        change2faState.selectedAccounts.add(browserId);
    }
    renderChange2FAList();
}

function toggleChange2FASelectAll() {
    if (change2faState.isRunning) return;
    
    const isChecked = document.getElementById('change2fa-select-all').checked;
    if (isChecked) {
        change2faState.accounts.forEach(acc => {
            if (acc.browser_id) change2faState.selectedAccounts.add(acc.browser_id);
        });
    } else {
        change2faState.selectedAccounts.clear();
    }
    renderChange2FAList();
}

function updateChange2FASelectedCount() {
    document.getElementById('change2fa-selected-count').textContent = change2faState.selectedAccounts.size;
}

async function startChange2FAProcess() {
    if (change2faState.selectedAccounts.size === 0) {
        showToast('请先选择要处理的账号', 'warning');
        return;
    }
    
    if (!confirm(`确定要更改选中的 ${change2faState.selectedAccounts.size} 个账号的2FA密钥吗？\n\n⚠️ 注意：更改后原2FA密钥将失效！`)) {
        return;
    }
    
    const browserIds = Array.from(change2faState.selectedAccounts);
    const concurrency = parseInt(document.getElementById('change2fa-concurrency').value) || 1;
    
    change2faState.stats = { total: browserIds.length, processed: 0, success: 0, failed: 0 };
    change2faState.lastLogIndex = 0;
    change2faState.isRunning = true;
    
    document.getElementById('btn-start-change2fa').style.display = 'none';
    document.getElementById('btn-stop-change2fa').style.display = 'inline-flex';
    document.getElementById('change2fa-progress-section').style.display = 'block';
    
    clearChange2FALog();
    addChange2FALog('info', `开始更改 ${browserIds.length} 个账号的2FA密钥，并发: ${concurrency}`);
    
    try {
        const result = await api.post('/api/change2fa/start', {
            browser_ids: browserIds,
            concurrency: concurrency,
        });
        
        if (result.success) {
            change2faState.taskId = result.task_id;
            startChange2FAPolling();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        addChange2FALog('error', `启动失败: ${error.message}`);
        finishChange2FAProcess();
    }
}

function stopChange2FAProcess() {
    if (change2faState.taskId) {
        api.post('/api/task/stop', { task_id: change2faState.taskId });
        addChange2FALog('warning', '正在停止...');
    }
}

function startChange2FAPolling() {
    change2faState.pollInterval = setInterval(pollChange2FAStatus, 1500);
}

async function pollChange2FAStatus() {
    if (!change2faState.taskId) return;
    
    try {
        const result = await api.post('/api/task/status', { task_id: change2faState.taskId });
        
        if (result.success) {
            change2faState.stats = {
                total: result.total,
                processed: result.processed,
                success: result.success_count,
                failed: result.failed_count,
            };
            
            updateChange2FAStats();
            
            const percent = result.total > 0 ? Math.round((result.processed / result.total) * 100) : 0;
            document.getElementById('change2fa-progress-bar').style.width = `${percent}%`;
            document.getElementById('change2fa-progress-text').textContent = `${result.processed} / ${result.total}`;
            
            // 只添加新的日志
            const logs = result.logs || [];
            for (let i = change2faState.lastLogIndex; i < logs.length; i++) {
                addChange2FALog('info', logs[i].message);
            }
            change2faState.lastLogIndex = logs.length;
            
            if (result.status === 'completed') {
                finishChange2FAProcess();
                showToast('2FA密钥更改完成!', 'success');
            }
        }
    } catch (error) {
        console.error('[Change2FA] Poll failed:', error);
    }
}

function finishChange2FAProcess() {
    change2faState.isRunning = false;
    clearInterval(change2faState.pollInterval);
    
    document.getElementById('btn-start-change2fa').style.display = 'inline-flex';
    document.getElementById('btn-stop-change2fa').style.display = 'none';
    
    loadChange2FAAccounts();
}

function updateChange2FAStats() {
    document.getElementById('change2fa-total').textContent = change2faState.stats.total;
    document.getElementById('change2fa-processed').textContent = change2faState.stats.processed;
    document.getElementById('change2fa-success').textContent = change2faState.stats.success;
    document.getElementById('change2fa-failed').textContent = change2faState.stats.failed;
}

function addChange2FALog(type, message) {
    const logContainer = document.getElementById('change2fa-log');
    const emptyEl = logContainer.querySelector('.log-empty');
    if (emptyEl) emptyEl.remove();
    
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `<span class="log-time">${time}</span>${escapeHtml(message)}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function clearChange2FALog() {
    document.getElementById('change2fa-log').innerHTML = '<div class="log-empty">等待开始...</div>';
}
