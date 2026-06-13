"""统一中间表示(IR)：跨平台迁移时的通用对话格式。

同平台无损迁移不一定用 IR(直接搬原始文件更保真)；IR 主要用于跨平台转换。
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import json


@dataclass
class Message:
    role: str                      # user | assistant | system | tool
    content: str                   # 纯文本(跨平台保文本为主)
    timestamp: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)   # 平台特定附加信息


@dataclass
class Conversation:
    id: str
    platform: str                  # 来源平台，如 "claude-code"
    title: str | None = None
    created: str | None = None
    cwd: str | None = None         # CLI 类 agent 的项目工作目录
    messages: list[Message] = field(default_factory=list)
    raw_meta: dict[str, Any] = field(default_factory=dict)  # 为往返保留的原始信息

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @staticmethod
    def from_json(s: str) -> "Conversation":
        d = json.loads(s)
        d["messages"] = [Message(**m) for m in d.get("messages", [])]
        return Conversation(**d)
