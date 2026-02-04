"""
创建比特浏览器新窗口
根据示例窗口的参数创建新窗口，从accounts.txt读取账户信息
"""
import requests
import json
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# 比特浏览器API地址
url = "http://127.0.0.1:54345"
headers = {'Content-Type': 'application/json'}


def read_proxies(file_path: str = None) -> list:
    """
    从数据库读取代理信息（兼容旧接口，file_path参数已弃用）
    
    Args:
        file_path: [已弃用] 代理文件路径，保留仅为兼容性
        
    Returns:
        代理列表，每个代理为字典格式 {'type': 'socks5', 'host': '', 'port': '', 'username': '', 'password': ''}
    """
    try:
        from database import DBManager
        DBManager.init_db()
        
        db_proxies = DBManager.get_available_proxies()
        
        # 转换为旧格式
        proxies = []
        for p in db_proxies:
            proxies.append({
                'type': p.get('proxy_type', 'socks5'),
                'host': p.get('host', ''),
                'port': p.get('port', ''),
                'username': p.get('username', ''),
                'password': p.get('password', ''),
                'id': p.get('id')  # 保留ID用于标记已使用
            })
        
        return proxies
    except Exception as e:
        print(f"[警告] 从数据库读取代理失败: {e}")
        return []


def read_separator_config(file_path: str) -> str:
    """
    从文件顶部读取分隔符配置
    
    格式: 分隔符="----"
    
    Returns:
        分隔符字符串，默认为 "----"
    """
    default_sep = "----"
    
    if not os.path.exists(file_path):
        return default_sep
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # 查找分隔符配置行
                if line.startswith('分隔符=') or line.startswith('separator='):
                    # 提取引号内的内容
                    import re
                    match = re.search(r'["\'](.+?)["\']', line)
                    if match:
                        return match.group(1)
                # 如果遇到非注释、非配置行，停止搜索
                if not line.startswith('#') and '=' not in line:
                    break
    except Exception:
        pass
    
    return default_sep


def parse_account_line(line: str, separator: str) -> dict:
    """
    根据指定分隔符解析账号信息行（智能识别字段）
    
    Args:
        line: 账号信息行
        separator: 分隔符
        
    Returns:
        解析后的账号字典
    """
    import re
    
    # 移除注释
    if '#' in line:
        comment_pos = line.find('#')
        line = line[:comment_pos].strip()
    
    if not line:
        return None
    
    # 使用指定分隔符分割
    parts = line.split(separator)
    parts = [p.strip() for p in parts if p.strip()]
    
    if len(parts) < 2:
        return None
    
    result = {
        'email': '',
        'password': '',
        'backup_email': '',
        '2fa_secret': '',
        'full_line': line
    }
    
    # 分类所有字段
    emails = []
    secrets = []
    others = []
    
    for part in parts:
        if '@' in part and '.' in part:
            # 邮箱格式：包含@和.
            emails.append(part)
        elif re.match(r'^[A-Z0-9]{16,}$', part):
            # 2FA密钥格式：16位以上，只包含大写字母和数字（常见Base32编码）
            secrets.append(part)
        else:
            # 其他（密码）
            others.append(part)
    
    # 分配字段
    if len(emails) >= 1:
        result['email'] = emails[0]
    if len(emails) >= 2:
        result['backup_email'] = emails[1]
    
    if len(secrets) >= 1:
        result['2fa_secret'] = secrets[0]
    
    if len(others) >= 1:
        result['password'] = others[0]
    
    return result if result['email'] else None


def read_accounts(file_path: str) -> list:
    """
    读取账户信息文件（使用配置的分隔符）
    
    文件格式：
    第一行（可选）：分隔符="----"
    后续行：邮箱[分隔符]密码[分隔符]辅助邮箱[分隔符]2FA密钥
    
    Args:
        file_path: 账户文件路径
        
    Returns:
        账户列表，每个账户为字典格式
    """
    accounts = []
    
    if not os.path.exists(file_path):
        print(f"错误: 找不到文件 {file_path}")
        return accounts
    
    # 读取分隔符配置
    separator = read_separator_config(file_path)
    print(f"使用分隔符: '{separator}'")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                
                # 跳过配置行
                if line.startswith('分隔符=') or line.startswith('separator='):
                    continue
                
                account = parse_account_line(line, separator)
                if account:
                    accounts.append(account)
                else:
                    print(f"警告: 第{line_num}行格式不正确: {line[:50]}")
    except Exception as e:
        print(f"读取文件出错: {e}")
    
    return accounts


def get_browser_list(page: int = 0, pageSize: int = 50):
    """
    获取所有窗口列表
    
    Args:
        page: 页码，默认为0
        pageSize: 每页数量，默认为50
    
    Returns:
        窗口列表
    """
    try:
        json_data = {
            "page": page,
            "pageSize": pageSize
        }
        response = requests.post(
            f"{url}/browser/list",
            json=json_data,
            headers=headers,
            timeout=10
        )
        result = response.json()
        
        if result.get('success'):
            data = result.get('data', {})
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get('list', [])
        return []
    except Exception as e:
        print(f"获取浏览器列表失败: {e}")
        return []


def get_browser_info(browser_id: str):
    """
    获取指定窗口的详细信息
    
    Args:
        browser_id: 窗口ID
        
    Returns:
        窗口信息字典
    """
    browsers = get_browser_list()
    for browser in browsers:
        if browser.get('id') == browser_id:
            return browser
    return None


def delete_browsers_by_name(name_pattern: str):
    """
    根据名称删除所有匹配的窗口
    
    Args:
        name_pattern: 窗口名称（精确匹配）
        
    Returns:
        删除的窗口数量
    """
    browsers = get_browser_list()
    deleted_count = 0
    
    for browser in browsers:
        if browser.get('name') == name_pattern:
            browser_id = browser.get('id')
            try:
                res = requests.post(
                    f"{url}/browser/delete",
                    json={'id': browser_id},
                    headers=headers,
                    timeout=10
                ).json()
                
                if res.get('code') == 0 or res.get('success') == True:
                    deleted_count += 1
            except Exception:
                pass
    
    return deleted_count


def open_browser_by_id(browser_id: str):
    """
    打开指定ID的窗口（使用新API）
    
    Args:
        browser_id: 窗口ID
        
    Returns:
        bool: 是否调用成功
    """
    try:
        api = get_api()
        result = api.open_browser(browser_id, queue=True)
        return result['success']
    except Exception:
        return False


def delete_browser_by_id(browser_id: str):
    """
    删除指定ID的窗口（使用新API）
    
    Args:
        browser_id: 窗口ID
        
    Returns:
        bool: 是否删除成功
    """
    try:
        api = get_api()
        result = api.delete_browser(browser_id)
        return result['success']
    except Exception:
        return False


def get_next_window_name(prefix: str):
    """
    根据前缀生成下一个窗口名称，格式：前缀_序号
    
    Args:
        prefix: 窗口名称前缀
        
    Returns:
        下一个窗口名称，如 "美国_1"
    """
    browsers = get_browser_list()
    max_num = 0
    
    # 遍历所有窗口，找到匹配前缀的最大序号
    prefix_pattern = f"{prefix}_"
    for browser in browsers:
        name = browser.get('name', '')
        if name == prefix: # 精确匹配前缀（视为序号0或1，视情况而定，这里假设如果不带序号算占用）
             pass # 简单起见，我们只看带下划线的，或者如果只有前缀，我们从1开始
             
        if name.startswith(prefix_pattern):
            try:
                # 尝试提取后缀数字
                suffix = name[len(prefix_pattern):]
                num = int(suffix)
                if num > max_num:
                    max_num = num
            except:
                pass
    
    return f"{prefix}_{max_num + 1}"


def open_browser_url(browser_id: str, target_url: str):
    """打开浏览器窗口并导航到指定URL（使用新API）"""
    try:
        api = get_api()
        result = api.open_browser(browser_id, queue=True)
        
        if result['success']:
            driver_path = result['data'].get('driver')
            debugger_address = result['data'].get('http')
            
            if driver_path and debugger_address:
                try:
                    chrome_options = Options()
                    chrome_options.add_experimental_option("debuggerAddress", debugger_address)
                    chrome_service = Service(driver_path)
                    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
                    driver.get(target_url)
                    time.sleep(2)
                    driver.quit()
                except Exception:
                    pass
    except Exception:
        pass


def create_browser_window(account: dict, reference_browser_id: str = None, proxy: dict = None, platform: str = None, extra_url: str = None, name_prefix: str = None, template_config: dict = None):
    """
    创建新的浏览器窗口
    
    Args:
        account: 账户信息
        reference_browser_id: 参考窗口ID
        proxy: 代理信息
        platform: 平台URL
        extra_url: 额外URL
        name_prefix: 窗口名称前缀
        template_config: 直接提供的模板配置字典 (优先级高于 reference_browser_id)
        
    Returns:
        (browser_id, error_message)
    """
    if template_config:
        reference_config = template_config
    elif reference_browser_id:
        reference_config = get_browser_info(reference_browser_id)
        if not reference_config:
            return None, f"找不到参考窗口: {reference_browser_id}"
    else:
        return None, "未指定参考窗口ID或模板配置"
    
    json_data = {}
    exclude_fields = {'id', 'name', 'remark', 'userName', 'password', 'faSecretKey', 'createTime', 'updateTime'}
    
    for key, value in reference_config.items():
        if key not in exclude_fields:
            json_data[key] = value
    
    # 确定窗口名称
    if name_prefix:
        final_prefix = name_prefix
    else:
        # 如果未指定前缀，尝试从参考窗口名称推断
        ref_name = reference_config.get('name', '')
        if '_' in ref_name:
            final_prefix = '_'.join(ref_name.split('_')[:-1])
        else:
            final_prefix = ref_name
            
    json_data['name'] = get_next_window_name(final_prefix)
    
    # 构建备注（格式：email----password----backup_email----2fa_secret，空的留空）
    remark_parts = [
        account.get('email', ''),
        account.get('password', ''),
        account.get('backup_email', ''),
        account.get('2fa_secret', '')
    ]
    json_data['remark'] = '----'.join(remark_parts)
    
    if platform:
        json_data['platform'] = platform
    if extra_url:
        json_data['url'] = extra_url
    
    if account.get('email'):
        json_data['userName'] = account['email']
    if account.get('password'):
        json_data['password'] = account['password']
    if account.get('2fa_secret') and account['2fa_secret'].strip():
        json_data['faSecretKey'] = account['2fa_secret'].strip()
    
    if 'browserFingerPrint' not in json_data:
        json_data['browserFingerPrint'] = {}
    
    if 'browserFingerPrint' in reference_config:
        ref_fp = reference_config['browserFingerPrint']
        if isinstance(ref_fp, dict):
            for key, value in ref_fp.items():
                if key != 'id':
                    json_data['browserFingerPrint'][key] = value
    
    json_data['browserFingerPrint']['coreVersion'] = '140'
    json_data['browserFingerPrint']['version'] = '140'
    
    if proxy:
        json_data['proxyType'] = proxy['type']
        json_data['proxyMethod'] = 2
        json_data['host'] = proxy['host']
        json_data['port'] = proxy['port']
        json_data['proxyUserName'] = proxy['username']
        json_data['proxyPassword'] = proxy['password']
    else:
        json_data['proxyType'] = 'noproxy'
        json_data['proxyMethod'] = 2
        json_data['host'] = ''
        json_data['port'] = ''
        json_data['proxyUserName'] = ''
        json_data['proxyPassword'] = ''
    
    
    # 检查是否已存在该账号的窗口
    all_browsers = get_browser_list()
    for b in all_browsers:
        if b.get('userName') == account['email']:
            return None, f"该账号已有对应窗口: {b.get('name')} (ID: {b.get('id')})"

    try:
        # 创建窗口
        res = requests.post(
            f"{url}/browser/update",
            json=json_data,
            headers=headers,
            timeout=30
        ).json()
        
        if res.get('success'):
            browser_id = res.get('data', {}).get('id')
            if not browser_id:
                return None, "API返回成功但未获取到ID"
            
            created_config = get_browser_info(browser_id)
            need_update = False
            if created_config:
                if created_config.get('userName') != account['email']:
                    need_update = True
                if created_config.get('password') != account['password']:
                    need_update = True
                if account.get('2fa_secret') and account['2fa_secret'].strip():
                    if created_config.get('faSecretKey') != account['2fa_secret'].strip():
                        need_update = True
            
            if need_update or 'userName' not in json_data:
                update_data = {
                    'ids': [browser_id],
                    'userName': account['email'],
                    'password': account['password']
                }
                
                if account.get('2fa_secret') and account['2fa_secret'].strip():
                    update_data['faSecretKey'] = account['2fa_secret'].strip()
                
                try:
                    update_res = requests.post(
                        f"{url}/browser/update/partial",
                        json=update_data,
                        headers=headers,
                        timeout=10
                    ).json()
                    
                    if not update_res.get('success'):
                        if 'faSecretKey' in update_data:
                            retry_data = {
                                'ids': [browser_id],
                                'userName': account['email'],
                                'password': account['password']
                            }
                            requests.post(
                                f"{url}/browser/update/partial",
                                json=retry_data,
                                headers=headers,
                                timeout=10
                            )
                except Exception:
                    pass
            
            if account.get('2fa_secret') and account['2fa_secret'].strip():
                verify_config = get_browser_info(browser_id)
                if not (verify_config and verify_config.get('faSecretKey') == account['2fa_secret'].strip()):
                    try:
                        twofa_data = {
                            'ids': [browser_id],
                            'faSecretKey': account['2fa_secret'].strip()
                        }
                        requests.post(
                            f"{url}/browser/update/partial",
                            json=twofa_data,
                            headers=headers,
                            timeout=10
                        )
                    except Exception:
                        pass
            
            # 如果使用了代理，标记代理已使用
            if proxy and proxy.get('id'):
                try:
                    from database import DBManager
                    DBManager.mark_proxy_used(proxy['id'], account['email'])
                except Exception as e:
                    print(f"[警告] 标记代理已使用失败: {e}")
            
            return browser_id, None
        
        error_msg = res.get('msg', '未知API错误')
        return None, f"创建请求被拒绝: {error_msg}"
        
    except Exception as e:
        return None, f"请求异常: {str(e)}"



def print_browser_info(browser_id: str):
    """打印窗口的完整配置信息"""
    config = get_browser_info(browser_id)
    if config:
        print(json.dumps(config, indent=2, ensure_ascii=False))


def main():
    accounts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'accounts.txt')
    accounts = read_accounts(accounts_file)
    
    if not accounts:
        return
    
    proxies_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'proxies.txt')
    proxies = read_proxies(proxies_file)
    
    browsers = get_browser_list()
    if not browsers:
        return
    
    reference_browser_id = "4964d1fe7e584e868f14975f4c22e106"
    reference_config = get_browser_info(reference_browser_id)
    if not reference_config:
        browsers = get_browser_list()
        if browsers:
            reference_browser_id = browsers[0].get('id')
        else:
            return
    
    success_count = 0
    for i, account in enumerate(accounts, 1):
        proxy = proxies[i - 1] if i - 1 < len(proxies) else None
        browser_id, error = create_browser_window(account, reference_browser_id, proxy)
        if browser_id:
            success_count += 1
        else:
            print(f"窗口创建失败: {error}")
        if i < len(accounts):
            time.sleep(1)
    
    print(f"完成: {success_count}/{len(accounts)}")


if __name__ == "__main__":
    main()

