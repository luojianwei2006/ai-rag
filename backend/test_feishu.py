#!/usr/bin/env python3
"""
飞书消息收发本地测试脚本
模拟飞书服务器发送消息，测试处理逻辑
"""

import json
import requests
import time
from datetime import datetime

# 测试配置
BASE_URL = "http://localhost:8000"
TENANT_ID = 1  # 假设商户ID为1

# 模拟飞书消息格式
def create_feishu_message(content: str, msg_type: str = "text") -> dict:
    """创建飞书消息体"""
    return {
        "schema": "2.0",
        "header": {
            "event_id": f"test_{int(time.time() * 1000)}",
            "token": "test_token",
            "create_time": str(int(time.time() * 1000)),
            "event_type": "im.message.receive_v1",
            "tenant_key": "test_tenant",
            "app_id": "test_app_id"
        },
        "event": {
            "message": {
                "message_id": f"om_{int(time.time() * 1000)}",
                "root_id": "",
                "parent_id": "",
                "create_time": str(int(time.time() * 1000)),
                "chat_id": "test_chat_id",
                "chat_type": "p2p",  # 单聊
                "message_type": msg_type,
                "content": json.dumps({"text": content}) if msg_type == "text" else content,
                "mentions": []
            },
            "sender": {
                "sender_id": {
                    "union_id": "test_union_id",
                    "user_id": "test_user_id",
                },
                "sender_type": "user",
                "tenant_key": "test_tenant"
            }
        }
    }


def test_webhook_url():
    """测试 Webhook URL 是否可访问"""
    print("=" * 50)
    print("测试1: 检查 Webhook URL 可访问性")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/feishu/webhook/{TENANT_ID}"
    try:
        # 发送 GET 请求测试（飞书实际用 POST）
        response = requests.get(url, timeout=5)
        print(f"✅ Webhook URL 可访问: {url}")
        print(f"   状态码: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到后端服务")
        print(f"   请确保后端已启动: python3 -m uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"⚠️ 请求异常: {e}")
        return False


def test_text_message():
    """测试普通文本消息"""
    print("\n" + "=" * 50)
    print("测试2: 发送普通文本消息")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/feishu/webhook/{TENANT_ID}"
    message = create_feishu_message("你好，请问怎么使用这个产品？")
    
    try:
        response = requests.post(url, json=message, timeout=10)
        print(f"📤 发送消息: 你好，请问怎么使用这个产品？")
        print(f"📥 响应状态: {response.status_code}")
        print(f"📄 响应内容: {response.text[:200] if response.text else '(空)'}")
        
        if response.status_code == 200:
            print("✅ 消息处理成功")
        else:
            print(f"⚠️ 消息处理返回非200状态码")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_human_handoff():
    """测试转人工消息"""
    print("\n" + "=" * 50)
    print("测试3: 测试转人工消息")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/feishu/webhook/{TENANT_ID}"
    message = create_feishu_message("人工客服")
    
    try:
        response = requests.post(url, json=message, timeout=10)
        print(f"📤 发送消息: 人工客服")
        print(f"📥 响应状态: {response.status_code}")
        print(f"📄 响应内容: {response.text[:200] if response.text else '(空)'}")
        
        if response.status_code == 200:
            print("✅ 转人工处理成功")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_empty_tenant():
    """测试不存在的商户"""
    print("\n" + "=" * 50)
    print("测试4: 测试不存在的商户ID")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/feishu/webhook/99999"
    message = create_feishu_message("测试消息")
    
    try:
        response = requests.post(url, json=message, timeout=10)
        print(f"📤 发送到不存在的商户ID: 99999")
        print(f"📥 响应状态: {response.status_code}")
        
        if response.status_code == 404:
            print("✅ 正确返回404，商户不存在")
        else:
            print(f"⚠️ 预期返回404，实际返回 {response.status_code}")
        return response.status_code == 404
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_challenge_request():
    """测试飞书 URL 验证（挑战请求）"""
    print("\n" + "=" * 50)
    print("测试5: 测试飞书 URL 验证（挑战请求）")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/feishu/webhook/{TENANT_ID}"
    challenge_data = {
        "challenge": "test_challenge_token_123",
        "token": "test_token",
        "type": "url_verification"
    }
    
    try:
        response = requests.post(url, json=challenge_data, timeout=10)
        print(f"📤 发送挑战请求")
        print(f"📥 响应状态: {response.status_code}")
        print(f"📄 响应内容: {response.text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("challenge") == "test_challenge_token_123":
                    print("✅ URL 验证成功，返回正确的 challenge")
                    return True
                else:
                    print("⚠️ 返回的 challenge 不匹配")
                    return False
            except:
                print("⚠️ 响应不是有效的JSON")
                return False
        else:
            print(f"⚠️ 预期返回200，实际返回 {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "🚀 " * 25)
    print("飞书消息收发本地测试")
    print("🚀 " * 25 + "\n")
    
    # 检查服务是否启动
    if not test_webhook_url():
        print("\n❌ 后端服务未启动，请先启动服务:")
        print("   cd /Users/luojianwei/WorkBuddy/20260411104248/customer-service-platform/backend")
        print("   python3 -m uvicorn main:app --reload")
        return
    
    # 运行其他测试
    results = []
    results.append(("挑战请求", test_challenge_request()))
    results.append(("普通消息", test_text_message()))
    results.append(("转人工", test_human_handoff()))
    results.append(("不存在商户", test_empty_tenant()))
    
    # 打印测试总结
    print("\n" + "=" * 50)
    print("测试结果总结")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！飞书消息收发功能正常。")
    else:
        print("\n⚠️ 部分测试失败，请检查日志和配置。")


if __name__ == "__main__":
    run_all_tests()
