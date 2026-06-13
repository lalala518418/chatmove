"""适配器基类。每个平台实现一个 Adapter。"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..ir import Conversation


@dataclass
class ConvRef:
    """一个会话的轻量引用(用于列表，不含完整内容)。"""
    id: str
    platform: str
    title: str | None = None
    cwd: str | None = None
    mtime: float | None = None
    extra: dict | None = None


class Adapter(ABC):
    name: str = "base"

    @abstractmethod
    def list_conversations(self) -> list[ConvRef]:
        """列出该平台本机的会话。"""

    @abstractmethod
    def export_ir(self, conv_id: str) -> Conversation:
        """读取原生格式 -> 统一 IR(跨平台用)。"""

    # 同平台无损迁移(可选实现)：直接打包/解包原始文件 + 路径重映射
    def export_package(self, conv_id: str, out_path: str) -> None:
        raise NotImplementedError(f"{self.name} 暂不支持无损打包")

    def import_package(self, pkg_path: str, **target_opts) -> str:
        raise NotImplementedError(f"{self.name} 暂不支持无损导入")
