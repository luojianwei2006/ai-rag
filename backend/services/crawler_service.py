"""
网页爬虫服务
支持单页爬取和全站爬取（最多5层深度）
"""
import asyncio
import hashlib
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


class CrawlResult:
    def __init__(self, url: str, title: str, content: str, depth: int = 0):
        self.url = url
        self.title = title
        self.content = content
        self.depth = depth


def _normalize_url(url: str) -> str:
    """规范化URL（去掉锚点、查询参数中的会话参数、尾部斜杠等）"""
    parsed = urlparse(url)
    # 去掉锚点
    normalized = parsed._replace(fragment="").geturl()
    return normalized.rstrip("/")


def _is_under_start_url(start_url: str, target_url: str) -> bool:
    """
    判断 target_url 是否在 start_url 的范围内。
    规则：
    1. 必须是相同的域名（netloc）
    2. target_url 的路径必须以 start_url 的路径前缀开头
    例如：start_url=https://example.com/docs/
          允许：https://example.com/docs/api, https://example.com/docs/guide/intro
          不允许：https://example.com/blog, https://other.com/docs
    """
    base = urlparse(start_url)
    target = urlparse(target_url)

    # 域名必须相同
    if base.netloc != target.netloc:
        return False

    # 获取起始路径前缀（确保以 / 结尾进行前缀匹配）
    base_path = base.path.rstrip("/")
    target_path = target.path

    # 如果起始路径为空（即根路径），则允许所有同域名页面
    if not base_path:
        return True

    # target 路径必须以 base_path 开头，且下一个字符是 / 或结尾
    return target_path == base_path or target_path.startswith(base_path + "/")


def _content_fingerprint(content: str) -> str:
    """计算内容指纹（用于去重）：取正文前2000字符的md5"""
    # 标准化：去掉多余空白再计算
    normalized = " ".join(content.split())
    sample = normalized[:2000]
    return hashlib.md5(sample.encode("utf-8")).hexdigest()


def _is_duplicate(content: str, seen_fingerprints: set) -> bool:
    """检查内容是否重复"""
    fp = _content_fingerprint(content)
    if fp in seen_fingerprints:
        return True
    seen_fingerprints.add(fp)
    return False


def _extract_text(html: str) -> tuple[str, str]:
    """从HTML中提取标题和正文文本"""
    soup = BeautifulSoup(html, "lxml")

    # 提取标题
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    # 移除不需要的标签
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "iframe", "noscript", "meta", "link"]):
        tag.decompose()

    # 提取正文
    body = soup.find("main") or soup.find("article") or soup.find("body")
    if not body:
        body = soup

    text = body.get_text(separator="\n", strip=True)
    # 清理多余空行
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    content = "\n".join(lines)

    return title, content


def _extract_links(html: str, base_url: str, start_url: str) -> List[str]:
    """从HTML中提取链接，只保留在 start_url 范围内的链接"""
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        full_url = urljoin(base_url, href)
        full_url = _normalize_url(full_url)
        if _is_under_start_url(start_url, full_url) and full_url not in links:
            links.append(full_url)
    return links


async def crawl_single_page(url: str) -> Optional[CrawlResult]:
    """爬取单个网页"""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; KnowledgeBot/1.0)"
            })
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None
            title, content = _extract_text(resp.text)
            if not content:
                return None
            return CrawlResult(url=url, title=title or url, content=content)
    except Exception as e:
        print(f"爬取失败 {url}: {e}")
        return None


async def crawl_website(
    start_url: str,
    max_depth: int = 5,
    max_pages: int = 100,
    progress_callback=None
) -> List[CrawlResult]:
    """
    爬取网站（BFS广度优先），只爬取 start_url 路径范围内的页面，并自动去重。
    :param start_url: 起始URL（只爬取该URL路径前缀下的页面）
    :param max_depth: 最大深度
    :param max_pages: 最多爬取页面数
    :param progress_callback: 进度回调 callback(crawled, total_found)
    """
    start_url = _normalize_url(start_url)
    visited = set()       # 已访问/已入队的URL
    seen_fingerprints = set()  # 内容指纹，用于去重
    results = []
    # 队列：(url, depth)
    queue = [(start_url, 0)]
    visited.add(start_url)

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        while queue and len(results) < max_pages:
            url, depth = queue.pop(0)

            try:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; KnowledgeBot/1.0)"
                })
                if resp.status_code != 200:
                    continue
                content_type = resp.headers.get("content-type", "")
                if "text/html" not in content_type:
                    continue

                title, content = _extract_text(resp.text)
                if content:
                    # 内容去重
                    if not _is_duplicate(content, seen_fingerprints):
                        result = CrawlResult(url=url, title=title or url, content=content, depth=depth)
                        results.append(result)
                        if progress_callback:
                            await progress_callback(len(results), len(visited) + len(queue))
                    else:
                        print(f"跳过重复内容: {url}")

                # 如果还没到最大深度，继续提取链接
                if depth < max_depth:
                    links = _extract_links(resp.text, url, start_url)
                    for link in links:
                        if link not in visited:
                            visited.add(link)
                            queue.append((link, depth + 1))

                # 防止请求太快
                await asyncio.sleep(0.2)

            except Exception as e:
                print(f"爬取失败 {url}: {e}")
                continue

    return results
