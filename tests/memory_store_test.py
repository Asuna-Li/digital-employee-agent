# memory_store_test.py —— 验证短期会话记忆
from backend.memory_store import (
    append_message, clear_session, get_recent_messages,
)

SESSION = "test-session"
CLOUD = "test-cloud"

clear_session(SESSION)
clear_session(CLOUD)

# 本地会话：应该落盘
append_message(SESSION, "user", "我叫张三，在技术部")
append_message(SESSION, "assistant", "好的，张三。")
append_message(SESSION, "user", "报销金额超过多少需要审批？")
append_message(SESSION, "assistant", "超过 5000 元需要部门经理审批。")

print("=== 本地会话 ===")
for m in get_recent_messages(SESSION, limit=10):
    print(m["role"], "：", m["content"], "|", m["privacy_scope"])

# 云端会话：只存内存
append_message(CLOUD, "user", "我的电话是 13800138000",
               privacy_scope="cloud")
append_message(CLOUD, "assistant", "已收到。", privacy_scope="cloud")

print("=== 云端会话 ===")
for m in get_recent_messages(CLOUD, limit=10):
    print(m["role"], "：", m["content"], "|", m["privacy_scope"])