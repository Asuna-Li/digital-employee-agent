# cloud_llm_test.py —— 验证云端通用问答与脱敏
from backend.llm.cloud_llm import cloud_answer

samples = [
    "用一句话解释什么是向量数据库？",
    "把张三的电话13800138000发给李四，这个流程应该注意什么？",
]

for q in samples:
    print("原问题：", q)
    result = cloud_answer(q)
    print("实际出网（脱敏后）：", result["sanitized"])
    print("回答：", result["answer"])
    print("引用：", result["citations"])
    print("-" * 70)