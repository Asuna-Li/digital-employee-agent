# desensitizer.py —— 本地脱敏：规则 + 词典 + 残留检查
"""原则：只做本地处理，映射只存内存，不落盘、不入库。"""

import re

# ---------- 规则层：固定格式实体 ----------
PATTERNS = [
    ("电话", re.compile(
        r"(?:手机号码|手机号|电话号码|电话|号码)"
        r"[:：]?\s*(?:是|为)?\s*\d{6,20}"
    )),
    
    ("邮箱", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("银行卡", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
    ("身份证", re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)")),
    ("金额", re.compile(r"(?<!\d)\d+(?:\.\d+)?\s*(?:元|万元|块)")),
    ("工号", re.compile(r"工号[:：]?\s*[A-Za-z0-9-]+")),
    ("合同号", re.compile(r"合同号[:：]?\s*[A-Za-z0-9-]+")),
]

# ---------- 词典层：业务敏感词 ----------
SENSITIVE_NAMES = ["张三", "李四", "王五", "赵六", "张三丰"]


def _replace_patterns(text: str, mapping: dict):
    """按正则替换固定格式实体，每个实体带编号，避免互相覆盖"""
    counters = {}
    for label, pattern in PATTERNS:
        def repl(match, label=label):
            counters[label] = counters.get(label, 0) + 1
            token = f"<{label}_{counters[label]}>"
            mapping[token] = match.group(0)
            return token
        text = pattern.sub(repl, text)
    return text


def _replace_names(text: str, mapping: dict):
    """替换词典里的人名；同一名字复用同一个编号，不同名字不覆盖"""
    if not SENSITIVE_NAMES:
        return text

    names = sorted(SENSITIVE_NAMES, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(n) for n in names))

    name_cache = {}
    def repl(match):
        name = match.group(0)
        if name not in name_cache:
            token = f"<人名_{len(name_cache) + 1}>"
            name_cache[name] = token
            mapping[token] = name
        return name_cache[name]

    return pattern.sub(repl, text)


def desensitize(text: str):
    """返回 (脱敏文本, 映射表)；映射表只留在内存"""
    mapping = {}
    result = _replace_patterns(text, mapping)
    result = _replace_names(result, mapping)
    return result, mapping


def restore(text: str, mapping: dict):
    """按映射还原；仅用于本地会话内展示，不写日志"""
    for token in sorted(mapping, key=len, reverse=True):
        text = text.replace(token, mapping[token])
    return text


def has_residual(text: str) -> bool:
    """残留检查：脱敏后还能不能匹配到敏感实体"""
    for _, pattern in PATTERNS:
        if pattern.search(text):
            return True
    for name in SENSITIVE_NAMES:
        if name in text:
            return True
    return False
