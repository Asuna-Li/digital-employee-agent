# inspect_index.py —— 检查索引里实际有哪些文档和元数据
import os
from collections import Counter

from backend.rag.knowledge import build_or_load_index, DOCS_DIR

print("docs 目录里的文件：", os.listdir(DOCS_DIR))

index, storage_context = build_or_load_index() # 解包两个返回值
docstore = storage_context.docstore            # 用返回的 storage_context
nodes = list(docstore.docs.values())

print("索引节点总数：", len(nodes))
print("按文件名统计：", Counter(
    n.metadata.get("file_name", "未知") for n in nodes))
print("元数据字段：", sorted(nodes[0].metadata.keys()) if nodes else "无")
print("示例元数据：", nodes[0].metadata if nodes else "无")