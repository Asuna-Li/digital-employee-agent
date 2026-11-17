# pending.py —— 待确认操作（内存版，单用户足够）
_PENDING = {}


def set_pending(owner: str, tool_name: str, arguments: dict,
                summary: str = ""):
    """保存一个等待用户确认的操作"""
    _PENDING[owner] = {
        "tool_name": tool_name,
        "arguments": arguments,
        "summary": summary,
    }


def get_pending(owner: str):
    return _PENDING.get(owner)


def clear_pending(owner: str):
    _PENDING.pop(owner, None)


def has_pending(owner: str) -> bool:
    return owner in _PENDING
