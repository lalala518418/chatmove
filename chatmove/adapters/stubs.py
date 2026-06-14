"""其它平台的适配器占位。

架构上已支持多平台——这里给出 Cursor / Codex 的探测路径和接口占位，
具体读取格式待实现(见 docs/adding-an-adapter.md，欢迎贡献)。
detect() 会检查该平台数据目录是否存在，让向导能自动发现已安装的平台。
"""
from __future__ import annotations
import os, sys
from pathlib import Path
from .base import Adapter, ConvRef
from ..ir import Conversation

_TODO = "adapter WIP: {name} session format not implemented yet. See docs/adding-an-adapter.md — contributions welcome."


def _platform_dirs(linux, mac, win):
    if sys.platform == "darwin":
        return [Path.home() / mac]
    if os.name == "nt":
        return [Path(os.environ.get("APPDATA", Path.home())) / win]
    return [Path.home() / linux]


class CursorAdapter(Adapter):
    name = "cursor"
    # Cursor 把对话存在 SQLite(state.vscdb) 里；下面是各系统的配置目录(待确认)
    def _dirs(self):
        return _platform_dirs(".config/Cursor", "Library/Application Support/Cursor",
                              "Cursor")

    def detect(self) -> bool:
        return any(d.exists() for d in self._dirs())

    def list_conversations(self) -> list[ConvRef]:
        raise NotImplementedError(_TODO.format(name="cursor"))

    def export_ir(self, conv_id: str) -> Conversation:
        raise NotImplementedError(_TODO.format(name="cursor"))


class CodexAdapter(Adapter):
    name = "codex"
    # OpenAI Codex CLI 一般在 ~/.codex/ 下存会话(待确认)
    def _dirs(self):
        return [Path.home() / ".codex"]

    def detect(self) -> bool:
        return any(d.exists() for d in self._dirs())

    def list_conversations(self) -> list[ConvRef]:
        raise NotImplementedError(_TODO.format(name="codex"))

    def export_ir(self, conv_id: str) -> Conversation:
        raise NotImplementedError(_TODO.format(name="codex"))
