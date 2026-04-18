import json
from typing import Optional, List
from sqlalchemy.orm import Session
from models.models import SystemConfig, Tenant


def get_system_api_keys(db: Session) -> dict:
    """获取系统默认API Keys，支持新格式v2"""
    # 优先查询新格式 api_keys_v2
    v2_config = db.query(SystemConfig).filter(SystemConfig.key == "api_keys_v2").first()
    if v2_config and v2_config.value:
        try:
            import json
            keys_list = json.loads(v2_config.value)
            # 构建 model -> api_key 的映射
            result = {}
            for item in keys_list:
                if item.get("enabled") and item.get("api_key"):
                    model = item.get("model")
                    if model:
                        result[model] = item.get("api_key")
            return result
        except Exception:
            pass  # 解析失败，回退到旧格式
    
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
    
    # 前缀匹配：例如 model="glm" 匹配 "glm-4-flash"
    for key_model, api_key in system_keys.items():
        if key_model.startswith(model) or model.startswith(key_model.split('-')[0]):
            return api_key
    
    # 厂家匹配：例如 model="glm-4-flash"，查找glm开头的任何key
    provider = model.split('-')[0] if '-' in model else model
    for key_model, api_key in system_keys.items():
        if key_model.startswith(provider):
            return api_key
    
    return None


async def call_llm(
    model: str,
    api_keys: list,
    messages: List[dict],
    context: str = ""
) -> str:
    """调用大模型接口，支持轮询多个API Key
    
    api_keys: [(model_name, api_key), ...] 轮询列表
    """
    if not api_keys:
        return "错误：未配置API Key"

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

    # 优先使用与preferred_model匹配的Key
    errors = []
    
    # 第一轮：尝试匹配的模型
    for m, key in api_keys:
        if m == model or m.startswith(model) or model.startswith(m.split('-')[0] if '-' in m else m):
            result = await _call_llm_with_model(m, key, messages, system_prompt)
            if not result.startswith("调用失败") and not result.startswith("GLM调用失败") and not result.startswith("OpenAI调用失败") and not result.startswith("Gemini调用失败"):
                return result
            errors.append(f"{m}: {result}")
    
    # 第二轮：尝试所有可用的Key
    for m, key in api_keys:
        result = await _call_llm_with_model(m, key, messages, system_prompt)
        if not result.startswith("调用失败") and not result.startswith("GLM调用失败") and not result.startswith("OpenAI调用失败") and not result.startswith("Gemini调用失败"):
            return result
        errors.append(f"{m}: {result}")
    
    return f"所有API Key调用失败: {'; '.join(errors[:3])}"


async def _call_llm_with_model(model: str, api_key: str, messages: List[dict], system_prompt: str) -> str:
    """根据模型类型调用对应的API"""
    # 判断模型类型
    if "nvidia" in model.lower() or "z-ai" in model.lower():
        return await _call_nvidia_zai(model, api_key, messages, system_prompt)
    elif "glm" in model.lower():
        return await _call_glm(api_key, messages, system_prompt)
    elif "gpt" in model.lower() or "openai" in model.lower():
        return await _call_openai(api_key, messages, system_prompt)
    elif "gemini" in model.lower():
        return await _call_gemini(api_key, messages, system_prompt)
    else:
        # 默认使用GLM
        return await _call_glm(api_key, messages, system_prompt)


async def _call_glm(api_key: str, messages: List[dict], system_prompt: str) -> str:
    """调用智谱GLM"""
    try:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=api_key)
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=all_messages
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"GLM调用失败: {str(e)}"


async def _call_openai(api_key: str, messages: List[dict], system_prompt: str) -> str:
    """调用OpenAI ChatGPT"""
    try:
        import httpx
        import json
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": all_messages,
            "max_tokens": 1000
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenAI调用失败: {str(e)}"


async def _call_gemini(api_key: str, messages: List[dict], system_prompt: str) -> str:
    """调用Google Gemini"""
    try:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        # 转换消息格式
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]}
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Gemini调用失败: {str(e)}"


async def _call_nvidia_zai(model: str, api_key: str, messages: List[dict], system_prompt: str) -> str:
    """调用NVIDIA Z-AI API"""
    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        payload = {
            "model": model,
            "messages": all_messages,
            "max_tokens": 1000
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            data = resp.json()
            # 调试：打印响应结构
            print(f"NVIDIA Z-AI response: {data}")
            # 检查响应结构
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice:
                    msg = choice["message"]
                    # 优先返回 content，如果没有则返回 reasoning_content
                    if "content" in msg and msg["content"]:
                        return msg["content"]
                    elif "reasoning_content" in msg and msg["reasoning_content"]:
                        return msg["reasoning_content"]
                    else:
                        return f"NVIDIA Z-AI调用失败: 消息为空: {msg}"
                elif "text" in choice:
                    return choice["text"]
                else:
                    return f"NVIDIA Z-AI调用失败: 未知的响应格式: {choice}"
            elif "error" in data:
                return f"NVIDIA Z-AI调用失败: {data['error']}"
            else:
                return f"NVIDIA Z-AI调用失败: 未知响应: {data}"
    except Exception as e:
        return f"NVIDIA Z-AI调用失败: {str(e)}"


def _get_api_key_from_v2_list(custom_keys: dict, model: str) -> Optional[str]:
    """从新格式v2的api_keys_list中获取对应模型的API Key"""
    v2_list = custom_keys.get("__v2__", [])
    if not v2_list:
        return None
    
    # 找到启用的、匹配模型的Key
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
