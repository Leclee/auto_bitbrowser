"""
@file sheerid_verifier.py
@brief SheerID学生验证器模块 (V2 - 基于 batch.1key.me API)
@details 通过 batch.1key.me API 进行 Google 学生资格验证
@api_doc https://batch.1key.me/api/docs
"""
import requests
import re
import json
import time
import logging
from typing import List, Dict, Optional, Callable

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API 配置
BASE_URL = "https://neigui.1key.me"
DEFAULT_API_KEY = ""  # 在 GUI 中输入 API Key (hCaptchaToken)


class SheerIDVerifier:
    """
    @class SheerIDVerifier
    @brief SheerID 批量验证器
    @details 封装 neigui.1key.me 批量验证 API
    
    API 端点:
    - POST /api/batch      : 批量验证 (SSE 流)
    - POST /api/cancel     : 取消验证
    - POST /api/check-status : 检查状态 (无需 CSRF)
    - GET  /api/status     : 系统状态
    """
    
    def __init__(self, api_key: str = DEFAULT_API_KEY):
        """
        @brief 初始化验证器
        @param api_key API 密钥 (用作 hCaptchaToken)
        """
        self.session = requests.Session()
        self.api_key = api_key
        self.csrf_token = None
        self.quota_info = {}  # 存储配额信息
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/"
        }

    def _get_csrf_token(self) -> bool:
        """
        @brief 获取CSRF令牌
        @return 是否成功获取令牌
        """
        try:
            logger.info("Fetching CSRF token...")
            resp = self.session.get(BASE_URL, headers=self.headers, timeout=10)
            resp.raise_for_status()
            
            logger.debug(f"Response status: {resp.status_code}")
            logger.debug(f"Response length: {len(resp.text)} chars")
            
            # 尝试多种 CSRF token 模式
            patterns = [
                r'window\.CSRF_TOKEN\s*=\s*["\']([^"\']+)["\']',
                r'csrfToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'_csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            ]
            
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, resp.text, re.IGNORECASE)
                if match:
                    self.csrf_token = match.group(1)
                    self.headers["X-CSRF-Token"] = self.csrf_token
                    logger.info(f"✅ CSRF Token obtained (pattern {i+1}): {self.csrf_token[:10]}...")
                    return True
            
            # 如果都没匹配到，输出更详细的调试信息
            logger.error("❌ CSRF Token pattern not found in page.")
            logger.error(f"Page content preview (first 1000 chars):\n{resp.text[:1000]}")
            
            # 查找所有可能的 token 相关字符串
            token_hints = re.findall(r'(csrf|token|_token)[^"\']*["\']([^"\']{20,})["\']', resp.text, re.IGNORECASE)
            if token_hints:
                logger.info(f"Found potential token patterns: {token_hints[:3]}")
            
            # 尝试不使用 CSRF token 继续
            logger.warning("Attempting to proceed without CSRF token...")
            return False
            
        except Exception as e:
            logger.error(f"Failed to get CSRF token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_system_status(self) -> Dict:
        """
        @brief 获取系统状态
        @return 系统状态信息
        """
        try:
            resp = self.session.get(f"{BASE_URL}/api/status", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {"status": "ok", "raw": resp.text}
            return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def verify_batch(self, verification_ids: List[str], callback: Callable = None) -> Dict:
        """
        @brief 批量验证
        @param verification_ids 验证ID列表
        @param callback 状态回调函数 callback(vid, message)
        @return 验证结果字典 {verification_id: result}
        
        API 响应格式 (SSE):
        - event: start -> {"total":N, "current_quota":M, "cost":C}
        - data: {"verificationId":"...", "currentStep":"success/error/pending", "message":"..."}
        - event: end -> {"completed":N, "total":N}
        """
        # 每次批次验证前刷新 CSRF token
        logger.info("Refreshing CSRF token before batch...")
        if not self._get_csrf_token():
            logger.warning("CSRF token refresh failed, attempting with old/no token")

        results = {}
        
        # 构建请求体 (注意: useLucky 和 programId 已废弃，但保留以兼容)
        payload = {
            "verificationIds": verification_ids,
            "hCaptchaToken": self.api_key,  # API Key 作为 hCaptchaToken
        }
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"

        try:
            logger.info(f"📤 提交批量验证: {len(verification_ids)} 个 ID")
            logger.info(f"🔑 API Key: {self.api_key[:15] if self.api_key else '❌ 未设置'}...")
            
            resp = self.session.post(
                f"{BASE_URL}/api/batch", 
                headers=headers, 
                json=payload,
                stream=True,
                timeout=60
            )
            
            # 如果返回 403/401，说明 token 过期，再试一次
            if resp.status_code in [403, 401]:
                logger.warning(f"Token 过期 (status {resp.status_code}), 重新获取...")
                if self._get_csrf_token():
                    headers["X-CSRF-Token"] = self.csrf_token
                    resp = self.session.post(
                        f"{BASE_URL}/api/batch", 
                        headers=headers, 
                        json=payload,
                        stream=True,
                        timeout=60
                    )
                else:
                    return {vid: {"currentStep": "error", "message": "Token 过期且刷新失败"} for vid in verification_ids}

            # 检查响应状态
            if resp.status_code != 200:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error(f"批量请求失败: {error_msg}")
                return {vid: {"currentStep": "error", "message": error_msg} for vid in verification_ids}

            # 解析 SSE 流
            current_event = None
            for line in resp.iter_lines():
                if not line: 
                    continue
                decoded_line = line.decode('utf-8')
                
                # 处理 event 行
                if decoded_line.startswith("event:"):
                    current_event = decoded_line[6:].strip()
                    continue
                
                # 处理 data 行
                if decoded_line.startswith("data:"):
                    json_str = decoded_line[5:].strip()
                    try:
                        data = json.loads(json_str)
                        
                        # 处理 start 事件 (配额信息)
                        if current_event == "start":
                            self.quota_info = {
                                "total": data.get("total"),
                                "current_quota": data.get("current_quota"),
                                "cost": data.get("cost")
                            }
                            logger.info(f"📊 配额信息: 剩余={data.get('current_quota')}, 本次消耗={data.get('cost')}")
                            
                            # 保存配额信息到数据库
                            try:
                                from core.database import DBManager
                                import json as json_module
                                DBManager.set_setting('sheerid_quota', json_module.dumps(self.quota_info))
                                DBManager.set_setting('sheerid_quota_time', str(int(time.time())))
                            except Exception as e:
                                logger.warning(f"保存配额信息失败: {e}")
                            
                            if callback:
                                callback(None, f"配额: {data.get('current_quota')}, 消耗: {data.get('cost')}")
                        
                        # 处理 end 事件
                        elif current_event == "end":
                            logger.info(f"✅ 批量验证完成: {data.get('completed')}/{data.get('total')}")
                        
                        # 处理验证结果数据
                        else:
                            self._handle_api_response(data, results, callback)
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 解析失败: {json_str[:50]}... | {e}")
                        
                current_event = None  # 重置事件类型
                        
        except requests.exceptions.Timeout:
            logger.error("批量验证请求超时")
            for vid in verification_ids:
                if vid not in results:
                    results[vid] = {"currentStep": "error", "message": "请求超时"}
                    
        except Exception as e:
            logger.error(f"批量验证失败: {e}")
            import traceback
            traceback.print_exc()
            for vid in verification_ids:
                if vid not in results:
                    results[vid] = {"currentStep": "error", "message": str(e)}

        return results


    def _handle_api_response(self, data: dict, results: dict, callback: Callable = None):
        """
        @brief 处理API响应
        @param data 响应数据
        @param results 结果字典
        @param callback 状态回调
        """
        vid = data.get("verificationId")
        if not vid: return

        status = data.get("currentStep")
        message = data.get("message", "")
        
        if callback:
            callback(vid, f"Step: {status} | Msg: {message}")

        if status == "pending" and "checkToken" in data:
            # Need to poll
            check_token = data["checkToken"]
            final_res = self._poll_status(check_token, vid, callback)
            results[vid] = final_res
        elif status == "success" or status == "error":
            # Done
            results[vid] = data

    def _poll_status(self, check_token: str, vid: str, callback: Callable = None) -> dict:
        """
        @brief 轮询验证状态
        @param check_token 检查令牌
        @param vid 验证ID
        @param callback 状态回调
        @return 最终状态
        
        @note /api/check-status 不需要 CSRF Token
        """
        url = f"{BASE_URL}/api/check-status"
        
        # 注意: check-status 端点不需要 CSRF Token
        headers = {
            "User-Agent": self.headers.get("User-Agent"),
            "Content-Type": "application/json"
        }
        
        # 最多轮询 60 次 (每次间隔 2 秒，约 120 秒)
        for i in range(60):
            try:
                time.sleep(2)
                payload = {"checkToken": check_token}
                
                resp = self.session.post(url, headers=headers, json=payload, timeout=30)
                json_data = resp.json()
                
                status = json_data.get("currentStep")
                message = json_data.get("message", "")
                
                if callback:
                    callback(vid, f"轮询中: {status} ({i+1}/60) | {message}")

                if status in ["success", "error"]:
                    return json_data
                
                # 如果是 pending，更新 checkToken (如果有新的)
                if "checkToken" in json_data:
                    check_token = json_data["checkToken"]
                    
            except requests.exceptions.Timeout:
                logger.warning(f"轮询超时 (第 {i+1}/60 次), 重试中...")
                if callback:
                    callback(vid, f"轮询超时 (重试 {i+1}/60)")
                continue
                
            except Exception as e:
                logger.error(f"轮询失败: {e}")
                if callback:
                    callback(vid, f"轮询错误: {str(e)[:50]} (重试 {i+1}/60)")
                continue
        
        return {"currentStep": "error", "message": "轮询超时 (120秒)"}

    def cancel_verification(self, verification_id: str) -> dict:
        """
        @brief 取消验证
        @param verification_id 验证ID
        @return 取消结果
        """
        if not self.csrf_token:
            if not self._get_csrf_token():
                return {"status": "error", "message": "No CSRF Token"}
        
        url = f"{BASE_URL}/api/cancel"
        headers = self.headers.copy()
        headers["X-CSRF-Token"] = self.csrf_token
        headers["Content-Type"] = "application/json"
        
        try:
            resp = self.session.post(url, headers=headers, json={"verificationId": verification_id}, timeout=10)
            try:
                return resp.json()
            except:
                return {"status": "error", "message": f"Invalid JSON: {resp.text}"}
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    pass
