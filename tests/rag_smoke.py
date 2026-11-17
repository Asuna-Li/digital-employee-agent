# rag_smoke.py —— 验证本地向量化、持久化与检索
from backend.rag.knowledge import retrieve

tests = [
    ("不过滤", {}),
    ("只看 hr", {"department": "hr"}),
    ("只看 finance", {"department": "finance"}),
    ("只看 public", {"department": "public"}),
]

for label, kwargs in tests:
    print("=" * 20, label)
    results = retrieve("年假有几天？", **kwargs)
    if not results:
        print("  （没有检索到结果）")
    for item in results:
        print(f"  文件：{item['file_name']} | 部门：{item['department']} "
              f"| 相关度：{item['score']}")