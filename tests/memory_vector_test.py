# memory_vector_test.py —— 验证长期记忆的提炼、写入、检索、隔离
from backend.memory_vectors import (
    add_memory, clear_owner, extract_memories,
    list_memories, search_memory, soft_delete_memory,
)

OWNER_A = "test-owner-a"
OWNER_B = "test-owner-b"

clear_owner(OWNER_A)
clear_owner(OWNER_B)

# 1. 提炼记忆
dialogue = (
    "用户：我叫张三，在技术部，喜欢喝美式咖啡。\n"
    "助手：好的，记住了。"
)
print("=== 提炼结果 ===")
for item in extract_memories(dialogue):
    print(item)

# 2. 写入记忆
pref_id = add_memory("用户喜欢喝美式咖啡", OWNER_A,
                     mtype="preference")
add_memory("用户叫张三", OWNER_A, mtype="fact")
add_memory("用户喜欢喝拿铁", OWNER_B, mtype="preference")

# 3. 检索
print("=== A 的记忆检索 ===")
for m in search_memory("我喜欢喝什么咖啡", OWNER_A):
    print(m["text"], "|", m["type"], "|", m["distance"])

print("=== B 的记忆检索（验证隔离） ===")
for m in search_memory("我喜欢喝什么咖啡", OWNER_B):
    print(m["text"], "|", m["type"])

# 4. 软删除
soft_delete_memory(pref_id)
print("=== 软删除后 A 的检索 ===")
for m in search_memory("我喜欢喝什么咖啡", OWNER_A):
    print(m["text"], "|", m["type"])

print("=== A 的全部记忆（含已过时） ===")
for m in list_memories(OWNER_A):
    print(m["text"], "|", m["type"], "|", m["status"])