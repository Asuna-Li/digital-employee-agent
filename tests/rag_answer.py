# rag_answer.py —— 验证“检索 + 本地大模型生成”
from backend.rag.knowledge import answer

question = "公司食堂几点开门？"
result = answer(question)

print("问题：", question)
print("-" * 60)
print("回答：")
print(result["answer"])
print("-" * 60)
print("引用来源：")
for i, item in enumerate(result["citations"], 1):
    print(f"[{i}] {item['file_name']} | 部门：{item['department']} "
          f"| 第{item['page']}页 | 相关度：{item['score']}")