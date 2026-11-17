# desensitize_test.py —— 验证本地脱敏
from backend.privacy.desensitizer import (
    desensitize, has_residual, restore,
)

samples = [
    "把张三的电话13800138000发给张三丰，金额8000元，工号A12345",
    "请把报销制度发给李四，邮箱lisi@example.com",
    "合同号HT-2026-001的金额是12000 元，卡号6222123456789012",
]

for text in samples:
    sanitized, mapping = desensitize(text)
    print("原文：", text)
    print("脱敏：", sanitized)
    print("映射：", mapping)
    print("有残留：", has_residual(sanitized))
    print("还原：", restore(sanitized, mapping))
    print("-" * 60)