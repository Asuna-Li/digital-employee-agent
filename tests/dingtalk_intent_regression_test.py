# 回归测试：@所有人 不能被误判成邮件请求
from backend.llm.tool_agent import _is_send_request


dingtalk_text = (
    "给钉钉群发送通知：今天下午三点开会，请准时参加，并@所有人。"
)
email_text = "把审批单作为附件发送到2894229619@qq.com"

assert _is_send_request(dingtalk_text) is False
assert _is_send_request(email_text) is True

print("钉钉 @所有人 未被误判为邮件：通过")
print("真实邮箱附件发送仍可识别：通过")
