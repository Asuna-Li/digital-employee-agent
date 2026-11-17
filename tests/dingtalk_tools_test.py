# dingtalk_tools_test.py —— 使用模拟响应验证钉钉工具，不发送真实群消息
from unittest.mock import Mock, patch

from backend.tools.dingtalk_tools import dingtalk_send


fake_response = Mock()
fake_response.raise_for_status.return_value = None
fake_response.json.return_value = {"errcode": 0, "errmsg": "ok"}

with patch(
    "backend.tools.dingtalk_tools.requests.post",
    return_value=fake_response,
) as mocked_post:
    result = dingtalk_send(
        "数字化员工测试通知，请忽略。",
        at_mobiles=["13900000000"],
    )

    request_url = mocked_post.call_args.args[0]
    payload = mocked_post.call_args.kwargs["json"]

    print(result)
    print("加签参数已生成:", "timestamp=" in request_url and "sign=" in request_url)
    print("消息类型:", payload["msgtype"])
    print("@手机号:", payload["at"]["atMobiles"])
    print("是否真实联网:", False)
