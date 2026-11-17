# registry.py —— 工具注册表：schema + 真实函数
REGISTRY = {}


def register_tool(schema: dict):
    """注册一个工具；返回装饰器，保持原函数不变"""
    def decorator(func):
        name = schema["function"]["name"]
        REGISTRY[name] = {"schema": schema, "func": func}
        return func
    return decorator


def get_tool_schemas() -> list:
    """返回所有工具的 OpenAI tools 说明书"""
    return [item["schema"] for item in REGISTRY.values()]


def call_tool(name: str, arguments: dict):
    """按工具名执行真实函数"""
    item = REGISTRY.get(name)
    if not item:
        raise ValueError(f"未知工具：{name}")
    return item["func"](**arguments)
