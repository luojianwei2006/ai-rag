"""
小红书自动发布服务（基于 Playwright 浏览器自动化）

发布流程：
  1. 启动无头浏览器，加载账号 cookies
  2. 访问发布页，检查登录状态
  2.5 点击"上传图文"Tab（默认停在"上传视频"）
  3. 等待图文上传区域加载
  4. 上传图片（如有）
  5. 填写标题
  6. 填写正文
  7. 添加话题标签
  8. 点击发布按钮
  9. 等待发布成功
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger("xhs_publisher")

# 小红书创作中心地址
XHS_CREATOR_URL = "https://creator.xiaohongshu.com"
XHS_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"

# 截图保存目录
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "xhs_screenshots")


async def _check_playwright_installed() -> bool:
    """检测 playwright 是否安装"""
    try:
        from playwright.async_api import async_playwright  # noqa
        return True
    except ImportError:
        return False


async def publish_to_xhs(
    cookies_json: str,
    title: str,
    content: str,
    tags: Optional[str] = None,
    image_paths: Optional[list] = None,
    headless: bool = True,
) -> dict:
    """
    发布一篇图文笔记到小红书。

    Args:
        cookies_json: 账号 cookies JSON 字符串（playwright cookies 格式）
        title: 笔记标题（最多 20 字）
        content: 正文内容
        tags: 话题标签，逗号分隔，如 "生活,美食,分享"
        image_paths: 本地图片路径列表（至少 1 张，最多 9 张）
        headless: 是否无头模式（生产环境用 True，调试用 False）

    Returns:
        {"success": True, "url": "https://www.xiaohongshu.com/explore/xxx"}
        or {"success": False, "error": "错误原因"}
    """
    if not await _check_playwright_installed():
        return {
            "success": False,
            "error": "Playwright 未安装，请先执行: pip install playwright && playwright install chromium"
        }

    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {"success": False, "error": "Playwright 导入失败"}

    # 解析 cookies
    try:
        cookies = json.loads(cookies_json) if cookies_json else []
    except (json.JSONDecodeError, TypeError):
        cookies = []

    # 补充 Playwright 要求的 domain/path 字段
    # 前端可能只传了 {name, value}，Playwright 要求至少有 domain+path 或 url
    if cookies and isinstance(cookies, list):
        normalized = []
        for c in cookies:
            if not isinstance(c, dict):
                continue
            if "name" not in c or "value" not in c:
                continue
            if c.get("domain") or c.get("url"):
                normalized.append(c)
            else:
                c["domain"] = ".xiaohongshu.com"
                c["path"] = "/"
                normalized.append(c)
        cookies = normalized

    note_url = None

    # 确保截图目录存在
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )

        # 注入 cookies
        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()

        # 辅助函数：截图并记录
        async def _screenshot(step: str):
            path = os.path.join(SCREENSHOT_DIR, f"{ts}_{step}.png")
            try:
                await page.screenshot(path=path, full_page=True)
                logger.info(f"截图已保存: {path}")
            except Exception as e:
                logger.warning(f"截图失败: {e}")

        try:
            # ── Step 1: 打开发布页 ──
            logger.info("打开小红书创作者中心...")
            await page.goto(XHS_PUBLISH_URL, wait_until="networkidle", timeout=30000)
            await _screenshot("01_page_loaded")

            # ── Step 2: 检查是否需要登录 ──
            current_url = page.url
            if "login" in current_url or "signin" in current_url:
                await _screenshot("02_login_redirect")
                await browser.close()
                return {"success": False, "error": "Cookies 已失效，请重新登录获取 Cookies"}

            # ── Step 2.5: 点击"上传图文"Tab ──
            # 页面默认停在"上传视频"，必须切换到"上传图文"才会出现图文编辑区
            logger.info("切换到「上传图文」Tab...")
            await asyncio.sleep(2)  # 等待页面 JS 渲染完成
            await _screenshot("02a_before_tab_switch")

            tab_clicked = False
            try:
                # 策略1：用 locator get_by_text 找到包含"上传图文"的最小叶子元素并点击
                # 注意：has-text 会匹配所有包含该文字的祖先元素，用 filter + first 确保拿到最小的
                tab_locator = page.locator("*").filter(has_text=re.compile(r"^上传图文$"))
                cnt = await tab_locator.count()
                logger.info(f"locator 找到「上传图文」元素数量: {cnt}")
                if cnt > 0:
                    # 从最后一个（通常是最小/最内层）开始尝试
                    for i in range(cnt - 1, -1, -1):
                        el = tab_locator.nth(i)
                        try:
                            if await el.is_visible():
                                await el.click()
                                tab_clicked = True
                                logger.info(f"locator 点击成功，第 {i} 个元素")
                                break
                        except Exception:
                            pass

                # 策略2：JavaScript 直接找包含"上传图文"文字的元素并点击
                if not tab_clicked:
                    logger.info("尝试 JS 方式点击「上传图文」Tab...")
                    js_result = await page.evaluate("""() => {
                        // 遍历所有元素，找 innerText === "上传图文" 的叶子节点
                        const all = Array.from(document.querySelectorAll('*'));
                        const candidates = all.filter(el => {
                            const t = el.innerText?.trim();
                            return t === '上传图文' || t === '上传图文 ';
                        });
                        if (candidates.length === 0) {
                            // 放宽：包含"图文"
                            const c2 = all.filter(el => {
                                const t = el.innerText?.trim();
                                return t && t.includes('图文') && t.length < 10;
                            });
                            if (c2.length > 0) {
                                c2[c2.length - 1].click();
                                return 'clicked_fuzzy:' + c2[c2.length-1].outerHTML.substring(0, 100);
                            }
                            return 'not_found';
                        }
                        // 优先点最后一个（最小/最内层）
                        candidates[candidates.length - 1].click();
                        return 'clicked:' + candidates[candidates.length-1].outerHTML.substring(0, 100);
                    }""")
                    logger.info(f"JS 点击结果: {js_result}")
                    if js_result and js_result != "not_found":
                        tab_clicked = True

                if not tab_clicked:
                    # 打印页面元素辅助排查
                    await _screenshot("02b_tab_not_found")
                    tab_info = await page.evaluate("""() => {
                        const all = Array.from(document.querySelectorAll('*'));
                        return all.filter(el => {
                            const t = el.innerText?.trim();
                            return t && t.length < 25 && (
                                t.includes('上传') || t.includes('图文') || t.includes('视频')
                                || el.className?.toString().includes('tab')
                                || el.getAttribute('role') === 'tab'
                            );
                        }).slice(0, 30).map(el => ({
                            text: el.innerText?.trim(),
                            tag: el.tagName,
                            cls: el.className?.toString().substring(0, 80),
                            role: el.getAttribute('role') || '',
                        }));
                    }""")
                    logger.error(f"未找到「上传图文」Tab，页面元素: {json.dumps(tab_info, ensure_ascii=False)}")
                    await browser.close()
                    return {"success": False, "error": "未找到「上传图文」Tab，请查看日志和截图"}

                await asyncio.sleep(2)
                await _screenshot("02c_after_tab_click")

                # 验证：确认已切换到图文模式（检查 URL 或上传区域）
                current_url = page.url
                logger.info(f"Tab 切换后 URL: {current_url}")

            except Exception as tab_err:
                await _screenshot("02b_tab_error")
                logger.error(f"切换 Tab 异常: {tab_err}")
                await browser.close()
                return {"success": False, "error": f"切换「上传图文」Tab 失败: {tab_err}"}

            # ── Step 3: 等待图文上传区域出现 ──
            logger.info("等待图文上传区域加载...")
            try:
                await page.wait_for_selector("input[type='file'], [class*='upload']", timeout=15000)
                logger.info("图文上传区域已出现")
            except PWTimeout:
                logger.warning("等待上传区域超时，尝试继续...")
                await _screenshot("03_upload_timeout")
            await asyncio.sleep(1)

            # ── Step 4: 上传图片 ──
            if image_paths:
                try:
                    valid_paths = [p for p in image_paths if os.path.exists(p)]
                    if valid_paths:
                        file_inputs = await page.query_selector_all("input[type='file']")
                        logger.info(f"找到 {len(file_inputs)} 个 file input")
                        upload_input = None
                        for fi in file_inputs:
                            accept = await fi.get_attribute("accept") or ""
                            multiple = await fi.get_attribute("multiple")
                            if "image" in accept and multiple is not None:
                                upload_input = fi
                                logger.info("找到 multiple 图片 input")
                                break

                        # 退而求其次：找 accept 含 image 的
                        if not upload_input:
                            for fi in file_inputs:
                                accept = await fi.get_attribute("accept") or ""
                                if "image" in accept:
                                    upload_input = fi
                                    logger.info("找到 image input（非 multiple）")
                                    break

                        if not upload_input and file_inputs:
                            upload_input = file_inputs[0]

                        if upload_input:
                            # 检查是否支持 multiple，单文件 input 只传第一张
                            multiple = await upload_input.get_attribute("multiple")
                            if multiple is not None:
                                await upload_input.set_input_files(valid_paths[:9])
                                logger.info(f"批量上传 {min(len(valid_paths), 9)} 张图片")
                            else:
                                await upload_input.set_input_files([valid_paths[0]])
                                logger.info(f"单文件 input，只上传第 1 张: {valid_paths[0]}")
                            await asyncio.sleep(4)
                            await _screenshot("04_after_upload")
                        else:
                            logger.warning("未找到文件上传 input")
                except Exception as e:
                    logger.warning(f"图片上传失败: {e}，将继续发布文字内容")

            # ── Step 5: 填写标题 ──
            await asyncio.sleep(1)
            title_input = None
            try:
                for sel in [
                    "input[placeholder*='标题']",
                    ".title-input input",
                    "input[class*='title']",
                    "input[maxlength='20']",
                    "input[maxlength='50']",
                ]:
                    title_input = await page.query_selector(sel)
                    if title_input:
                        logger.info(f"找到标题输入框: {sel}")
                        break
                if title_input:
                    await title_input.click()
                    await title_input.fill(title[:20])
                    logger.info(f"已填写标题: {title[:20]}")
                else:
                    logger.warning("未找到标题输入框")
                    await _screenshot("05_no_title_input")
            except Exception as e:
                logger.warning(f"填写标题失败: {e}")

            # ── Step 6: 填写正文 ──
            await asyncio.sleep(0.5)
            content_editor = None
            try:
                for sel in [
                    ".ql-editor",
                    "[contenteditable='true']",
                    "textarea[placeholder*='正文']",
                    "textarea[placeholder*='内容']",
                    ".desc-input textarea",
                    ".content-input textarea",
                ]:
                    els = await page.query_selector_all(sel)
                    for el in els:
                        tag = await el.evaluate("el => el.tagName")
                        if tag != "INPUT":
                            content_editor = el
                            logger.info(f"找到正文编辑器: {sel}")
                            break
                    if content_editor:
                        break
                if content_editor:
                    await content_editor.click()
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Control+a")
                    await page.keyboard.press("Delete")
                    await content_editor.type(content, delay=10)
                    logger.info(f"已填写正文，长度: {len(content)}")
                else:
                    logger.warning("未找到正文输入框")
                    await _screenshot("06_no_content_input")
            except Exception as e:
                logger.warning(f"填写正文失败: {e}")
            await _screenshot("06b_after_content")

            # ── Step 7: 添加话题标签 ──
            if tags and content_editor:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                for tag in tag_list[:5]:
                    try:
                        await content_editor.click()
                        await page.keyboard.press("End")
                        await content_editor.type(f" #{tag}", delay=50)
                        await asyncio.sleep(1)
                        try:
                            topic_item = await page.wait_for_selector(
                                ".topic-item, [class*='topic-item'], [class*='hash-tag']",
                                timeout=2000
                            )
                            if topic_item:
                                await topic_item.click()
                                await asyncio.sleep(0.3)
                        except PWTimeout:
                            pass
                    except Exception as e:
                        logger.warning(f"添加话题 #{tag} 失败: {e}")

            # ── Step 8: 点击发布按钮 ──
            await asyncio.sleep(1)
            await _screenshot("07_before_publish")
            publish_btn = None
            for sel in [
                "button.publish-btn",
                "button:has-text('发布')",
                ".publish-button button",
                "[class*='publish'][class*='btn']",
                "button:has-text('提交')",
            ]:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        is_disabled = await btn.get_attribute("disabled")
                        if not is_disabled:
                            publish_btn = btn
                            logger.info(f"找到发布按钮: {sel}")
                            break
                except Exception:
                    pass

            if not publish_btn:
                await _screenshot("07_no_publish_btn")
                debug_info = await page.evaluate("""() => ({
                    url: location.href,
                    inputs: [...document.querySelectorAll('input, textarea, [contenteditable]')].map(el => ({
                        tag: el.tagName, placeholder: el.placeholder || '',
                        cls: el.className.toString().substring(0, 80)
                    })),
                    buttons: [...document.querySelectorAll('button')].map(el => ({
                        text: el.innerText.trim().substring(0, 30),
                        cls: el.className.toString().substring(0, 80),
                        disabled: el.disabled
                    }))
                })""")
                logger.info(f"页面URL: {debug_info['url']}")
                logger.info(f"页面输入框: {json.dumps(debug_info['inputs'], ensure_ascii=False)}")
                logger.info(f"页面按钮: {json.dumps(debug_info['buttons'], ensure_ascii=False)}")
                await browser.close()
                return {"success": False, "error": "未找到发布按钮，请查看截图"}

            logger.info("点击发布按钮...")
            await publish_btn.click()

            # ── Step 9: 等待发布成功 ──
            try:
                await page.wait_for_url(
                    re.compile(r"xiaohongshu\.com/(explore|user|success|manage)"),
                    timeout=20000
                )
                note_url = page.url
                logger.info(f"发布成功！笔记链接: {note_url}")
            except PWTimeout:
                await _screenshot("09_publish_timeout")
                try:
                    success_el = await page.wait_for_selector("[class*='success']", timeout=5000)
                    if success_el:
                        note_url = page.url
                        logger.info("检测到发布成功提示")
                except PWTimeout:
                    error_el = await page.query_selector("[class*='error'], .error-tip")
                    error_text = await error_el.inner_text() if error_el else "发布超时，请手动确认是否成功"
                    await browser.close()
                    return {"success": False, "error": error_text}

        except Exception as e:
            logger.exception(f"发布过程中发生异常: {e}")
            await _screenshot("99_exception")
            await browser.close()
            return {"success": False, "error": str(e)}

        await browser.close()

    return {
        "success": True,
        "url": note_url or XHS_CREATOR_URL,
    }


async def save_xhs_cookies(
    xhs_phone: str,
    xhs_password: str,
    headless: bool = False,
) -> dict:
    """
    通过账号密码登录小红书，保存并返回 cookies。
    注意：小红书有验证码，通常需要 headless=False 人工完成滑块。

    Returns:
        {"success": True, "cookies": [...]}
        or {"success": False, "error": "..."}
    """
    if not await _check_playwright_installed():
        return {
            "success": False,
            "error": "Playwright 未安装，请先执行: pip install playwright && playwright install chromium"
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"success": False, "error": "Playwright 导入失败"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        try:
            await page.goto("https://www.xiaohongshu.com", timeout=20000)
            await asyncio.sleep(2)
            # 此处仅打开浏览器，实际登录需人工完成（验证码/二维码）
            # 在非无头模式下，等待用户登录完成（最多 5 分钟）
            if not headless:
                logger.info("请在浏览器中完成登录（最多等待 5 分钟）...")
                await page.wait_for_url(
                    re.compile(r"xiaohongshu\.com(?!/login|/signin)"),
                    timeout=300000
                )

            cookies = await context.cookies()
            await browser.close()
            return {"success": True, "cookies": cookies}

        except Exception as e:
            await browser.close()
            return {"success": False, "error": str(e)}
