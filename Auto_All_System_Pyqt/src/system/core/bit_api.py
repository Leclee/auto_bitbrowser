"""
@file bit_api.py
@brief 比特浏览器 Local API 封装
@details 完整的比特浏览器API封装，基于官方文档 https://doc2.bitbrowser.cn/
         所有接口使用 POST 方法，body 传参，json 格式
"""

import requests
import json
from typing import Optional, Dict, List, Any


class BitBrowserAPI:
    """
    @class BitBrowserAPI
    @brief 比特浏览器API类
    @details 封装所有比特浏览器Local API接口
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:54345"):
        """
        @brief 初始化API
        @param base_url Local Server地址，默认 http://127.0.0.1:54345
        """
        self.base_url = base_url
        self.headers = {'Content-Type': 'application/json'}
    
    def _request(self, endpoint: str, data: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
        """
        @brief 发送POST请求
        @param endpoint API端点
        @param data 请求数据（dict）
        @param timeout 超时时间（秒）
        @return 响应JSON
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(
                url,
                json=data if data else {},
                headers=self.headers,
                timeout=timeout
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "msg": f"请求失败: {str(e)}"}
        except json.JSONDecodeError:
            return {"success": False, "msg": "响应JSON解析失败"}
    
    # ==================== 健康检查 ====================
    
    def health_check(self) -> Dict:
        """
        @brief 健康检查，测试Local Server是否连接成功
        @return {"success": True}
        """
        return self._request("/health")
    
    # ==================== 浏览器窗口接口 ====================
    
    def create_browser(self, 
                      name: str = "new browser",
                      group_id: Optional[str] = None,
                      browser_fingerprint: Optional[Dict] = None,
                      proxy_method: int = 2,
                      proxy_type: str = "noproxy",
                      **kwargs) -> Dict:
        """
        @brief 创建浏览器窗口
        @param name 窗口名称
        @param group_id 分组ID，不传则创建到API分组
        @param browser_fingerprint 指纹对象，不传则传空对象 {}
        @param proxy_method 代理方式，2=自定义，3=提取IP
        @param proxy_type 代理类型：noproxy/http/https/socks5/ssh
        @param kwargs 其他参数
        @return 创建结果
        """
        data = {
            "name": name,
            "proxyMethod": proxy_method,
            "proxyType": proxy_type,
            "browserFingerPrint": browser_fingerprint if browser_fingerprint is not None else {}
        }
        
        if group_id:
            data["groupId"] = group_id
        
        # 添加其他可选参数
        optional_fields = [
            'platform', 'url', 'remark', 'userName', 'password', 'isSynOpen',
            'faSecretKey', 'cookie', 'host', 'port', 'ipCheckService', 'isIpv6',
            'proxyUserName', 'proxyPassword', 'refreshProxyUrl', 'enableSocks5Udp',
            'country', 'province', 'city', 'workbench', 'abortImage', 'abortImageMaxSize',
            'abortMedia', 'muteAudio', 'stopWhileNetError', 'stopWhileIpChange',
            'stopWhileCountryChange', 'dynamicIpUrl', 'dynamicIpChannel',
            'isDynamicIpChangeIp', 'duplicateCheck', 'isGlobalProxyInfo',
            'syncTabs', 'syncCookies', 'syncIndexedDb', 'syncLocalStorage',
            'syncBookmarks', 'syncAuthorization', 'syncHistory', 'syncExtensions',
            'isValidUsername', 'allowedSignin', 'clearCacheFilesBeforeLaunch',
            'clearCacheWithoutExtensions', 'clearCookiesBeforeLaunch',
            'clearHistoriesBeforeLaunch', 'randomFingerprint', 'disableGpu',
            'disableTranslatePopup', 'disableNotifications', 'disableClipboard',
            'memorySaver', 'credentialsEnableService'
        ]
        
        for field in optional_fields:
            if field in kwargs:
                data[field] = kwargs[field]
        
        return self._request("/browser/update", data)
    
    def update_browser_partial(self, 
                              browser_ids: List[str],
                              updates: Dict) -> Dict:
        """
        @brief 批量修改窗口指定字段
        @param browser_ids 窗口ID列表
        @param updates 要更新的字段字典
        @return 更新结果
        """
        data = {
            "ids": browser_ids,
            **updates
        }
        return self._request("/browser/update/partial", data)
    
    def open_browser(self, 
                    browser_id: str,
                    args: Optional[List[str]] = None,
                    queue: bool = True,
                    ignore_default_urls: bool = False,
                    new_page_url: Optional[str] = None) -> Dict:
        """
        @brief 打开浏览器窗口
        @param browser_id 窗口ID
        @param args 启动参数列表
        @param queue 是否队列方式打开（防止并发报错）
        @param ignore_default_urls 忽略已同步的url
        @param new_page_url 指定open时打开的url
        @return 打开结果，包含ws和http连接地址
        """
        data = {
            "id": browser_id,
            "queue": queue
        }
        
        if args:
            data["args"] = args
        if ignore_default_urls:
            data["ignoreDefaultUrls"] = ignore_default_urls
        if new_page_url:
            data["newPageUrl"] = new_page_url
        
        return self._request("/browser/open", data, timeout=60)
    
    def close_browser(self, browser_id: str) -> Dict:
        """
        @brief 关闭浏览器窗口
        @param browser_id 窗口ID
        @return 关闭结果
        """
        return self._request("/browser/close", {"id": browser_id})
    
    def reset_closing_status(self, browser_id: str) -> Dict:
        """
        @brief 重置浏览器关闭状态
        @param browser_id 窗口ID
        @return 重置结果
        """
        return self._request("/browser/closing/reset", {"id": browser_id})
    
    def delete_browser(self, browser_id: str) -> Dict:
        """
        @brief 删除浏览器窗口（彻底删除，无法恢复）
        @param browser_id 窗口ID
        @return 删除结果
        """
        return self._request("/browser/delete", {"id": browser_id})
    
    def get_browser_detail(self, browser_id: str) -> Dict:
        """
        @brief 获取浏览器窗口详情
        @param browser_id 窗口ID
        @return 窗口详细信息
        """
        return self._request("/browser/detail", {"id": browser_id})
    
    def list_browsers(self, 
                     page: int = 0,
                     page_size: int = 10,
                     group_id: Optional[str] = None,
                     name: Optional[str] = None,
                     remark: Optional[str] = None,
                     seq: Optional[int] = None,
                     min_seq: Optional[int] = None,
                     max_seq: Optional[int] = None,
                     sort: str = "desc") -> Dict:
        """
        @brief 分页获取浏览器窗口列表
        @param page 页码，从0开始
        @param page_size 每页数量，最大100
        @param group_id 分组ID筛选
        @param name 窗口名称模糊匹配
        @param remark 备注模糊匹配
        @param seq 序号精确查询
        @param min_seq 最小序号（范围查询）
        @param max_seq 最大序号（范围查询）
        @param sort 排序：desc/asc
        @return 窗口列表
        """
        data = {
            "page": page,
            "pageSize": min(page_size, 100),
            "sort": sort
        }
        
        if group_id:
            data["groupId"] = group_id
        if name:
            data["name"] = name
        if remark:
            data["remark"] = remark
        if seq is not None:
            data["seq"] = seq
        if min_seq is not None:
            data["minSeq"] = min_seq
        if max_seq is not None:
            data["maxSeq"] = max_seq
        
        return self._request("/browser/list", data)
    
    def arrange_windows(self,
                       window_type: str = "box",
                       start_x: int = 0,
                       start_y: int = 0,
                       width: int = 500,
                       height: int = 400,
                       col: int = 3,
                       space_x: int = 0,
                       space_y: int = 0,
                       offset_x: int = 50,
                       offset_y: int = 50,
                       order_by: str = "asc",
                       ids: Optional[List[str]] = None,
                       seqlist: Optional[List[int]] = None,
                       screen_id: Optional[int] = None) -> Dict:
        """
        @brief 排列窗口
        @param window_type 排列方式：box=宫格，diagonal=对角线
        @param start_x 起始X位置
        @param start_y 起始Y位置
        @param width 窗口宽度（最小500）
        @param height 窗口高度（最小200）
        @param col 宫格每行列数
        @param space_x 宫格横向间距
        @param space_y 宫格纵向间距
        @param offset_x 对角线横向偏移
        @param offset_y 对角线纵向偏移
        @param order_by 排序：asc/desc
        @param ids 窗口ID列表
        @param seqlist 窗口序号列表
        @param screen_id 显示器ID
        @return 排列结果
        """
        data = {
            "type": window_type,
            "startX": start_x,
            "startY": start_y,
            "width": max(width, 500),
            "height": max(height, 200),
            "col": col,
            "spaceX": space_x,
            "spaceY": space_y,
            "offsetX": offset_x,
            "offsetY": offset_y,
            "orderBy": order_by
        }
        
        if ids:
            data["ids"] = ids
        elif seqlist:
            data["seqlist"] = seqlist
        
        if screen_id is not None:
            data["screenId"] = screen_id
        
        return self._request("/windowbounds", data)
    
    def arrange_windows_flexible(self, seqlist: Optional[List[int]] = None) -> Dict:
        """
        @brief 一键自适应排列窗口
        @param seqlist 窗口序号列表，不传则排列全部
        @return 排列结果
        """
        data = {"seqlist": seqlist if seqlist else []}
        return self._request("/windowbounds/flexable", data)
    
    def update_browser_group(self, group_id: str, browser_ids: List[str]) -> Dict:
        """
        @brief 批量修改窗口分组
        @param group_id 目标分组ID
        @param browser_ids 窗口ID列表
        @return 更新结果
        """
        data = {
            "groupId": group_id,
            "browserIds": browser_ids
        }
        return self._request("/browser/group/update", data)
    
    def update_browser_proxy(self, 
                            browser_ids: List[str],
                            proxy_method: int = 2,
                            proxy_type: str = "noproxy",
                            **proxy_config) -> Dict:
        """
        @brief 批量修改窗口代理
        @param browser_ids 窗口ID列表
        @param proxy_method 代理方式，2=自定义，3=提取IP
        @param proxy_type 代理类型
        @param proxy_config 代理配置
        @return 更新结果
        """
        data = {
            "ids": browser_ids,
            "proxyMethod": proxy_method,
            "proxyType": proxy_type,
            **proxy_config
        }
        return self._request("/browser/proxy/update", data)
    
    def update_browser_remark(self, browser_ids: List[str], remark: str) -> Dict:
        """
        @brief 批量修改窗口备注
        @param browser_ids 窗口ID列表
        @param remark 备注内容
        @return 更新结果
        """
        data = {
            "browserIds": browser_ids,
            "remark": remark
        }
        return self._request("/browser/remark/update", data)
    
    def close_browsers_by_seqs(self, seqs: List[int]) -> Dict:
        """
        @brief 通过序号批量关闭窗口
        @param seqs 窗口序号列表
        @return 关闭结果
        """
        return self._request("/browser/close/byseqs", {"seqs": seqs})
    
    def close_all_browsers(self) -> Dict:
        """
        @brief 关闭所有窗口
        @return 关闭结果
        """
        return self._request("/browser/close/all")
    
    def get_browser_pids(self, browser_ids: List[str]) -> Dict:
        """
        @brief 获取已打开窗口的进程PID
        @param browser_ids 窗口ID列表
        @return PID字典 {browser_id: pid}
        """
        return self._request("/browser/pids", {"ids": browser_ids})
    
    def get_all_browser_pids(self) -> Dict:
        """
        @brief 获取所有活着的已打开窗口的进程PID
        @return PID字典
        """
        return self._request("/browser/pids/all")
    
    def get_alive_browser_pids(self, browser_ids: List[str]) -> Dict:
        """
        @brief 获取活着的窗口PID（会检查进程）
        @param browser_ids 窗口ID列表
        @return PID字典
        """
        return self._request("/browser/pids/alive", {"ids": browser_ids})
    
    def delete_browsers(self, browser_ids: List[str]) -> Dict:
        """
        @brief 批量删除窗口（最多100个）
        @param browser_ids 窗口ID列表
        @return 删除结果
        """
        return self._request("/browser/delete/ids", {"ids": browser_ids[:100]})
    
    def clear_browser_cache(self, browser_ids: List[str]) -> Dict:
        """
        @brief 清理窗口缓存（本地+服务端）
        @param browser_ids 窗口ID列表
        @return 清理结果
        """
        return self._request("/cache/clear", {"ids": browser_ids})
    
    def clear_cache_except_extensions(self, browser_ids: List[str]) -> Dict:
        """
        @brief 清理窗口缓存（保留扩展数据）
        @param browser_ids 窗口ID列表
        @return 清理结果
        """
        return self._request("/cache/clear/exceptExtensions", {"ids": browser_ids})
    
    def get_browser_ports(self) -> Dict:
        """
        @brief 获取所有已打开窗口的调试端口
        @return 端口字典 {browser_id: port}
        """
        return self._request("/browser/ports")
    
    def check_proxy(self,
                   host: str,
                   port: int,
                   proxy_type: str = "socks5",
                   proxy_username: str = "",
                   proxy_password: str = "",
                   ip_check_service: str = "ip123in",
                   check_exists: int = 0) -> Dict:
        """
        @brief 代理检测
        @param host 代理主机
        @param port 代理端口
        @param proxy_type 代理类型
        @param proxy_username 代理用户名
        @param proxy_password 代理密码
        @param ip_check_service IP检测渠道
        @param check_exists 检测IP是否已使用（1=检测，0=不检测）
        @return 代理信息
        """
        data = {
            "host": host,
            "port": port,
            "proxyType": proxy_type,
            "proxyUserName": proxy_username,
            "proxyPassword": proxy_password,
            "ipCheckService": ip_check_service,
            "checkExists": check_exists
        }
        return self._request("/checkagent", data)
    
    def random_browser_fingerprint(self, browser_id: str) -> Dict:
        """
        @brief 随机窗口指纹
        @param browser_id 窗口ID
        @return 指纹对象
        """
        return self._request("/browser/fingerprint/random", {"browserId": browser_id})
    
    def set_browser_cookies(self, browser_id: str, cookies: List[Dict]) -> Dict:
        """
        @brief 设置实时cookie
        @param browser_id 窗口ID
        @param cookies cookie列表
        @return 设置结果
        """
        data = {
            "browserId": browser_id,
            "cookies": cookies
        }
        return self._request("/browser/cookies/set", data)
    
    def clear_browser_cookies(self, browser_id: str, save_synced: bool = True) -> Dict:
        """
        @brief 清空cookie
        @param browser_id 窗口ID
        @param save_synced 是否保留已同步到服务端的cookie
        @return 清理结果
        """
        data = {
            "browserId": browser_id,
            "saveSynced": save_synced
        }
        return self._request("/browser/cookies/clear", data)
    
    def get_browser_cookies(self, browser_id: str) -> Dict:
        """
        @brief 获取实时cookie
        @param browser_id 窗口ID
        @return cookie列表
        """
        return self._request("/browser/cookies/get", {"browserId": browser_id})
    
    def format_cookies(self, cookie: Any, hostname: str = "") -> Dict:
        """
        @brief 格式化cookie
        @param cookie cookie数据（可能是数组、字符串等）
        @param hostname cookie的domain值
        @return 格式化后的cookie
        """
        data = {
            "cookie": cookie
        }
        if hostname:
            data["hostname"] = hostname
        return self._request("/browser/cookies/format", data)
    
    def get_all_displays(self) -> Dict:
        """
        @brief 获取所有显示器列表
        @return 显示器列表
        """
        return self._request("/alldisplays")
    
    def run_rpa_task(self, rpa_id: str) -> Dict:
        """
        @brief 执行RPA任务
        @param rpa_id RPA任务ID
        @return 执行结果
        """
        return self._request("/rpa/run", {"id": rpa_id})
    
    def stop_rpa_task(self, rpa_id: str) -> Dict:
        """
        @brief 停止RPA任务
        @param rpa_id RPA任务ID
        @return 停止结果
        """
        return self._request("/rpa/stop", {"id": rpa_id})
    
    def auto_paste(self, browser_id: str, url: str) -> Dict:
        """
        @brief 仿真输入（剪贴板内容）
        @param browser_id 窗口ID
        @param url 页面URL
        @return 输入结果
        """
        data = {
            "browserId": browser_id,
            "url": url
        }
        return self._request("/autopaste", data)
    
    def read_excel(self, filepath: str) -> Dict:
        """
        @brief 读取本地Excel文件
        @param filepath Excel文件绝对路径
        @return 文件内容
        """
        return self._request("/utils/readexcel", {"filepath": filepath})
    
    def read_file(self, filepath: str) -> Dict:
        """
        @brief 读取文本文件
        @param filepath 文件绝对路径
        @return 文件内容
        """
        return self._request("/utils/readfile", {"filepath": filepath})


# ==================== 兼容旧函数接口 ====================

# 全局API实例
_api_instance: Optional[BitBrowserAPI] = None

def get_bit_browser_port() -> int:
    """从数据库获取比特浏览器端口配置"""
    try:
        from core.database import DBManager
        port_str = DBManager.get_setting('bit_browser_port', '54345')
        return int(port_str) if port_str else 54345
    except:
        return 54345  # 默认端口

def get_api(force_new: bool = False) -> BitBrowserAPI:
    """
    获取全局API实例（单例模式）
    @param force_new 是否强制创建新实例（端口配置更改后需要）
    """
    global _api_instance
    if _api_instance is None or force_new:
        port = get_bit_browser_port()
        base_url = f"http://127.0.0.1:{port}"
        _api_instance = BitBrowserAPI(base_url=base_url)
    return _api_instance

def reset_api():
    """重置API实例（端口配置更改后调用）"""
    global _api_instance
    _api_instance = None


def openBrowser(browser_id: str, args: Optional[List[str]] = None, queue: bool = True) -> Dict:
    """
    @brief 打开浏览器窗口（兼容函数）
    @param browser_id 窗口ID
    @param args 启动参数
    @param queue 队列模式
    @return 打开结果
    """
    return get_api().open_browser(browser_id, args=args, queue=queue)


def closeBrowser(browser_id: str) -> Dict:
    """
    @brief 关闭浏览器窗口（兼容函数）
    @param browser_id 窗口ID
    @return 关闭结果
    """
    return get_api().close_browser(browser_id)


def createBrowser(name: str = "new browser", 
                 browser_fingerprint: Optional[Dict] = None,
                 **kwargs) -> str:
    """
    @brief 创建浏览器窗口（兼容函数）
    @param name 窗口名称
    @param browser_fingerprint 指纹对象
    @return 窗口ID
    """
    result = get_api().create_browser(name=name, browser_fingerprint=browser_fingerprint, **kwargs)
    if result.get('success'):
        return result.get('data', {}).get('id', '')
    return ''


def deleteBrowser(browser_id: str) -> Dict:
    """
    @brief 删除浏览器窗口（兼容函数）
    @param browser_id 窗口ID
    @return 删除结果
    """
    return get_api().delete_browser(browser_id)


# ==================== GUI便捷函数 ====================

def get_browser_list_simple(page: int = 0, page_size: int = 1000) -> List[Dict]:
    """
    @brief 获取浏览器列表（简化版）
    @param page 页码
    @param page_size 每页数量
    @return 浏览器列表
    """
    result = get_api().list_browsers(page=page, page_size=page_size)
    if result.get('success'):
        data = result.get('data', {})
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get('list', [])
    return []


def open_browsers_batch(browser_ids: List[str], callback=None) -> tuple:
    """
    @brief 批量打开浏览器
    @param browser_ids 窗口ID列表
    @param callback 回调函数 callback(browser_id, success, message)
    @return (success_count, total_count)
    """
    api = get_api()
    success_count = 0
    
    for browser_id in browser_ids:
        result = api.open_browser(browser_id, queue=True)
        success = result.get('success', False)
        message = result.get('msg', '') if not success else ''
        
        if success:
            success_count += 1
        
        if callback:
            callback(browser_id, success, message)
    
    return success_count, len(browser_ids)


def delete_browsers_batch(browser_ids: List[str], callback=None) -> tuple:
    """
    @brief 批量删除浏览器
    @param browser_ids 窗口ID列表
    @param callback 回调函数 callback(browser_id, success, message)
    @return (success_count, total_count)
    """
    api = get_api()
    success_count = 0
    
    for browser_id in browser_ids:
        result = api.delete_browser(browser_id)
        success = result.get('success', False)
        message = result.get('msg', '') if not success else ''
        
        if success:
            success_count += 1
        
        if callback:
            callback(browser_id, success, message)
    
    return success_count, len(browser_ids)


def get_browser_info(browser_id: str) -> Optional[Dict]:
    """
    @brief 获取浏览器详情（简化版）
    @param browser_id 窗口ID
    @return 浏览器信息，失败返回None
    """
    result = get_api().get_browser_detail(browser_id)
    if result.get('success'):
        return result.get('data', {})
    return None


def get_next_window_name(prefix: str) -> str:
    """
    @brief 根据前缀生成下一个窗口名称，格式：前缀_序号
    @param prefix 窗口名称前缀
    @return 下一个窗口名称
    """
    browsers = get_browser_list_simple(page=0, page_size=1000)
    
    max_num = 0
    for b in browsers:
        name = b.get('name', '')
        if name.startswith(f"{prefix}_"):
            try:
                num_part = name[len(prefix)+1:]
                num = int(num_part)
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    
    return f"{prefix}_{max_num + 1}"


# ==================== 默认模板配置 ====================
# 完整的浏览器创建模板，包含指纹、同步设置等

DEFAULT_BROWSER_TEMPLATE = {
    "browserFingerPrint": {
        "coreVersion": "140",
        "ostype": "PC",
        "os": "Win32",
        "architecture": "x86",
        "osVersion": "",
        "platformVersion": "10.0.0",
        "version": "",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.127 Safari/537.36",
        "isIpCreateTimeZone": True,
        "isIpCreatePosition": True,
        "isIpCreateDisplayLanguage": True,
        "isIpCreateLanguage": True,
        "webRTC": "3",
        "position": "1",
        "resolutionType": "0",
        "resolution": "1920 x 1080",
        "openWidth": 1280,
        "openHeight": 720,
        "fontType": "0",
        "canvas": "0",
        "webGL": "0",
        "webGLMeta": "0",
        "audioContext": "0",
        "mediaDevice": "1",
        "speechVoices": "0",
        "hardwareConcurrency": "6",
        "deviceMemory": "8",
        "deviceInfoEnabled": True,
        "clientRectNoiseEnabled": True,
        "doNotTrack": "0",
        "flash": "1",
        "portScanProtect": "0",
        "colorDepth": 24,
        "devicePixelRatio": 1,
        "enablePlugins": False,
        "windowSizeLimit": True,
        "coreProduct": "chrome",
        "navigatorVendor": "Google Inc.",
        "defaultAccuracy": 10
    },
    "proxyMethod": 2,
    "proxyType": "noproxy",
    "ipCheckService": "IP2Location",
    "syncTabs": False,           # 不保存标签页，下次打开时空白
    "syncCookies": True,         # 保存cookies，保持登录状态
    "syncIndexedDb": True,
    "syncLocalStorage": True,
    "syncBookmarks": False,      # 不保存书签
    "syncAuthorization": True,   # 保存授权信息
    "syncHistory": False,        # 不保存历史记录
    "syncGoogleAccount": False,  # 不同步 Google 账号
    "syncExtensions": False,     # 不同步扩展
    "syncUserExtensions": False,
    "syncSessions": False,
    "allowedSignin": False,
    "clearCacheFilesBeforeLaunch": False,
    "clearCookiesBeforeLaunch": False,
    "clearHistoriesBeforeLaunch": False,
    "randomFingerprint": False,
    "muteAudio": False,
    "disableGpu": False,
    "enableBackgroundMode": False,
    "credentialsEnableService": False,
    "disableTranslatePopup": False,
    "disableClipboard": False,
    "disableNotifications": False,
    "memorySaver": False,
    "abortImage": False,
    "abortMedia": False,
    "stopWhileNetError": False,
    "stopWhileCountryChange": False,
    "stopWhileIpChange": False,
    "isRandomFinger": True,
    "remarkType": 1,
    "duplicateCheck": 0,
    "workbench": "localserver"
}


def create_browser_from_account(
    account: Dict,
    name_prefix: str = "默认模板",
    template_config: Optional[Dict] = None,
    template_id: Optional[str] = None,
    proxy: Optional[Dict] = None,
    platform_url: str = "",
    extra_url: str = ""
) -> tuple:
    """
    @brief 根据账号创建浏览器窗口
    @param account 账号信息字典，需包含email, password, 可选backup_email, 2fa_secret
    @param name_prefix 窗口名称前缀
    @param template_config 模板配置（优先级高于template_id）
    @param template_id 模板窗口ID
    @param proxy 代理信息字典，需包含type, host, port, username, password
    @param platform_url 平台URL
    @param extra_url 额外URL
    @return (browser_id, error_message)
    """
    api = get_api()
    
    # 确定模板配置
    if template_config:
        base_config = template_config.copy()
    elif template_id:
        result = api.get_browser_detail(template_id)
        if result.get('success'):
            base_config = result.get('data', {})
        else:
            return None, f"找不到模板窗口: {template_id}"
    else:
        # 使用默认模板
        base_config = DEFAULT_BROWSER_TEMPLATE.copy()
    
    # 构建请求数据
    json_data = {}
    exclude_fields = {'id', 'name', 'remark', 'userName', 'password', 'faSecretKey', 
                      'createTime', 'updateTime', 'seq', 'groupId'}
    
    for key, value in base_config.items():
        if key not in exclude_fields:
            json_data[key] = value
    
    # 设置窗口名称
    json_data['name'] = get_next_window_name(name_prefix)
    
    # 设置备注（格式：email----password----backup_email----2fa_secret）
    email = account.get('email') or ''
    password = account.get('password') or ''
    backup_email = account.get('backup_email') or account.get('recovery_email') or ''
    secret = account.get('2fa_secret') or account.get('secret_key') or ''
    
    # 确保所有元素都是字符串，避免 None 导致 join 失败
    remark_parts = [str(email), str(password), str(backup_email), str(secret)]
    json_data['remark'] = '----'.join(remark_parts)
    
    # 设置账号信息
    if email:
        json_data['userName'] = email
    if password:
        json_data['password'] = password
    if secret and secret.strip():
        json_data['faSecretKey'] = secret.strip()
    
    # 设置平台和额外URL
    if platform_url:
        json_data['platform'] = platform_url
    if extra_url:
        json_data['url'] = extra_url
    
    # 确保有指纹配置
    if 'browserFingerPrint' not in json_data:
        json_data['browserFingerPrint'] = DEFAULT_BROWSER_TEMPLATE['browserFingerPrint'].copy()
    
    # 设置代理
    if proxy:
        json_data['proxyType'] = proxy.get('type', 'socks5')
        json_data['proxyMethod'] = 2
        json_data['host'] = proxy.get('host', '')
        json_data['port'] = str(proxy.get('port', ''))
        json_data['proxyUserName'] = proxy.get('username', '')
        json_data['proxyPassword'] = proxy.get('password', '')
    else:
        json_data['proxyType'] = 'noproxy'
        json_data['proxyMethod'] = 2
    
    # 检查是否已存在该账号的窗口
    browsers = get_browser_list_simple(page=0, page_size=1000)
    for b in browsers:
        if b.get('userName') == email and email:
            return None, f"该账号已有对应窗口: {b.get('name')} (ID: {b.get('id')})"
    
    # 创建窗口
    try:
        result = api._request('/browser/update', json_data, timeout=30)
        
        if result.get('success'):
            browser_id = result.get('data', {}).get('id')
            if not browser_id:
                return None, "API返回成功但未获取到ID"
            return browser_id, None
        else:
            return None, result.get('msg', '创建失败')
    except Exception as e:
        return None, f"请求异常: {str(e)}"


def create_browsers_batch(
    accounts: List[Dict],
    name_prefix: str = "默认模板",
    template_config: Optional[Dict] = None,
    template_id: Optional[str] = None,
    proxies: Optional[List[Dict]] = None,
    platform_url: str = "",
    extra_url: str = "",
    callback=None,
    stop_check=None
) -> tuple:
    """
    @brief 批量创建浏览器窗口
    @param accounts 账号列表
    @param name_prefix 窗口名称前缀
    @param template_config 模板配置
    @param template_id 模板窗口ID
    @param proxies 代理列表
    @param platform_url 平台URL
    @param extra_url 额外URL
    @param callback 回调函数 callback(index, account, browser_id, error)
    @param stop_check 停止检查函数 stop_check() -> bool
    @return (success_count, total_count)
    """
    success_count = 0
    proxy_index = 0
    
    for i, account in enumerate(accounts):
        # 检查停止标志
        if stop_check and stop_check():
            break
        
        # 分配代理
        proxy = None
        if proxies and proxy_index < len(proxies):
            proxy = proxies[proxy_index]
            proxy_index += 1
        
        # 创建窗口
        browser_id, error = create_browser_from_account(
            account=account,
            name_prefix=name_prefix,
            template_config=template_config,
            template_id=template_id,
            proxy=proxy,
            platform_url=platform_url,
            extra_url=extra_url
        )
        
        if browser_id:
            success_count += 1
        
        # 回调
        if callback:
            callback(i, account, browser_id, error)
    
    return success_count, len(accounts)


if __name__ == "__main__":
    # 测试代码
    api = BitBrowserAPI()
    
    # 健康检查
    print("健康检查:", api.health_check())
    
    # 获取窗口列表
    result = api.list_browsers(page=0, page_size=5)
    if result.get('success'):
        browsers = result.get('data', {}).get('list', [])
        print(f"窗口数量: {len(browsers)}")
        for browser in browsers[:3]:
            print(f"  - {browser.get('name')} (ID: {browser.get('id')})")


# ==================== 便捷函数（使用动态端口） ====================

def open_browser(browser_id: str, **kwargs) -> dict:
    """
    @brief 打开浏览器窗口
    @param browser_id 窗口ID
    @return API响应
    """
    return get_api().open_browser(browser_id, **kwargs)


def close_browser(browser_id: str) -> dict:
    """
    @brief 关闭浏览器窗口
    @param browser_id 窗口ID
    @return API响应
    """
    return get_api().close_browser(browser_id)


def get_browser_info(browser_id: str) -> dict:
    """
    @brief 获取浏览器详情
    @param browser_id 窗口ID
    @return 浏览器信息
    """
    result = get_api().get_browser_detail(browser_id)
    if result.get('success'):
        return result.get('data', {})
    return {}


def delete_browser(browser_id: str) -> dict:
    """
    @brief 删除浏览器窗口
    @param browser_id 窗口ID
    @return API响应
    """
    return get_api().delete_browser(browser_id)


