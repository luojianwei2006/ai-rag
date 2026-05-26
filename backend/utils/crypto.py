"""
简易加密工具：XOR + base64url
用于客服链接参数加密，方便商户在各个语言中复现。
支持自定义密钥（每个商户独立 embed_api_key），不传则使用默认密钥。
"""
import base64

# 默认固定密钥（与前端旧版本保持一致，向后兼容）
DEFAULT_CRYPTO_KEY = "xhs_kf_2024!@#"


def _xor_process(data_bytes: bytes, key: str) -> bytes:
    """XOR 运算：加密和解密是同一个操作"""
    key_bytes = key.encode("utf-8")
    return bytes([
        b ^ key_bytes[i % len(key_bytes)]
        for i, b in enumerate(data_bytes)
    ])


def xor_encrypt(text: str, key: str = None) -> str:
    """XOR 加密并 base64url 编码"""
    crypto_key = key or DEFAULT_CRYPTO_KEY
    text_bytes = text.encode("utf-8")
    encrypted = _xor_process(text_bytes, crypto_key)
    return base64.urlsafe_b64encode(encrypted).rstrip(b"=").decode("ascii")


def xor_decrypt(token: str, key: str = None) -> str:
    """base64url 解码并 XOR 解密"""
    crypto_key = key or DEFAULT_CRYPTO_KEY
    # 补回 padding
    padding = (4 - len(token) % 4) % 4
    token = token + "=" * padding
    token = token.replace("-", "+").replace("_", "/")
    encrypted = base64.b64decode(token)
    decrypted = _xor_process(encrypted, crypto_key)
    return decrypted.decode("utf-8")


def encrypt_chat_params(uid: str, nickname: str, key: str = None) -> str:
    """加密 uid 和 nickname 为 token 参数"""
    raw = f"uid={uid}&nickname={nickname}"
    return xor_encrypt(raw, key=key)


def decrypt_chat_params(token: str, key: str = None) -> dict:
    """解密 token 参数，返回 uid 和 nickname"""
    raw = xor_decrypt(token, key=key)
    params = {}
    for part in raw.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    return {"uid": params.get("uid", ""), "nickname": params.get("nickname", "")}
