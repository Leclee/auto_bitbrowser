"""
@file bind_card_service.py
@brief 绑卡订阅服务模块 (V2 - 智能等待版)
@details 自动绑定测试卡并完成Google One订阅，使用 Playwright .or() 智能等待
"""
import asyncio
import re
from typing import Tuple, Optional, Callable, List, Dict
from playwright.async_api import async_playwright, Page, expect


# ==================== 超时配置 ====================
DEFAULT_TIMEOUT = 15000  # 默认15秒超时


def get_card_from_db() -> dict:
    """
    @brief 从数据库获取可用的卡片信息
    @return 卡信息字典，若无可用卡则返回None
    """
    try:
        from core.database import DBManager
        cards = DBManager.get_available_cards()
        if cards:
            card = cards[0]
            return {
                'id': card.get('id'),
                'number': card.get('card_number', ''),
                'exp_month': card.get('exp_month', ''),
                'exp_year': card.get('exp_year', ''),
                'cvv': card.get('cvv', ''),
                'zip_code': card.get('zip_code', ''),
            }
    except Exception as e:
        print(f"[BindCard] 获取卡片失败: {e}")
    return None


def update_card_usage(card_id: int) -> tuple:
    """
    @brief 更新卡片使用次数
    @param card_id 卡片ID
    @return (usage_count, max_usage) 使用次数和最大次数
    """
    try:
        from core.database import DBManager
        return DBManager.increment_card_usage(card_id)
    except Exception as e:
        print(f"[BindCard] 更新卡片使用次数失败: {e}")
        return None, None


async def auto_bind_card(page: Page, card_info: dict = None, account_info: dict = None, log_callback=None) -> Tuple[bool, str]:
    """
    @brief 自动绑卡订阅 (V3 - 智能等待版)
    @param page Playwright页面对象
    @param card_info 卡信息字典 {'number', 'exp_month', 'exp_year', 'cvv'}
    @param account_info 账号信息(用于登录)
    @param log_callback 日志回调函数
    @return (success, message)
    @details 使用智能等待替代固定时间等待
    """
    def log(msg: str):
        """统一日志输出"""
        if log_callback:
            log_callback(msg)
        else:
            print(msg)  # 只有没有 callback 时才打印
    
    # 优先从数据库获取卡片
    if card_info is None:
        card_info = get_card_from_db()
        if card_info is None:
            return False, "数据库中无可用卡片，请先在Web管理界面导入卡片"
    
    # 验证卡片信息完整性
    required_fields = ['number', 'exp_month', 'exp_year', 'cvv']
    for field in required_fields:
        if not card_info.get(field):
            return False, f"卡片信息不完整，缺少: {field}"
    
    try:
        log("[BindCard] 开始自动绑卡流程...")
        log(f"[BindCard] 当前页面: {page.url[:60]}...")
        
        # ==================== Step 1: 点击 "Get student offer" 按钮 ====================
        log("[BindCard] Step 1: 查找 Get student offer 按钮...")
        
        # 更精确的定位器：使用 jsname 属性（Google 按钮常用）
        get_offer_btn = page.locator('[jsname="V67aGc"]:has-text("Get student offer"), [jsname="V67aGc"]:has-text("Get offer")')
        get_offer_btn_fallback = page.get_by_role("button", name=re.compile(r"Get.*offer", re.IGNORECASE))
        
        # 先检查付款 iframe 是否已存在（可能之前已点击过）
        iframe_already_exists = False
        try:
            iframe_count = await page.locator('iframe[src*="tokenized.play.google.com"]').count()
            if iframe_count > 0:
                existing_iframe = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
                existing_btn = existing_iframe.get_by_role("button", name=re.compile(r"Subscribe|Add.*card", re.IGNORECASE))
                if await existing_btn.count() > 0:
                    iframe_already_exists = True
                    log("[BindCard] ✅ 付款 iframe 已存在，跳过点击按钮")
        except Exception as e:
            log(f"[BindCard] iframe 检查异常: {e}")
        
        # 如果 iframe 不存在，点击 Get student offer 按钮
        if not iframe_already_exists:
            try:
                combined_offer = get_offer_btn.or_(get_offer_btn_fallback)
                await expect(combined_offer.first).to_be_visible(timeout=8000)
                await combined_offer.first.click()
                log("[BindCard] ✅ 已点击 'Get student offer'")
            except Exception as e:
                # 检查是否在正确的页面
                if 'one.google.com' not in page.url:
                    return False, f"页面状态异常，不在 Google One 页面: {page.url[:50]}"
                log(f"[BindCard] ⚠️ 未找到 Get student offer 按钮: {e}，尝试继续...")
        
        # ==================== Step 2: 智能等待付款 iframe 加载 ====================
        log("[BindCard] Step 2: 智能等待付款页面 iframe...")
        
        iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
        
        # 等待 iframe 内任意关键元素出现（支持中英文）
        subscribe_btn_en = iframe_locator.get_by_role("button", name="Subscribe", exact=True)
        subscribe_btn_cn = iframe_locator.get_by_role("button", name="订阅", exact=True)
        subscribe_btn = subscribe_btn_en.or_(subscribe_btn_cn).or_(iframe_locator.locator('button:has-text("Subscribe"), button:has-text("订阅")'))
        
        add_card_btn = iframe_locator.locator('span.PjwE0:has-text("Add card"), button:has-text("Add card"), span:has-text("添加卡片"), button:has-text("添加卡片"), span:has-text("添加"), button:has-text("添加")')
        change_payment_btn = iframe_locator.locator('[aria-label="Change payment method"], [aria-label="更改付款方式"], button.Rkjmoc')
        
        # 使用 .or() 并行等待
        combined_payment = subscribe_btn.or_(add_card_btn).or_(change_payment_btn)
        
        try:
            await expect(combined_payment.first).to_be_visible(timeout=30000)
            log("[BindCard] ✅ 付款页面已加载")
        except Exception as e:
            return False, f"付款页面加载超时: {e}"
        
        # ==================== Step 2.5: 检测当前状态 ====================
        has_subscribe = await subscribe_btn.count() > 0
        has_change_payment = await change_payment_btn.count() > 0
        has_add_card = await add_card_btn.count() > 0
        
        log(f"[BindCard] 状态检测: 订阅按钮={has_subscribe}, 换绑按钮={has_change_payment}, Add card={has_add_card}")
        
        # ==================== Step 2.6: 如果已绑卡且有订阅按钮，先尝试直接订阅 ====================
        if has_subscribe and (has_change_payment or not has_add_card):
            log("[BindCard] 📋 检测到已绑卡，先尝试直接订阅...")
            try:
                # 定位订阅按钮 - 使用精确选择器
                # Google 按钮结构: <button><span jsname="V67aGc">Subscribe</span></button>
                sub_btn_precise = iframe_locator.locator('button:has(span[jsname="V67aGc"]:text-is("Subscribe"))')
                sub_btn_precise_cn = iframe_locator.locator('button:has(span[jsname="V67aGc"]:text-is("订阅"))')
                combined_sub = sub_btn_precise.or_(sub_btn_precise_cn)
                
                # 调试：打印匹配数量
                sub_count = await combined_sub.count()
                log(f"[BindCard] 🔍 找到 {sub_count} 个订阅按钮 (精确)")
                
                if sub_count == 0:
                    # 备选方案
                    combined_sub = iframe_locator.locator('button:has-text("Subscribe"), button:has-text("订阅")')
                    sub_count = await combined_sub.count()
                    log(f"[BindCard] 🔍 备选方案找到 {sub_count} 个订阅按钮")
                
                if sub_count == 0:
                    log("[BindCard] ⚠️ 未找到订阅按钮，跳过直接订阅")
                    raise Exception("未找到订阅按钮")
                
                # 确保按钮可见
                await expect(combined_sub.first).to_be_visible(timeout=5000)
                await combined_sub.first.click(force=True)
                log("[BindCard] ✅ 已点击订阅按钮，智能等待结果...")
                
                # 智能轮询检测订阅结果（最多等待15秒，每500ms检测一次）
                success_locator = (
                    iframe_locator.locator('text=/Subscribed/i')
                    .or_(iframe_locator.locator('text=/订阅成功/i'))
                    .or_(iframe_locator.locator('text=/Thank you/i'))
                    .or_(page.locator('text=/You.*subscribed/i'))
                )
                error_locator = iframe_locator.locator('text=/declined/i, text=/expired/i, text=/failed/i, text=/error/i, text=/拒绝/i, text=/过期/i, text=/失败/i')
                
                subscribe_result = None  # 'success', 'error', 'button_gone', None
                for poll_i in range(30):  # 30 * 0.5s = 15秒
                    await asyncio.sleep(0.5)
                    
                    # 检查是否订阅成功
                    try:
                        if await success_locator.count() > 0:
                            log("[BindCard] ✅ 直接订阅成功！")
                            _update_success_status(account_info, card_info, log_func=log)
                            return True, "绑卡订阅成功 (已绑卡直接订阅)"
                    except:
                        pass
                    
                    # 检查是否有错误提示（卡过期等）
                    try:
                        if await error_locator.count() > 0:
                            log("[BindCard] ⚠️ 检测到错误提示（可能卡过期），将重新绑卡...")
                            subscribe_result = 'error'
                            break
                    except:
                        pass
                    
                    # 检查订阅按钮是否已消失（可能成功了）
                    try:
                        if await combined_sub.count() == 0 or not await combined_sub.first.is_visible():
                            log("[BindCard] ℹ️ 订阅按钮已消失，检查最终状态...")
                            subscribe_result = 'button_gone'
                            break
                    except:
                        pass
                
                # 根据检测结果处理
                if subscribe_result == 'button_gone':
                    # 直接订阅后检查状态，传入 is_direct_subscribe=True 表示用的是旧卡
                    check_success, check_msg = await _check_subscription_status(page, account_info, card_info, log_func=log, is_direct_subscribe=True)
                    if check_success:
                        return True, check_msg
                    # 如果检测到失败（旧卡被拒绝），继续走换绑流程，不返回错误
                    log("[BindCard] ⚠️ 旧卡订阅失败，继续换绑新卡流程...")
                    subscribe_result = 'error'  # 转换为 error 状态，继续处理
                
                # ===== 检测到 Error（旧卡被拒绝）→ 刷新页面 → 重新点击 Get student offer → 点击持卡人行 → Add card =====
                if subscribe_result == 'error':
                    log("[BindCard] ⚠️ 旧卡订阅失败，刷新页面准备换绑新卡...")
                    
                    # Step A: 刷新页面（不点击 Got it，直接刷新更可靠）
                    try:
                        await page.reload(wait_until='domcontentloaded')
                        log("[BindCard] ✅ 页面已刷新")
                        await asyncio.sleep(1)
                    except Exception as e:
                        log(f"[BindCard] ⚠️ 刷新页面失败: {e}")
                        return False, "REBIND_NEEDED:刷新页面失败"
                    
                    # Step B: 重新点击 "Get student offer"
                    try:
                        get_offer_btn = page.locator('button:has-text("Get student offer")')
                        get_offer_btn_fallback = page.locator('button:has-text("获取学生优惠")')
                        combined_offer = get_offer_btn.or_(get_offer_btn_fallback)
                        await expect(combined_offer.first).to_be_visible(timeout=10000)
                        await combined_offer.first.click()
                        log("[BindCard] ✅ 重新点击 'Get student offer'")
                        await asyncio.sleep(1)
                    except Exception as e:
                        log(f"[BindCard] ⚠️ 重新点击 Get student offer 失败: {e}")
                        return False, "REBIND_NEEDED:重新点击按钮失败"
                    
                    # Step C: 等待付款 iframe 加载
                    log("[BindCard] Step C: 等待付款 iframe 加载...")
                    await asyncio.sleep(2)  # 等待 iframe 完全渲染
                    
                    # 重新获取 iframe（使用 .first 确保第一层）
                    iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]').first
                    
                    try:
                        # 等待 iframe 内的 button.Rkjmoc（持卡人行）出现
                        change_payment_btn = iframe_locator.locator('button.Rkjmoc')
                        await expect(change_payment_btn.first).to_be_visible(timeout=15000)
                        log("[BindCard] ✅ 付款页面已重新加载，检测到持卡人行")
                    except Exception as e:
                        log(f"[BindCard] ⚠️ 付款页面加载失败: {e}")
                        return False, "REBIND_NEEDED:付款页面加载失败"
                    
                    # Step D: 点击持卡人名字那一行
                    # HTML: <button class="Rkjmoc" aria-label="Change payment method">...</button>
                    log("[BindCard] Step D: 点击持卡人行 (button.Rkjmoc)...")
                    try:
                        payment_btn = iframe_locator.locator('button.Rkjmoc')
                        btn_count = await payment_btn.count()
                        log(f"[BindCard] 🔍 在 iframe 内找到 {btn_count} 个 button.Rkjmoc")
                        
                        if btn_count > 0:
                            await expect(payment_btn.first).to_be_enabled(timeout=5000)
                            await payment_btn.first.click()
                            log("[BindCard] ✅ 已点击持卡人行")
                            await asyncio.sleep(1.5)  # 等待下拉展开
                        else:
                            log("[BindCard] ⚠️ 未找到 button.Rkjmoc，尝试 aria-label...")
                            aria_btn = iframe_locator.locator('[aria-label="Change payment method"]')
                            aria_count = await aria_btn.count()
                            log(f"[BindCard] 🔍 aria-label 找到 {aria_count} 个")
                            
                            if aria_count > 0:
                                await aria_btn.first.click()
                                log("[BindCard] ✅ 已点击持卡人行 (via aria-label)")
                                await asyncio.sleep(1.5)
                            else:
                                log("[BindCard] ❌ 无法找到持卡人行按钮")
                                return False, "REBIND_NEEDED:无法找到持卡人行"
                    except Exception as e:
                        log(f"[BindCard] ⚠️ 点击持卡人行失败: {e}")
                        return False, f"REBIND_NEEDED:点击持卡人行失败 - {str(e)[:50]}"
                    
                    # Step E: 等待 Add card 按钮出现
                    log("[BindCard] Step E: 等待 Add card 按钮...")
                    add_card_btn = iframe_locator.locator('span.PjwE0:has-text("Add card"), button:has-text("Add card"), span:has-text("添加卡片"), button:has-text("添加")')
                    add_count = await add_card_btn.count()
                    log(f"[BindCard] 🔍 找到 {add_count} 个 Add card 按钮")
                    
                    try:
                        await expect(add_card_btn.first).to_be_visible(timeout=5000)
                        log("[BindCard] ✅ Add card 按钮已出现，继续换绑新卡流程...")
                        has_add_card = True
                        has_change_payment = False  # 不再需要点击 Change payment
                    except:
                        log("[BindCard] ⚠️ Add card 按钮未出现，将返回重试...")
                        return False, "REBIND_NEEDED:Add card 按钮未出现"
                else:
                    # 超时情况，也是旧卡的问题，同样刷新页面处理
                    log("[BindCard] ⚠️ 旧卡订阅超时，需要换绑新卡...")
                    return False, "REBIND_NEEDED:旧卡订阅超时"
                    
            except Exception as e:
                log(f"[BindCard] ⚠️ 直接订阅异常: {e}，继续换绑卡流程...")
        
        # ==================== Step 2.7: 处理换绑卡 ====================
        # 如果有 "Change payment method" 按钮，说明已绑卡，需要换绑新卡
        if has_change_payment:
            log("[BindCard] 📋 检测到已绑卡，点击换绑支付方式...")
            try:
                await change_payment_btn.first.click()
                log("[BindCard] ✅ 已点击 'Change payment method'")
                
                # 等待 Add card 按钮出现
                add_card_btn = iframe_locator.locator('span.PjwE0:has-text("Add card"), button:has-text("Add card"), span:has-text("添加卡片"), button:has-text("添加")')
                await expect(add_card_btn.first).to_be_visible(timeout=10000)
                log("[BindCard] ✅ Add card 按钮已出现")
            except Exception as e:
                log(f"[BindCard] ⚠️ 换绑流程异常: {e}")
        
        # ==================== Step 3: 点击 Add card / 添加卡片 ====================
        log("[BindCard] Step 3: 点击 Add card / 添加卡片...")
        
        # 重新获取 Add card 按钮（可能在换绑后才出现，支持中英文）
        add_card_btn = iframe_locator.locator('span.PjwE0:has-text("Add card"), button:has-text("Add card"), span:has-text("添加卡片"), button:has-text("添加卡片"), span:has-text("添加"), button:has-text("添加")')
        
        try:
            await expect(add_card_btn.first).to_be_visible(timeout=10000)
            await add_card_btn.first.click()
            log("[BindCard] ✅ 已点击 'Add card'")
        except Exception as e:
            # 如果没有 Add card 按钮，可能直接有输入框
            log(f"[BindCard] ⚠️ 未找到 Add card 按钮: {e}，检查是否已有输入框...")
        
        # ==================== Step 4: 智能等待卡号输入框 ====================
        log("[BindCard] Step 4: 智能等待卡号输入框...")
        
        # 检查是否有二层 iframe (Google 支付表单)
        # 关键：使用 data-widget="current" 精确匹配当前活动的 iframe
        active_iframe = iframe_locator  # 默认一层
        
        try:
            # 尝试检测二层 iframe - 使用更精确的选择器
            # 优先匹配 data-widget="current" (当前活动的iframe)
            # 或者 src 包含 instrumentmanager (卡片管理页面)
            inner_iframe_selector = (
                'iframe[data-widget="current"], '
                'iframe[name="hnyNZeIframe"][src*="instrumentmanager"], '
                'iframe[src*="instrumentmanager"]'
            )
            inner_iframe = iframe_locator.frame_locator(inner_iframe_selector)
            
            # 等待二层 iframe 中的输入框出现
            # 使用 jsname="YPqjbf" 精确定位 Google 的输入框
            inner_input = inner_iframe.locator('input[jsname="YPqjbf"], input[inputmode="numeric"]').first
            
            await expect(inner_input).to_be_visible(timeout=20000)
            log("[BindCard] ✅ 检测到二层 iframe 中的输入框")
            active_iframe = inner_iframe
                
        except Exception as e:
            log(f"[BindCard] ⚠️ 二层 iframe 检测失败: {str(e)[:80]}，尝试一层 iframe...")
            # 回退到一层 iframe
            try:
                outer_input = iframe_locator.locator('input[jsname="YPqjbf"], input[type="tel"], input[inputmode="numeric"]').first
                await expect(outer_input).to_be_visible(timeout=10000)
                log("[BindCard] ✅ 使用一层 iframe")
            except Exception as e2:
                log(f"[BindCard] ⚠️ 一层 iframe 也未找到输入框: {e2}")
        
        # ==================== Step 5: 填写卡信息 ====================
        log(f"[BindCard] Step 5: 填写卡号 {card_info['number'][:4]}****...")
        
        try:
            # 等待输入框可用
            await expect(active_iframe.locator('input[jsname="YPqjbf"], input[inputmode="numeric"]').first).to_be_visible(timeout=DEFAULT_TIMEOUT)
            
            # Google 支付表单的输入框都有 jsname="YPqjbf"，按顺序是：卡号、过期日期、CVV、(可选)邮编
            all_inputs = active_iframe.locator('input[jsname="YPqjbf"]')
            input_count = await all_inputs.count()
            log(f"[BindCard] 找到 {input_count} 个输入框 (jsname='YPqjbf')")
            
            if input_count < 3:
                # 回退：尝试获取所有可见输入框
                all_inputs = active_iframe.locator('input:visible')
                input_count = await all_inputs.count()
                log(f"[BindCard] 回退：找到 {input_count} 个可见输入框")
                
                if input_count < 3:
                    return False, f"输入框数量不足: {input_count}"
            
            # 填写卡号 (第1个输入框)
            await all_inputs.nth(0).click()
            await all_inputs.nth(0).fill(card_info['number'])
            log("[BindCard] ✅ 卡号已填写")
            
            # 填写过期日期 (第2个输入框) - 格式 MMYY
            exp_date = f"{card_info['exp_month']}{card_info['exp_year']}"
            await all_inputs.nth(1).click()
            await all_inputs.nth(1).fill(exp_date)
            log("[BindCard] ✅ 过期日期已填写")
            
            # 填写 CVV (第3个输入框)
            await all_inputs.nth(2).click()
            await all_inputs.nth(2).fill(card_info['cvv'])
            log("[BindCard] ✅ CVV已填写")
            
            # ===== Step 5.5: 检测并填写邮编 (可选) =====
            # 方法1: 通过 autocomplete="postal-code" 属性查找邮编输入框
            # 方法2: 如果有第4个输入框，尝试填写
            try:
                zip_filled = False
                zip_code = card_info.get('zip_code') or '14543'
                
                # 方法1: 通过 autocomplete 属性精确查找
                zip_input_by_autocomplete = active_iframe.locator('input[autocomplete="postal-code"]')
                if await zip_input_by_autocomplete.count() > 0:
                    zip_input = zip_input_by_autocomplete.first
                    if await zip_input.is_visible():
                        current_value = await zip_input.input_value()
                        if not current_value or current_value.strip() == '':
                            await zip_input.click()
                            await zip_input.fill(zip_code)
                            log(f"[BindCard] ✅ 邮编已填写 (autocomplete): {zip_code}")
                            zip_filled = True
                        else:
                            log(f"[BindCard] ℹ️ 邮编已存在: {current_value}")
                            zip_filled = True
                
                # 方法2: 如果方法1未填写，尝试第4个输入框
                if not zip_filled and input_count >= 4:
                    zip_input = all_inputs.nth(3)
                    if await zip_input.is_visible():
                        current_value = await zip_input.input_value()
                        if not current_value or current_value.strip() == '':
                            await zip_input.click()
                            await zip_input.fill(zip_code)
                            log(f"[BindCard] ✅ 邮编已填写 (第4个输入框): {zip_code}")
                        else:
                            log(f"[BindCard] ℹ️ 邮编已存在: {current_value}")
                elif not zip_filled:
                    log("[BindCard] ℹ️ 无邮编输入框")
            except Exception as zip_err:
                log(f"[BindCard] ℹ️ 邮编输入异常: {zip_err}")
            
        except Exception as e:
            return False, f"填写卡信息失败: {e}"
        
        # ==================== Step 6: 智能等待并点击 Save card ====================
        log("[BindCard] Step 6: 点击 Save card / 保存卡...")
        
        try:
            # 精确定位 Save / 保存卡 按钮
            save_btn_span_exact = active_iframe.locator('button:has(span[jsname="V67aGc"]:text-is("Save card"))')
            save_btn_span_save = active_iframe.locator('button:has(span[jsname="V67aGc"]:text-is("Save"))')
            save_btn_span_cn = active_iframe.locator('button:has(span[jsname="V67aGc"]:text-is("保存卡"))')
            save_btn_span_cn2 = active_iframe.locator('button:has(span[jsname="V67aGc"]:text-is("保存"))')
            save_btn_has_text = active_iframe.locator('button:has-text("Save card"), button:has-text("保存卡")')
            save_btn_has_text2 = active_iframe.locator('button:has-text("Save"):not(:has-text("Subscribe")), button:has-text("保存"):not(:has-text("订阅"))')
            save_btn_role = active_iframe.get_by_role("button", name=re.compile(r"^Save", re.IGNORECASE))
            
            combined_save = (
                save_btn_span_exact.or_(save_btn_span_save)
                .or_(save_btn_span_cn).or_(save_btn_span_cn2)
                .or_(save_btn_has_text).or_(save_btn_has_text2)
                .or_(save_btn_role)
            )
            
            await expect(combined_save.first).to_be_visible(timeout=DEFAULT_TIMEOUT)
            
            save_count = await combined_save.count()
            log(f"[BindCard] ✅ 找到 {save_count} 个保存按钮候选")
            
            # 获取第一层 iframe 用于检测 Subscribe 按钮
            iframe_for_subscribe = page.frame_locator('iframe[src*="tokenized.play.google.com"]').first
            subscribe_btn_precise = iframe_for_subscribe.locator('button:has(span[jsname="V67aGc"]:text-is("Subscribe"))')
            subscribe_btn_precise_cn = iframe_for_subscribe.locator('button:has(span[jsname="V67aGc"]:text-is("订阅"))')
            subscribe_btn_check = subscribe_btn_precise.or_(subscribe_btn_precise_cn)
            
            # 点击 Save，第一次点击后每隔2秒重试，最多5次
            save_success = False
            for click_attempt in range(5):
                try:
                    await expect(combined_save.first).to_be_enabled(timeout=5000)
                    await combined_save.first.click(force=True)
                    log(f"[BindCard] ✅ 第{click_attempt + 1}次点击保存按钮")
                    
                    # 等待2秒后检测结果
                    await asyncio.sleep(2)
                    
                    # 检测是否出现订阅按钮
                    try:
                        if await subscribe_btn_check.first.is_visible():
                            log("[BindCard] ✅ 检测到 Subscribe 按钮，保存卡成功")
                            save_success = True
                            break
                    except:
                        pass
                    
                    # 检测 Save 按钮是否已消失（可能成功了）
                    try:
                        if not await combined_save.first.is_visible():
                            log("[BindCard] ℹ️ Save card 按钮已消失")
                            save_success = True
                            break
                    except:
                        pass
                    
                    if click_attempt < 4:
                        log(f"[BindCard] ⏳ 订阅按钮未出现，2秒后重试...")
                    
                except Exception as click_err:
                    log(f"[BindCard] ⚠️ 点击异常: {click_err}")
                    break
            
            # 如果5次都失败，标记卡为不可用
            if not save_success:
                log("[BindCard] ❌ 保存卡失败5次，标记卡片为不可用")
                return False, "CARD_INVALID:保存卡失败，卡片可能无效"
                
        except Exception as e:
            return False, f"CARD_INVALID:保存卡异常 - {str(e)[:50]}"
        
        # ==================== Step 7: 智能等待 Subscribe / 订阅 按钮 ====================
        log("[BindCard] Step 7: 智能等待 Subscribe / 订阅 按钮...")
        
        try:
            # 重新获取第一层 iframe（Subscribe 按钮在第一层！）
            iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]').first
            
            # 精确定位 Subscribe / 订阅 按钮
            # Google 按钮结构: <button jscontroller="..."><span jsname="V67aGc">Subscribe</span></button>
            subscribe_btn_precise = iframe_locator.locator('button:has(span[jsname="V67aGc"]:text-is("Subscribe"))')
            subscribe_btn_precise_cn = iframe_locator.locator('button:has(span[jsname="V67aGc"]:text-is("订阅"))')
            subscribe_btn = subscribe_btn_precise.or_(subscribe_btn_precise_cn)
            
            # 智能等待按钮出现（最多等待 15 秒，每秒检测一次）
            sub_count = 0
            for wait_attempt in range(15):
                sub_count = await subscribe_btn.count()
                if sub_count > 0:
                    log(f"[BindCard] 🔍 找到 {sub_count} 个订阅按钮 (精确选择器)")
                    break
                
                # 尝试备选方案
                subscribe_btn_backup = iframe_locator.locator('button:has-text("Subscribe"), button:has-text("订阅")')
                backup_count = await subscribe_btn_backup.count()
                if backup_count > 0:
                    log(f"[BindCard] 🔍 备选方案找到 {backup_count} 个订阅按钮")
                    subscribe_btn = subscribe_btn_backup
                    sub_count = backup_count
                    break
                
                if wait_attempt < 14:
                    log(f"[BindCard] ⏳ 等待订阅按钮出现... ({wait_attempt + 1}/15)")
                    await asyncio.sleep(1)
            
            if sub_count == 0:
                return False, "CARD_INVALID:保存卡后未出现订阅按钮"
            
            # 等待按钮可见和可用
            await expect(subscribe_btn.first).to_be_visible(timeout=10000)
            await expect(subscribe_btn.first).to_be_enabled(timeout=5000)
            
            # 获取按钮文本用于调试
            try:
                btn_text = await subscribe_btn.first.inner_text()
                log(f"[BindCard] 📋 按钮文本: {btn_text}")
            except:
                pass
            
            # 点击订阅按钮
            await subscribe_btn.first.click(force=True)
            log("[BindCard] ✅ 已点击订阅按钮")
            
            # 等待操作生效
            await asyncio.sleep(2)
            
        except Exception as e:
            return False, f"CARD_INVALID:订阅按钮点击失败 - {str(e)[:50]}"
        
        # ==================== Step 8: 检查订阅状态 ====================
        return await _check_subscription_status(page, account_info, card_info, log_func=log)
        
    except Exception as e:
        log(f"[BindCard] ❌ 绑卡失败: {e}")
        import traceback
        traceback.print_exc()
        return False, f"绑卡错误: {str(e)}"


async def _check_subscription_status(page: Page, account_info: dict = None, card_info: dict = None, log_func=None, is_direct_subscribe: bool = False) -> Tuple[bool, str]:
    """
    @brief 检查订阅状态 (V4 增强版)
    @details 使用多种方式检测订阅成功状态，按可靠性排序
    @param is_direct_subscribe 是否是直接订阅（使用账号原有旧卡），如果是则错误返回 REBIND_NEEDED 而不是 CARD_INVALID
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    # 根据是否是直接订阅决定错误前缀
    # 直接订阅用的是旧卡，失败不应标记当前新卡为不可用
    error_prefix = "REBIND_NEEDED" if is_direct_subscribe else "CARD_INVALID"
    card_type = "旧卡" if is_direct_subscribe else "新卡"
    
    try:
        log("[BindCard] 检查订阅状态...")
        
        # ==================== 方式1: iframe 内检测 "Subscribed" 文字 ====================
        try:
            iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
            
            # 检测多种成功标志
            success_locator = (
                iframe_locator.locator('text=/Subscribed/i')
                .or_(iframe_locator.locator('text=/订阅成功/i'))
                .or_(iframe_locator.locator('text=/Thank you/i'))
                .or_(iframe_locator.locator('[data-subscribed="true"]'))
            )
            
            await expect(success_locator.first).to_be_visible(timeout=15000)
            log("[BindCard] ✅ iframe 内检测到订阅成功标志！")
            
            _update_success_status(account_info, card_info, log_func=log)
            return True, "绑卡订阅成功 (Subscribed)"
            
        except Exception as e1:
            log(f"[BindCard] ⚠️ iframe 内未检测到成功标志: {str(e1)[:50]}")
        
        # ==================== 方式2: 检测错误信息 (快速失败 → 触发换卡) ====================
        try:
            iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
            error_locator = (
                iframe_locator.locator('text=/declined/i')
                .or_(iframe_locator.locator('text=/failed/i'))
                .or_(iframe_locator.locator('text=/error/i'))
                .or_(iframe_locator.locator('text=/invalid/i'))
                .or_(iframe_locator.locator('text=/expired/i'))
                .or_(iframe_locator.locator('text=/拒绝/'))
                .or_(iframe_locator.locator('text=/失败/'))
                .or_(iframe_locator.locator('text=/过期/'))
            )
            if await error_locator.count() > 0:
                error_text = await error_locator.first.inner_text()
                log(f"[BindCard] ❌ 检测到{card_type}支付错误: {error_text}，需要换卡")
                return False, f"{error_prefix}:{card_type}支付失败 - {error_text[:50]}"
        except:
            pass
        
        # ==================== 方式3: 页面全局检测 (严格匹配) ====================
        try:
            # 只匹配明确的成功文案
            page_subscribed = page.locator('text=/You.*subscribed/i, text=/已成功订阅/i, text=/Thank you for subscribing/i')
            if await page_subscribed.count() > 0:
                log("[BindCard] ✅ 页面全局检测到订阅成功！")
                _update_success_status(account_info, card_info, log_func=log)
                return True, "绑卡订阅成功 (Subscribed)"
        except:
            pass
        
        # ==================== 方式4: URL 检测 (严格版) ====================
        try:
            current_url = page.url
            # 只有明确跳转到成功页面才算成功（不在 ai-student 页面）
            if 'one.google.com' in current_url and 'ai-student' not in current_url:
                # 必须是 /home 或 /explore 页面
                if '/home' in current_url or '/explore' in current_url:
                    log(f"[BindCard] ✅ URL 跳转到成功页面: {current_url[:60]}")
                    _update_success_status(account_info, card_info, log_func=log)
                    return True, "绑卡已完成 (URL检测)"
        except:
            pass
        
        # ==================== 无法确认状态 → 触发换卡 ====================
        log(f"[BindCard] ❌ 未检测到明确的订阅成功标志，{card_type}可能被拒绝")
        try:
            log(f"[BindCard] 当前URL: {page.url}")
        except:
            log("[BindCard] 无法获取当前URL")
        
        return False, f"{error_prefix}:{card_type}订阅未成功，卡片可能被拒绝"
        
    except Exception as e:
        error_msg = str(e)
        # 检测浏览器关闭的错误
        if 'closed' in error_msg.lower() or 'target' in error_msg.lower():
            return False, "浏览器已关闭"
        log(f"[BindCard] 状态检查异常: {e}")
        return False, f"状态检查失败: {error_msg[:50]}"


def _update_success_status(account_info: dict = None, card_info: dict = None, log_func=None):
    """更新成功状态到数据库"""
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    try:
        from core.database import DBManager
        
        # 更新账号状态
        if account_info and account_info.get('email'):
            DBManager.update_account_status(account_info['email'], 'subscribed')
            log(f"[BindCard] ✅ 已更新账号状态: {account_info['email']} -> subscribed")
        
        # 更新卡片使用次数
        if card_info and card_info.get('id'):
            usage_count, max_usage = update_card_usage(card_info['id'])
            if usage_count is not None:
                card_num = card_info.get('number', '')[-4:] if card_info.get('number') else '****'
                log(f"[BindCard] ✅ 已更新卡片使用次数: ****{card_num} ({usage_count}/{max_usage})")
            else:
                log(f"[BindCard] ⚠️ 更新卡片使用次数失败")
    except Exception as e:
        log(f"[BindCard] ⚠️ 更新状态失败: {e}")


def process_bind_card(browser_id: str, card_info: dict = None, log_callback: Callable = None) -> Tuple[bool, str]:
    """
    @brief 处理单个浏览器的绑卡订阅 (V3)
    @param browser_id 浏览器ID
    @param card_info 卡信息
    @param log_callback 日志回调
    @return (success, message)
    """
    def log(msg):
        print(msg)
        if log_callback:
            log_callback(msg)
    
    log(f"[BindCard] 开始处理: {browser_id[:12]}...")
    
    # 导入依赖
    try:
        from core.bit_api import openBrowser, closeBrowser, get_browser_info
        from core.database import DBManager
        from google.backend.google_auth import google_login  # V3: 使用 google_login
    except ImportError as e:
        return False, f"导入失败: {e}"
    
    # ==================== 获取账号信息 ====================
    account_info = None
    
    # 1. 优先从数据库获取 (使用 with 语句确保连接正确关闭)
    try:
        with DBManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, password, recovery_email, secret_key 
                FROM accounts WHERE browser_id = ?
            """, (browser_id,))
            row = cursor.fetchone()
            
            if row and row[1]:  # 确保有密码
                account_info = {
                    'email': row[0],
                    'password': row[1],
                    'backup': row[2],
                    'backup_email': row[2],
                    'secret': row[3],
                    '2fa_secret': row[3]
                }
                log(f"[BindCard] 从数据库获取账号: {account_info['email']}")
    except Exception as e:
        log(f"[BindCard] 数据库读取失败: {e}")
    
    # 2. 降级从浏览器备注获取
    if not account_info:
        try:
            browser_info = get_browser_info(browser_id)
            if browser_info:
                remark = browser_info.get('remark', '')
                if '----' in remark:
                    parts = remark.split('----')
                    if len(parts) >= 4:
                        account_info = {
                            'email': parts[0].strip(),
                            'password': parts[1].strip(),
                            'backup': parts[2].strip(),
                            'backup_email': parts[2].strip(),
                            'secret': parts[3].strip(),
                            '2fa_secret': parts[3].strip()
                        }
                        log(f"[BindCard] 从浏览器备注获取账号: {account_info['email']}")
        except Exception as e:
            log(f"[BindCard] 获取浏览器信息失败: {e}")
    
    # ==================== 打开浏览器 ====================
    result = openBrowser(browser_id)
    if not result or not result.get('success'):
        return False, f"打开浏览器失败: {result.get('msg', '未知错误') if result else '无响应'}"
    
    ws_endpoint = result.get('data', {}).get('ws')
    if not ws_endpoint:
        closeBrowser(browser_id)
        return False, "无法获取 WebSocket 端点"
    
    # ==================== 执行绑卡流程 ====================
    async def _run():
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()
                
                # ========== Step 1: 智能登录 ==========
                if account_info and account_info.get('password'):
                    log("[BindCard] Step 1: 智能登录检测...")
                    login_success, login_msg = await google_login(page, account_info)
                    if not login_success:
                        # 额外检查：URL 显示已登录
                        if 'myaccount.google.com' in page.url or 'one.google.com' in page.url:
                            log(f"[BindCard] ⚠️ 登录函数返回失败，但 URL 显示已登录")
                        else:
                            return False, f"登录失败: {login_msg}"
                    log(f"[BindCard] 登录状态: {login_msg}")
                else:
                    log("[BindCard] ⚠️ 无账号信息，跳过登录")
                
                # ========== Step 2: 导航到目标页面 ==========
                target_url = "https://one.google.com/ai-student?g1_landing_page=75"
                log("[BindCard] Step 2: 导航到 Google One 学生页面...")
                await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
                
                # 智能等待页面加载
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    pass
                
                # ========== Step 2.5: 资格预检测 (可选但推荐) ==========
                log("[BindCard] Step 2.5: 检测账号资格状态...")
                try:
                    from google.backend.google_auth import detect_eligibility_status, STATUS_VERIFIED, STATUS_SUBSCRIBED, STATUS_INELIGIBLE, STATUS_LINK_READY
                    
                    status, sheer_link = await detect_eligibility_status(page, timeout=10)
                    log(f"[BindCard] 资格状态: {status}")
                    
                    if status == STATUS_SUBSCRIBED:
                        log("[BindCard] ✅ 账号已订阅，无需绑卡")
                        return True, "账号已是订阅状态"
                    
                    if status == STATUS_INELIGIBLE:
                        log("[BindCard] ❌ 账号无资格，无法绑卡")
                        return False, "账号无资格 (ineligible)"
                    
                    if status == STATUS_LINK_READY:
                        log("[BindCard] ⚠️ 账号待验证，需要先完成 SheerID 验证")
                        return False, f"账号待验证，请先完成 SheerID 验证: {sheer_link or '无链接'}"
                    
                    if status != STATUS_VERIFIED:
                        log(f"[BindCard] ⚠️ 未知状态 '{status}'，尝试继续绑卡...")
                    
                except Exception as e:
                    log(f"[BindCard] ⚠️ 资格检测异常: {e}，尝试继续绑卡...")
                
                # ========== Step 3: 执行绑卡 ==========
                log("[BindCard] Step 3: 执行绑卡流程...")
                return await auto_bind_card(page, card_info, account_info, log_callback=log)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return False, f"绑卡异常: {str(e)}"
    
    try:
        return asyncio.run(_run())
    finally:
        # 确保关闭浏览器
        log(f"[BindCard] 关闭浏览器: {browser_id[:12]}...")
        closeBrowser(browser_id)


def process_bind_card_batch(
    browser_ids: List[str],
    thread_count: int = 1,
    callback: Callable = None,
    stop_check: Callable = None,
    log_callback: Callable = None
) -> Dict:
    """
    @brief 批量绑卡订阅
    @param browser_ids 浏览器ID列表
    @param thread_count 并发线程数
    @param callback 进度回调 (browser_id, success, message)
    @param stop_check 停止检查函数
    @param log_callback 日志回调
    @return 统计结果
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    stats = {
        'total': len(browser_ids),
        'processed': 0,
        'success': 0,
        'failed': 0,
    }
    
    if log_callback:
        log_callback(f"[BindCard] 开始批量绑卡，共 {len(browser_ids)} 个，并发: {thread_count}")
    
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = {}
        
        for bid in browser_ids:
            if stop_check and stop_check():
                break
            future = executor.submit(process_bind_card, bid, None, log_callback)
            futures[future] = bid
        
        for future in as_completed(futures):
            if stop_check and stop_check():
                if log_callback:
                    log_callback("[BindCard] 任务已停止")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            
            bid = futures[future]
            stats['processed'] += 1
            
            try:
                success, msg = future.result()
                
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                
                if callback:
                    callback(bid, success, msg)
                    
            except Exception as e:
                stats['failed'] += 1
                if callback:
                    callback(bid, False, str(e))
    
    return stats
