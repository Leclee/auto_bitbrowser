from bit_api import *
import time
import asyncio
import pyotp
import re
from playwright.async_api import async_playwright, Playwright, Page

async def google_login(page: Page, account_info: dict):
    """
    通用的Google登录函数
    支持: 账号密码登录, 2FA(TOTP), 辅助邮箱验证
    并处理登录后的安全提醒弹窗
    """
    print(f"[Login] 开始登录流程: {account_info.get('email')}")
    
    # 0. 导航到登录页
    try:
        # 检查是否已经在登录后的页面
        if "accounts.google.com" not in page.url and "myaccount.google.com" not in page.url and "one.google.com" not in page.url:
            await page.goto('https://accounts.google.com', timeout=60000)
    except Exception as e:
        print(f"[Login] 导航失败(可能已在页面): {e}")

    # 1. 输入邮箱
    try:
        email = account_info.get('email')
        # 检查是否存在邮箱输入框
        try:
            email_input = await page.wait_for_selector('input[type="email"]', timeout=5000)
            if email_input:
                print(f"[Login] 输入邮箱: {email}")
                await email_input.fill(email)
                await page.click('#identifierNext >> button')
                
                # 2. 输入密码
                print("[Login] 等待密码输入框...")
                try:
                    await page.wait_for_selector('input[type="password"]', state='visible', timeout=10000)
                    password = account_info.get('password')
                    if password:
                        print("[Login] 输入密码...")
                        await page.fill('input[type="password"]', password)
                        await page.click('#passwordNext >> button')
                        print("[Login] 密码已提交，等待跳转...")
                        await asyncio.sleep(5) # 增加等待时间
                    else:
                        print("[Login] 警告: 未提供密码")
                except:
                    print("[Login] 未检测到密码输入框，可能由于无需密码(已记住)或邮箱错误")
        except:
            pass # 邮箱输入框未出现，可能已经是密码页或已登录
            
    except Exception as e:
        print(f"[Login] 邮箱/密码步骤可能的异常(或许已登录): {e}")

    # 等待可能的跳转或验证步骤
    await asyncio.sleep(3)

    # 3. 处理各种验证挑战 (循环检测，直到登录成功或超时)
    max_checks = 5
    for i in range(max_checks):
        print(f"[Login] 检查验证步骤 ({i+1}/{max_checks})...")
        
        # A. 检测辅助邮箱验证 (Confirm your recovery email)
        try:
            # 情况1: 选择验证方式列表页面
            # 寻找包含 "Confirm your recovery email" 文本的列表项
            # 根据截图，该文本位于一个 role="link" 的 div 容器内，这是最稳健的点击目标
            recovery_option = page.locator('div[role="link"]:has-text("Confirm your recovery email")').first
            
            # 后备：如果找不到 role="link"，直接找文本
            if await recovery_option.count() == 0:
                print("[Login] 未找到 role=link，尝试直接定位文本...")
                recovery_option = page.locator('text="Confirm your recovery email"').first

            if await recovery_option.count() > 0 and await recovery_option.is_visible():
                print("[Login] 点击 'Confirm your recovery email' 选项")
                await recovery_option.hover() # 先悬停
                await asyncio.sleep(0.5)
                await recovery_option.click(force=True) # 强制点击
                await asyncio.sleep(3) # 等待跳转
            
            # 情况2: 辅助邮箱输入框页面
            # 特征: 包含提示 "Confirm your recovery email" 或 "Enter recovery email"
            # 并且有输入框 input[type="email"]
            if await page.locator("text=Confirm your recovery email").count() > 0 or \
               await page.locator("text=Enter recovery email").count() > 0:
                
                recovery_input = page.locator('input[id="knowledge-preregistered-email-response"], input[name="knowledgePreregisteredEmailResponse"]')
                if await recovery_input.count() > 0 and await recovery_input.is_visible():
                    print("[Login] 检测到辅助邮箱输入框")
                    backup_email = account_info.get('backup') or account_info.get('backup_email')
                    
                    if backup_email:
                        print(f"[Login] 输入辅助邮箱: {backup_email}")
                        await recovery_input.fill(backup_email)
                        # 点击 Next
                        next_btn = page.locator('button:has-text("Next"), button:has-text("下一步")').first
                        if await next_btn.count() > 0:
                            await next_btn.click()
                        else:
                            await page.keyboard.press('Enter')
                        await asyncio.sleep(3)
                    else:
                        print("[Login] 错误: 需要辅助邮箱但未提供!")
        except Exception as e:
            print(f"[Login] 辅助邮箱检测出错: {e}")

        # B. 检测 2FA (TOTP)
        try:
            totp_input = page.locator('input[name="totpPin"], input[id="totpPin"], input[type="tel"]').first
            if await totp_input.count() > 0 and await totp_input.is_visible():
                print("[Login] 检测到 2FA 输入框")
                
                # 尝试多种可能的键名获取密钥
                secret = account_info.get('secret') or account_info.get('2fa_secret') or account_info.get('secret_key')
                
                if secret:
                    try:
                        s = secret.replace(" ", "").strip()
                        totp = pyotp.TOTP(s)
                        code = totp.now()
                        print(f"[Login] 生成并输入 2FA 代码: {code}")
                        await totp_input.fill(code)
                        # 点击 Next
                        await page.click('#totpNext >> button')
                        await asyncio.sleep(3)
                    except Exception as otp_e:
                        print(f"[Login] TOTP 生成失败: {otp_e}")
                else:
                    print(f"[Login] 错误: 需要 2FA 但未提供密钥! 当前可用字段: {list(account_info.keys())}")
        except Exception as e:
            print(f"[Login] 2FA 检测出错: {e}")

        # 如果已经跳转到非登录相关页面(如myaccount)，则跳出
        if "myaccount.google.com" in page.url or "google.com/search" in page.url or "one.google.com" in page.url:
            print("[Login] 已检测到登录成功页面")
            break
            
        await asyncio.sleep(2)

    # 4. 处理登录后的安全增强提醒 (点击 Cancel / Not now)
    try:
        await asyncio.sleep(2)
        # 常见按钮文本: Not now, Cancel, No thanks
        potential_buttons = [
            'button:has-text("Not now")',
            'button:has-text("Cancel")',
            'button:has-text("No thanks")',
            'button:has-text("暂不")',
            'button:has-text("取消")'
        ]
        
        for btn_selector in potential_buttons:
            btn = page.locator(btn_selector).first
            if await btn.count() > 0 and await btn.is_visible():
                print(f"[Login] 检测到安全弹窗按钮: {await btn.inner_text()}, 点击跳过...")
                await btn.click()
                await asyncio.sleep(1)
                break
                
    except Exception as e:
        print(f"[Login] 安全弹窗处理出错(通常可忽略): {e}")

    print("[Login] 登录流程结束")

async def run(playwright: Playwright):
    # 测试代码，实际使用时会被import
    pass

async def main():
    async with async_playwright() as playwright:
      await run(playwright)

# asyncio.run(main())