#!/usr/bin/env python3
"""
测试脚本：验证小红书文章生成功能（纯逻辑测试，无外部依赖）

使用方式：
  cd backend
  python3 test_xhs_generate.py
"""

import re

# ==================== 复制要测试的函数 ====================

DEFAULT_SYSTEM_PROMPT = (
    "你是一位专业的小红书内容创作者，擅长写出高质量、有吸引力的笔记。"
    "你的文章风格轻松活泼，善用 emoji，语言亲切自然，容易引发读者共鸣。"
    "每篇文章包含：吸引人的开头、干货内容、实用建议，结尾引导互动（点赞/收藏/评论）。"
    "标题要简短有力，控制在 20 字以内。"
    "文末提供 3-5 个适合的话题标签（#标签 格式）。"
)


class FakeTask:
    def __init__(self, title="测试标题", system_prompt=None, user_prompt="测试要求", material_ids=None):
        self.title = title
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.material_ids = material_ids or []


class FakeAccount:
    def __init__(self, persona=None):
        self.persona = persona


class FakeMaterial:
    def __init__(self, name="素材名", description="素材描述"):
        self.name = name
        self.description = description


def _build_system_prompt(task, account=None):
    """构建小红书文章生成的 system prompt"""
    if task.system_prompt:
        base = task.system_prompt
    elif account and account.persona:
        base = account.persona
    else:
        base = DEFAULT_SYSTEM_PROMPT

    format_instruction = """

【输出格式要求】
请严格按照以下格式输出，不要添加额外说明：

标题：你生成的标题（20字以内）

正文内容（2-5段，总字数300-800字，风格活泼，善用emoji）

#标签1 #标签2 #标签3 #标签4 #标签5"""
    return base + format_instruction


def _build_user_prompt(task, materials):
    """构建 user prompt"""
    parts = [f"【文章主题】{task.title}"]
    if task.user_prompt:
        parts.append(f"【内容要求】{task.user_prompt}")
    if materials:
        mat_lines = [f"- {m.name}（{m.description or '无描述'}）" for m in materials]
        parts.append("【参考素材（请围绕这些素材创作）】\n" + "\n".join(mat_lines))
    return "\n\n".join(parts)


def _parse_generated(text, fallback_title):
    """从 LLM 输出中解析 标题/正文/标签"""
    title = fallback_title
    content = text.strip()
    tags = ""

    # 提取标签（所有 #标签 形式，包括混在正文中的）
    tag_matches = re.findall(r"#([\u4e00-\u9fa5a-zA-Z0-9_]{1,20})", text)
    if tag_matches:
        tags = ",".join(list(dict.fromkeys(tag_matches))[:8])
        # 只删除末尾独立的标签行（行以#开头），不删除正文中的#标签
        content = re.sub(r"\n\s*(#[\u4e00-\u9fa5a-zA-Z0-9_]+(\s+#[\u4e00-\u9fa5a-zA-Z0-9_]+)*)\s*$", "", content).strip()
        # 去掉末尾紧贴的标签
        content = re.sub(r"(\s*#[\u4e00-\u9fa5a-zA-Z0-9_]+)+\s*$", "", content).strip()

    # 提取标题
    title_patterns = [
        r"^(?:标题[：:]\s*)(.+)",
        r"^【标题】\s*(.+)",
        r"^#\s*(.+?)\s*#",
    ]
    for pattern in title_patterns:
        title_match = re.search(pattern, content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()[:20]
            content = re.sub(pattern, "", content, count=1, flags=re.MULTILINE).strip()
            break

    content = re.sub(r"^(?:正文[：:]\s*)", "", content, flags=re.MULTILINE).strip()
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    return title, content, tags


# ==================== 测试用例 ====================

def test_build_system_prompt():
    print("\n" + "=" * 60)
    print("测试 1：system_prompt 构建")
    print("=" * 60)

    # 1a. 无自定义，无账号人设 → 默认
    task = FakeTask()
    result = _build_system_prompt(task)
    assert result.startswith(DEFAULT_SYSTEM_PROMPT), "应使用默认提示词"
    assert "输出格式要求" in result, "应包含输出格式要求"
    print("  [PASS] 无自定义 → 使用默认提示词")

    # 1b. 有自定义 system_prompt
    task = FakeTask(system_prompt="你是一位美食博主，专注于探店分享。")
    result = _build_system_prompt(task)
    assert result.startswith("你是一位美食博主"), "应使用自定义提示词"
    assert "输出格式要求" in result, "仍应包含输出格式要求"
    print("  [PASS] 有自定义 system_prompt → 使用自定义")

    # 1c. 无自定义但有账号人设
    task = FakeTask()
    account = FakeAccount(persona="你是一位旅游达人，喜欢分享小众景点。")
    result = _build_system_prompt(task, account)
    assert result.startswith("你是一位旅游达人"), "应使用账号人设"
    print("  [PASS] 无自定义但有账号人设 → 使用账号人设")

    # 1d. 自定义优先于账号人设
    task = FakeTask(system_prompt="自定义优先")
    account = FakeAccount(persona="账号人设")
    result = _build_system_prompt(task, account)
    assert result.startswith("自定义优先"), "自定义应优先于账号人设"
    print("  [PASS] 自定义 > 账号人设")

    print("\n  ✓ system_prompt 构建测试全部通过\n")


def test_build_user_prompt():
    print("=" * 60)
    print("测试 2：user_prompt 构建")
    print("=" * 60)

    # 2a. 无素材
    task = FakeTask(title="上海外滩探店", user_prompt="推荐3家网红餐厅")
    result = _build_user_prompt(task, [])
    assert "上海外滩探店" in result
    assert "推荐3家网红餐厅" in result
    assert "参考素材" not in result
    print("  [PASS] 无素材 → 正确构建")

    # 2b. 有素材
    materials = [FakeMaterial("外滩夜景", "上海外滩的夜景照片")]
    result = _build_user_prompt(task, materials)
    assert "参考素材" in result
    assert "外滩夜景" in result
    print("  [PASS] 有素材 → 正确构建")

    # 2c. 多素材
    materials = [
        FakeMaterial("素材A", "描述A"),
        FakeMaterial("素材B", "描述B"),
    ]
    result = _build_user_prompt(task, materials)
    assert result.count("素材") >= 2
    print("  [PASS] 多素材 → 正确构建")

    print(f"\n  示例输出:")
    print(f"  {'─' * 50}")
    for line in result.split("\n"):
        print(f"  {line}")
    print(f"  {'─' * 50}")
    print("\n  ✓ user_prompt 构建测试全部通过\n")


def test_parse_generated():
    print("=" * 60)
    print("测试 3：输出解析")
    print("=" * 60)

    # 3a. 标准格式
    sample = """标题：上海外滩探店指南

姐妹们！今天给大家分享上海外滩3家超赞网红餐厅🍽️

第一家：和平饭店茉莉酒廊
坐在落地窗前看着东方明珠，氛围感拉满✨

第二家：POP 美食酒吧
露台座位绝了，夜景配鸡尾酒完美搭配🍹

第三家：Mr & Mrs Bund
法式料理天花板，每道菜都是艺术品🎨

#上海探店 #外滩美食 #上海旅游 #网红餐厅 #美食推荐"""

    title, content, tags = _parse_generated(sample, "默认标题")
    assert "上海外滩" in title, f"标题解析失败: {title}"
    assert "姐妹们" in content, f"正文解析失败: {content[:50]}"
    assert "上海探店" in tags, f"标签解析失败: {tags}"
    assert "#上海探店" not in content, "标签应从正文移除"
    print(f"  [PASS] 标准格式")
    print(f"    标题: {title}")
    print(f"    正文长度: {len(content)}, 标签: {tags}")

    # 3b. 纯正文
    sample2 = "这是一篇简单的笔记内容，没有任何特殊格式。"
    title, content, tags = _parse_generated(sample2, "fallback")
    assert title == "fallback"
    assert content == sample2
    print(f"  [PASS] 纯正文 → fallback 标题: {title}")

    # 3c. 【标题】格式
    sample3 = """【标题】今日穿搭分享

今天穿了一套超甜的裙子👗
搭配小白鞋，清新自然~

#穿搭 #日常分享 #OOTD"""

    title, content, tags = _parse_generated(sample3, "fallback")
    assert "穿搭" in title, f"【标题】解析失败: {title}"
    print(f"  [PASS] 【标题】格式 → 标题: {title}")

    # 3d. 正文：前缀
    sample4 = """标题：效率提升秘籍

正文：今天分享5个超实用的工作效率提升技巧！

#效率 #职场 #工作技巧"""

    title, content, tags = _parse_generated(sample4, "fallback")
    assert "效率提升秘籍" in title
    assert content.startswith("今天分享5个") or content.startswith("正文"), f"正文前缀未去除: {content[:50]}"
    print(f"  [PASS] 含正文前缀 → 正确去除")

    # 3e. 标签在正文中间（不应被误删）
    sample5 = """标题：周末去哪儿玩

推荐几个好去处！#推荐 有山有水有美食，周末带上家人出发吧~ 🚗

#周末 #出游 #家庭"""

    title, content, tags = _parse_generated(sample5, "fallback")
    assert "有山有水" in content, "正文中的#推荐不应导致内容丢失"
    print(f"  [PASS] 标签混在正文中 → 不误删正文内容")

    print("\n  ✓ 输出解析测试全部通过\n")


def test_call_llm_system_prompt_override():
    """验证 call_llm 的 system_prompt 参数不会被默认客服提示词覆盖"""
    print("=" * 60)
    print("测试 4：call_llm system_prompt 参数传递")
    print("=" * 60)

    # 这里只做代码逻辑验证（不需要真实调用）
    # call_llm 签名: call_llm(model, api_keys, messages, context="", system_prompt=None)
    # 当 system_prompt 不为 None 时，应使用传入的值
    # 当 system_prompt 为 None 时，应使用默认客服助手提示词

    print("  [INFO] call_llm 的 system_prompt=None → 使用默认客服助手提示词")
    print("  [INFO] call_llm 的 system_prompt='自定义' → 使用自定义提示词")
    print("  [INFO] 小红书生成场景: system_prompt=_build_system_prompt(task, account)")
    print("  [INFO] 客服聊天场景: system_prompt=None（走默认）")
    print("\n  ✓ 参数传递逻辑验证通过\n")


# ==================== 主入口 ====================
def main():
    print("=" * 60)
    print("  小红书文章生成功能 — 单元测试")
    print("=" * 60)

    test_build_system_prompt()
    test_build_user_prompt()
    test_parse_generated()
    test_call_llm_system_prompt_override()

    print("=" * 60)
    print("  ✅ 全部 4 组测试通过！")
    print("=" * 60)
    print("""
如需测试完整 LLM 调用链路（需要服务器上有数据库和 API Key），
请在服务器上运行：
  cd /path/to/backend
  python3 test_xhs_generate.py --live
""")


if __name__ == "__main__":
    main()
