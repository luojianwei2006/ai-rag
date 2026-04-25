"""
小红书自动发布服务（基于 Playwright 浏览器自动化）

发布流程：
  1. 启动无头浏览器，加载账号 cookies
  2. 验证 cookies 是否有效（访问创作者中心）
  3. 若 cookies 失效，标记账号状态为 cookie_expired，抛出异常
  4. 填写标题、正文、话题标签，上传封面图（如有）
  5. 点击发布，等待成功跳转，提取笔记链接
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("xhs_publisher")

# 小红书创作中心地址
XHS_CREATOR_URL = "https://creator.xiaohongshu.com"
XHS_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"


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

    try:
        cookies = json.loads(cookies_json) if cookies_json else []
    except (json.JSONDecodeError, TypeError):
        cookies = []

    note_url = None

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

        try:
            # ── Step 1: 打开发布页 ──
            logger.info("打开小红书创作者中心...")
            await page.goto(XHS_PUBLISH_URL, wait_until="networkidle", timeout=30000)

            # ── Step 2: 检查是否需要登录 ──
            current_url = page.url
            if "login" in current_url or "signin" in current_url:
                await browser.close()
                return {"success": False, "error": "Cookies 已失效，请重新登录获取 Cookies"}

            # ── Step 3: 等待发布页面加载 ──
            try:
                # 等待上传区域或发布按钮出现
                await page.wait_for_selector(
                    ".upload-input, input[type='file'], .publish-btn",
                    timeout=15000
                )
            except PWTimeout:
                # 截图辅助调试
                logger.warning("等待上传区域超时，尝试继续...")

            await asyncio.sleep(1)

            # ── Step 4: 上传图片 ──
            if image_paths:
                try:
                    file_input = await page.query_selector("input[type='file']")
                    if file_input:
                        valid_paths = [p for p in image_paths if os.path.exists(p)]
                        if valid_paths:
                            await file_input.set_input_files(valid_paths[:9])
                            logger.info(f"已上传 {len(valid_paths)} 张图片")
                            await asyncio.sleep(3)  # 等待图片上传完成
                except Exception as e:
                    logger.warning(f"图片上传失败: {e}，将继续发布文字内容")

            # ── Step 5: 填写标题 ──
            await asyncio.sleep(1)
            try:
                # 小红书标题输入框
                title_selectors = [
                    ".title-input input",
                    "input[placeholder*='标题']",
                    ".note-title input",
                    "input.title",
                ]
                title_input = None
                for sel in title_selectors:
                    title_input = await page.query_selector(sel)
                    if title_input:
                        break

                if title_input:
                    await title_input.click()
                    await title_input.fill("")
                    await title_input.type(title[:20], delay=30)
                    logger.info(f"已填写标题: {title[:20]}")
                else:
                    logger.warning("未找到标题输入框")
            except Exception as e:
                logger.warning(f"填写标题失败: {e}")

            # ── Step 6: 填写正文 ──
            await asyncio.sleep(0.5)
            try:
                content_selectors = [
                    ".content-input .ql-editor",
                    ".note-content .ql-editor",
                    "[contenteditable='true']",
                    "textarea[placeholder*='正文']",
                    ".desc-input textarea",
                ]
                content_editor = None
                for sel in content_selectors:
                    content_editor = await page.query_selector(sel)
                    if content_editor:
                        break

                if content_editor:
                    await content_editor.click()
                    # 使用 JS 设置内容（处理 contenteditable）
                    await page.evaluate(
                        """(el, text) => {
                            el.focus();
                            document.execCommand('selectAll');
                            document.execCommand('delete');
                            document.execCommand('insertText', false, text);
                        }""",
                        content_editor,
                        content,
                    )
                    logger.info("已填写正文")
                else:
                    logger.warning("未找到正文输入框")
            except Exception as e:
                logger.warning(f"填写正文失败: {e}")

            # ── Step 7: 添加话题标签 ──
            if tags:
                await asyncio.sleep(0.5)
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                for tag in tag_list[:5]:  # 最多5个话题
                    try:
                        # 在正文末尾输入 #话题
                        if content_editor:
                            await content_editor.click()
                            await page.keyboard.press("End")
                            await content_editor.type(f" #{tag}", delay=50)
                            await asyncio.sleep(0.8)
                            # 等待话题联想框并选择第一个
                            try:
                                topic_item = await page.wait_for_selector(
                                    ".topic-item:first-child, .hash-tag-item:first-child",
                                    timeout=2000
                                )
                                if topic_item:
                                    await topic_item.click()
                                    await asyncio.sleep(0.3)
                            except PWTimeout:
                                await page.keyboard.press("Enter")
                    except Exception as e:
                        logger.warning(f"添加话题 #{tag} 失败: {e}")

            # ── Step 8: 点击发布按钮 ──
            await asyncio.sleep(1)
            publish_selectors = [
                "button.publish-btn",
                "button:has-text('发布')",
                ".publish-button",
                "[class*='publish'][class*='btn']",
            ]
            publish_btn = None
            for sel in publish_selectors:
                try:
                    publish_btn = await page.query_selector(sel)
                    if publish_btn:
                        is_disabled = await publish_btn.get_attribute("disabled")
                        if not is_disabled:
                            break
                        publish_btn = None
                except Exception:
                    pass

            if not publish_btn:
                await browser.close()
                return {"success": False, "error": "未找到发布按钮，页面可能已变更，请截图检查"}

            logger.info("点击发布按钮...")
            await publish_btn.click()

            # ── Step 9: 等待发布成功 ──
            try:
                # 等待跳转到成功页或笔记详情页
                await page.wait_for_url(
                    re.compile(r"xiaohongshu\.com/(explore|user|success)"),
                    timeout=20000
                )
                note_url = page.url
                logger.info(f"发布成功！笔记链接: {note_url}")
            except PWTimeout:
                # 尝试从页面提取成功信息
                try:
                    success_el = await page.wait_for_selector(
                        ".success-tip, .publish-success, [class*='success']",
                        timeout=5000
                    )
                    if success_el:
                        note_url = page.url
                        logger.info("检测到发布成功提示")
                except PWTimeout:
                    # 检查是否有错误提示
                    error_el = await page.query_selector(".error-tip, .error-message, [class*='error']")
                    error_text = await error_el.inner_text() if error_el else "发布超时，请手动确认"
                    await browser.close()
                    return {"success": False, "error": error_text}

        except Exception as e:
            logger.exception(f"发布过程中发生异常: {e}")
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
