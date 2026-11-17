# email_tools_test.py —— 验证 QQ 邮箱搜索、读取、发送
import os

from backend.tools.email_tools import email_read, email_search, email_send

print("=== 最近邮件 ===")
result = email_search(max_count=5)
print(result)

# 从搜索结果里取第一封邮件的编号
uid = None
for line in result.splitlines():
    if line.startswith("编号:"):
        uid = line.split("编号:")[1].split("|")[0].strip()
        break

if uid:
    print("\n=== 读取最新邮件 ===")
    print(email_read(uid))

# 发信测试：默认发给自己
qq_email = os.getenv("QQ_EMAIL", "")
if qq_email:
    print("\n=== 发送测试邮件 ===")
    print(email_send(
        to=qq_email,
        subject="数字化员工邮件测试",
        body="这是一封来自本地 Agent 的测试邮件。",
    ))
else:
    print("未配置 QQ_EMAIL，跳过发送测试")
