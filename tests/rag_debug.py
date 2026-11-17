# rag_debug.py —— 查看实际检索到的上下文，判断是检索问题还是模型问题
from backend.rag.knowledge import retrieve

question = "报销金额超过多少需要审批？"
for i, item in enumerate(retrieve(question, top_k=6), 1):
    print(f"[{i}] {item['file_name']} | 相关度 {item['score']}")
    print("   内容：", item["snippet"])
    print("-" * 60)