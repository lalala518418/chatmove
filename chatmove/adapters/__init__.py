from .claude_code import ClaudeCodeAdapter

ADAPTERS = {a.name: a for a in [ClaudeCodeAdapter()]}


def get_adapter(name: str):
    if name not in ADAPTERS:
        raise SystemExit(f"未知平台 '{name}'. 可用: {', '.join(ADAPTERS)}")
    return ADAPTERS[name]
