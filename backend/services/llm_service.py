"""
LLM 调用服务

支持厂商：OpenAI / 兼容接口（DeepSeek、通义千问等）、智谱 GLM、Google Gemini、NVIDIA

核心改进：
- 统一异常体系（LLMError），调用方可据此判断是否扣积分
- 自动重试（3次，指数退避），覆盖超时 / 429 / 500 / 503
- 使用传入的 model 参数，不再硬编码模型名
- GLM SDK 改用 asyncio.to_thread 避免阻塞事件循环
- logging 替代 print
- 超时区分连接(10s)与读取(60s)
"""

import asyncio
import json
import logging
import time
from typing import Optional, List

import httpx
from sqlalchemy.orm import Session

from models.models import SystemConfig, Tenant

logger = logging.getLogger("llm_service")

# ─── 超时配置 ───────────────────────────────────────────────
CONNECT_TIMEOUT = 10.0  # 连接超时 10s
READ_TIMEOUT = 60.0     # 读取超时 60s（模型推理可能较慢）

# ─── 重试配置 ───────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # 指数退避基数：2s, 4s, 8s

# ─── 厂商路由表 ─────────────────────────────────────────────
# key: 厂商标识（小写），value: (API base URL, 认证头名前缀)
# OpenAI 兼容接口（DeepSeek、通义千问、Groq、Moonshot 等）共享同一路由
_OPENAI_COMPATIBLE_PROVIDERS = {
    "deepseek": "https://api.deepseek.com/v1",
    "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "chatglm":  "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
    "groq":     "https://api.groq.com/openai/v1",
    "yi":       "https://api.lingyiwanwu.com/v1",
    "baichuan": "https://api.baichuan-ai.com/v1",
    "minimax":  "https://api.minimax.chat/v1",
    "stepfun":  "https://api.stepfun.com/v1",
    "01ai":     "https://api.lingyiwanwu.com/v1",
}

_GLM_NATIVE_MODELS = {"glm"}  # 使用智谱原生 SDK 的模型前缀

_NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


# ─── 异常 ───────────────────────────────────────────────────

class LLMError(Exception):
    """所有 LLM 调用错误的基类"""
    def __init__(self, message: str, provider: str = "", model: str = "", retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.retryable = retryable


class LLMTimeoutError(LLMError):
    def __init__(self, provider: str = "", model: str = ""):
        super().__init__(f"请求超时", provider=provider, model=model, retryable=True)


class LLMRateLimitError(LLMError):
    def __init__(self, provider: str = "", model: str = ""):
        super().__init__(f"请求频率受限(429)", provider=provider, model=model, retryable=True)


class LLMServerError(LLMError):
    def __init__(self, status_code: int, body: str, provider: str = "", model: str = ""):
        super().__init__(f"服务端错误({status_code}): {body}", provider=provider, model=model, retryable=True)


class LLMAuthError(LLMError):
    def __init__(self, provider: str = "", model: str = ""):
        super().__init__(f"认证失败，请检查 API Key", provider=provider, model=model, retryable=False)


class LLMResponseError(LLMError):
    """响应解析失败"""
    def __init__(self, message: str, provider: str = "", model: str = ""):
        super().__init__(message, provider=provider, model=model, retryable=False)


# ─── 辅助：根据 model 名识别厂商 ────────────────────────────

def _detect_provider(model: str) -> str:
    """根据模型名称自动识别厂商，返回厂商 key"""
    m = model.lower()
    # GLM 优先（因为 "chatglm" 也包含 "glm"）
    if m.startswith("glm-") or m == "glm":
        return "glm"
    # NVIDIA Z-AI
    if "nvidia" in m or "z-ai" in m:
        return "nvidia"
    # Gemini
    if "gemini" in m:
        return "gemini"
    # OpenAI 兼容厂商（按长度倒序匹配，避免 "qwen" 被 "deepseek-qwen" 误匹配）
    for prefix in sorted(_OPENAI_COMPATIBLE_PROVIDERS.keys(), key=len, reverse=True):
        if prefix in m or m.startswith(prefix):
            return prefix
    # GPT 系列走 OpenAI
    if "gpt" in m or "openai" in m:
        return "openai"
    # 兜底：当作 OpenAI 兼容（大多数国产模型都兼容 OpenAI 格式）
    return "unknown_openai_compat"


def _get_api_base(model: str, provider: str) -> str:
    """获取 API base URL"""
    if provider == "openai":
        return "https://api.openai.com/v1"
    if provider == "nvidia":
        return _NVIDIA_API_BASE
    if provider in _OPENAI_COMPATIBLE_PROVIDERS:
        return _OPENAI_COMPATIBLE_PROVIDERS[provider]
    # 未知厂商兜底走 OpenAI 格式
    return "https://api.openai.com/v1"


# ─── 重试装饰器 ─────────────────────────────────────────────

async def _retry_async(coro_func, provider: str = "", model: str = "", label: str = ""):
    """带指数退避的异步重试"""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await coro_func()
        except LLMError as e:
            last_error = e
            if not e.retryable or attempt == MAX_RETRIES:
                raise
            wait = RETRY_BACKOFF_BASE ** attempt
            logger.warning(
                "[%s] 第%d次调用失败（%s），%ds后重试... model=%s",
                label, attempt, e, wait, model
            )
            await asyncio.sleep(wait)
        except Exception as e:
            last_error = e
            import traceback
            wait = RETRY_BACKOFF_BASE ** attempt
            # 增强日志：打印异常类型、状态码、响应体
            error_detail = f"{type(e).__name__}: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail += f" | status={e.response.status_code} body={e.response.text[:500]}"
                except Exception:
                    pass
            logger.warning(
                "[%s] 第%d次调用遇到未知错误（%s），%ds后重试... model=%s\n%s",
                label, attempt, error_detail, wait, model, traceback.format_exc()
            )
            if attempt == MAX_RETRIES:
                raise LLMError(
                    f"未知错误: {error_detail}", provider=provider, model=model, retryable=False
                )
            await asyncio.sleep(wait)
    raise last_error  # 理论上不会到这里


# ─── OpenAI 兼容格式调用 ────────────────────────────────────

async def _call_openai_compatible(
    api_base: str, model: str, api_key: str, messages: list, system_prompt: str
) -> str:
    """调用 OpenAI 兼容格式的 API（覆盖 DeepSeek、通义千问、Moonshot 等）"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    all_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "model": model,
        "messages": all_messages,
        "max_tokens": 2000,
        "temperature": 0.7,
    }

    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT, write=10.0, pool=10.0)

    async def _do_call():
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            # 处理 HTTP 错误
            if resp.status_code == 401 or resp.status_code == 403:
                raise LLMAuthError(provider=api_base, model=model)
            if resp.status_code == 429:
                raise LLMRateLimitError(provider=api_base, model=model)
            if resp.status_code >= 500:
                raise LLMServerError(
                    resp.status_code, resp.text[:200], provider=api_base, model=model
                )
            resp.raise_for_status()
            data = resp.json()

            # 解析响应
            if "error" in data:
                err = data["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                raise LLMResponseError(f"API返回错误: {msg}", provider=api_base, model=model)

            if "choices" not in data or not data["choices"]:
                raise LLMResponseError(f"响应无choices字段: {json.dumps(data, ensure_ascii=False)[:300]}", provider=api_base, model=model)

            choice = data["choices"][0]
            # 优先返回 content，无 content 则尝试 reasoning_content（DeepSeek R1 等）
            msg = choice.get("message", {})
            content = msg.get("content")
            if content:
                return content
            reasoning = msg.get("reasoning_content")
            if reasoning:
                return reasoning
            raise LLMResponseError(f"响应消息为空: {json.dumps(msg, ensure_ascii=False)[:300]}", provider=api_base, model=model)

    return await _retry_async(_do_call, provider=api_base, model=model, label="OpenAI兼容")


# ─── GLM 原生 SDK 调用 ─────────────────────────────────────

def _call_glm_sync(model: str, api_key: str, messages: list, system_prompt: str) -> str:
    """同步调用 GLM（在线程中执行，避免阻塞事件循环）"""
    from zhipuai import ZhipuAI
    client = ZhipuAI(api_key=api_key)
    all_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=all_messages,
        timeout=60,
    )
    if not response.choices:
        raise LLMResponseError("GLM响应无choices", provider="glm", model=model)
    content = response.choices[0].message.content
    if not content:
        raise LLMResponseError("GLM响应内容为空", provider="glm", model=model)
    return content


async def _call_glm(model: str, api_key: str, messages: list, system_prompt: str) -> str:
    """异步调用 GLM（通过线程池避免阻塞）"""
    provider = "glm"

    def _do_call():
        try:
            return _call_glm_sync(model, api_key, messages, system_prompt)
        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "Unauthorized" in err_msg or "auth" in err_msg.lower():
                raise LLMAuthError(provider=provider, model=model)
            if "429" in err_msg or "rate" in err_msg.lower():
                raise LLMRateLimitError(provider=provider, model=model)
            if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
                raise LLMTimeoutError(provider=provider, model=model)
            raise LLMError(err_msg, provider=provider, model=model, retryable=True)

    return await _retry_async(
        lambda: asyncio.to_thread(_do_call),
        provider=provider, model=model, label="GLM"
    )


# ─── Gemini 调用 ───────────────────────────────────────────

async def _call_gemini(model: str, api_key: str, messages: list, system_prompt: str) -> str:
    """调用 Google Gemini"""
    provider = "gemini"
    url = f"{_GEMINI_API_BASE}/{model}:generateContent?key={api_key}"

    # 转换消息格式
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }
    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT, write=10.0, pool=10.0)

    async def _do_call():
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 400:
                raise LLMAuthError(provider=provider, model=model)
            if resp.status_code == 429:
                raise LLMRateLimitError(provider=provider, model=model)
            if resp.status_code >= 500:
                raise LLMServerError(resp.status_code, resp.text[:200], provider=provider, model=model)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                raise LLMResponseError(f"Gemini错误: {data['error']}", provider=provider, model=model)

            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMResponseError(f"Gemini响应无candidates: {json.dumps(data, ensure_ascii=False)[:300]}", provider=provider, model=model)

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise LLMResponseError("Gemini响应parts为空", provider=provider, model=model)

            text = parts[0].get("text", "")
            if not text:
                raise LLMResponseError("Gemini响应文本为空", provider=provider, model=model)
            return text

    return await _retry_async(_do_call, provider=provider, model=model, label="Gemini")


# ─── NVIDIA 调用 ────────────────────────────────────────────

async def _call_nvidia(model: str, api_key: str, messages: list, system_prompt: str) -> str:
    """调用 NVIDIA Z-AI API（OpenAI 兼容格式）"""
    return await _call_openai_compatible(
        _NVIDIA_API_BASE, model, api_key, messages, system_prompt
    )


# ─── 厂商路由调度 ───────────────────────────────────────────

async def _dispatch_call(model: str, api_key: str, messages: list, system_prompt: str) -> str:
    """根据模型名自动路由到对应的调用函数"""
    provider = _detect_provider(model)
    logger.info("模型路由: model=%s -> provider=%s", model, provider)

    if provider == "glm":
        return await _call_glm(model, api_key, messages, system_prompt)
    elif provider == "gemini":
        return await _call_gemini(model, api_key, messages, system_prompt)
    elif provider == "nvidia":
        return await _call_nvidia(model, api_key, messages, system_prompt)
    else:
        # OpenAI 及所有兼容厂商
        api_base = _get_api_base(model, provider)
        return await _call_openai_compatible(api_base, model, api_key, messages, system_prompt)


# ─── 公开接口 ───────────────────────────────────────────────

async def call_llm(
    model: str,
    api_keys: list,
    messages: List[dict],
    context: str = ""
) -> str:
    """调用大模型接口，支持轮询多个 API Key

    Args:
        model: 首选模型名
        api_keys: [(model_name, api_key), ...] 轮询列表
        messages: 对话历史 [{"role": "user", "content": "..."}, ...]
        context: 知识库上下文

    Returns:
        LLM 回复文本

    Raises:
        LLMError: 所有 Key 都失败时抛出最后一个错误
    """
    if not api_keys:
        raise LLMError("未配置 API Key", model=model)

    # 构建系统提示
    system_prompt = (
        "你是一个专业的客服助手。回答要求：\n"
        "1. 简洁直接，只回答用户问题的核心内容；\n"
        "2. 不展开无关信息，不做额外解释或补充；\n"
        "3. 如果知识库中有相关内容，依据知识库作答；\n"
        "4. 如果知识库中没有相关信息，直接告知无法找到，不要编造。"
    )
    if context:
        system_prompt += f"\n\n知识库参考内容：\n{context}"

    errors = []

    # 第一轮：尝试与 preferred_model 匹配的 Key
    for m, key in api_keys:
        if m == model or m.startswith(model) or model.startswith(m.split('-')[0] if '-' in m else m):
            try:
                start = time.time()
                result = await _dispatch_call(m, key, messages, system_prompt)
                elapsed = time.time() - start
                logger.info("LLM调用成功: model=%s, 耗时=%.1fs, 回复长度=%d", m, elapsed, len(result))
                return result
            except LLMError as e:
                logger.warning("LLM调用失败: model=%s, provider=%s, error=%s", m, e.provider, e)
                errors.append(f"{m}({e.provider}): {e}")
            except Exception as e:
                logger.error("LLM未知错误: model=%s, error=%s", m, e, exc_info=True)
                errors.append(f"{m}: {e}")

    # 第二轮：尝试所有剩余的 Key
    for m, key in api_keys:
        if m == model or m.startswith(model) or model.startswith(m.split('-')[0] if '-' in m else m):
            continue  # 已经试过了
        try:
            start = time.time()
            result = await _dispatch_call(m, key, messages, system_prompt)
            elapsed = time.time() - start
            logger.info("LLM调用成功(备用Key): model=%s, 耗时=%.1fs, 回复长度=%d", m, elapsed, len(result))
            return result
        except LLMError as e:
            logger.warning("LLM备用Key失败: model=%s, provider=%s, error=%s", m, e.provider, e)
            errors.append(f"{m}({e.provider}): {e}")
        except Exception as e:
            logger.error("LLM备用Key未知错误: model=%s, error=%s", m, e, exc_info=True)
            errors.append(f"{m}: {e}")

    # 全部失败
    error_summary = "; ".join(errors[:5])
    logger.error("所有API Key调用失败: model=%s, errors=%s", model, error_summary)
    raise LLMError(f"所有 API Key 调用失败: {error_summary}", model=model)


# ─── 商户配置获取（保持原有接口不变）───────────────────────

def get_system_api_keys(db: Session) -> dict:
    """获取系统默认API Keys，支持新格式v2"""
    # 优先查询新格式 api_keys_v2
    v2_config = db.query(SystemConfig).filter(SystemConfig.key == "api_keys_v2").first()
    if v2_config and v2_config.value:
        try:
            keys_list = json.loads(v2_config.value)
            result = {}
            for item in keys_list:
                if item.get("enabled") and item.get("api_key"):
                    model = item.get("model")
                    if model:
                        result[model] = item.get("api_key")
            return result
        except Exception as e:
            logger.warning("解析 api_keys_v2 失败: %s", e)

    # 回退到旧格式
    configs = db.query(SystemConfig).filter(
        SystemConfig.key.in_(["api_key_glm", "api_key_openai", "api_key_gemini"])
    ).all()
    return {c.key.replace("api_key_", ""): c.value for c in configs if c.value}


def _find_api_key_for_model(system_keys: dict, model: str) -> Optional[str]:
    """根据模型名称查找匹配的API Key，支持前缀匹配"""
    if not system_keys:
        return None

    # 精确匹配
    if model in system_keys:
        return system_keys[model]

    # 前缀匹配
    for key_model, api_key in system_keys.items():
        if key_model.startswith(model) or model.startswith(key_model.split('-')[0]):
            return api_key

    # 厂家匹配
    provider = model.split('-')[0] if '-' in model else model
    for key_model, api_key in system_keys.items():
        if key_model.startswith(provider):
            return api_key

    return None


def _get_api_key_from_v2_list(custom_keys: dict, model: str) -> Optional[str]:
    """从新格式v2的api_keys_list中获取对应模型的API Key"""
    v2_list = custom_keys.get("__v2__", [])
    if not v2_list:
        return None

    for item in v2_list:
        if item.get("enabled") and item.get("model") == model:
            return item.get("api_key")
    return None


def get_tenant_llm_config(tenant: Tenant, db: Session) -> tuple[str, list]:
    """获取商户的模型和API Key配置，返回 (model, api_keys_list)

    api_keys_list 是 [(model_name, api_key), ...] 格式的列表，用于轮询
    """
    preferred_model = tenant.preferred_model or "glm"
    api_keys_list = []

    custom_keys = tenant.custom_api_keys or {}

    # 优先尝试商户自定义Key（新格式v2）
    v2_list = custom_keys.get("__v2__", [])
    for item in v2_list:
        if item.get("enabled") and item.get("api_key"):
            api_keys_list.append((item.get("model"), item.get("api_key")))

    # 新格式没有，尝试旧格式
    if not api_keys_list:
        for model, key in custom_keys.items():
            if model != "__v2__" and key:
                api_keys_list.append((model, key))

    # 商户选择使用系统Key，或自定义Key不存在
    if tenant.use_system_api_key or not api_keys_list:
        system_keys = get_system_api_keys(db)
        for model, key in system_keys.items():
            api_keys_list.append((model, key))

    # 去重，优先使用自定义Key
    seen = set()
    unique_list = []
    for model, key in api_keys_list:
        if key and key not in seen:
            seen.add(key)
            unique_list.append((model, key))

    return preferred_model, unique_list
