from .claude_code import ClaudeCodeAdapter
from .stubs import CursorAdapter, CodexAdapter

ADAPTERS = {a.name: a for a in [ClaudeCodeAdapter(), CursorAdapter(), CodexAdapter()]}


def get_adapter(name: str):
    if name not in ADAPTERS:
        raise SystemExit(f"未知平台 '{name}'. 可用: {', '.join(ADAPTERS)}")
    return ADAPTERS[name]


def detected_adapters():
    """返回本机探测到(数据目录存在)的平台。"""
    return {n: a for n, a in ADAPTERS.items() if a.detect()}
