"""Claude Code 适配器：本机会话在 ~/.claude/projects/<项目路径名>/<uuid>.jsonl

- 同平台无损迁移：打包 jsonl(+memory) → 目标机解包 + 路径重映射。
- 跨平台：export_ir 把 jsonl 解析成统一 IR。
"""
from __future__ import annotations
import json, os, glob, time, tarfile, io, shutil
from pathlib import Path
from .base import Adapter, ConvRef
from ..ir import Conversation, Message
from ..pathmap import sanitize_cwd, remap_line_cwd, detect_cwd

PROJECTS = Path.home() / ".claude" / "projects"


def _text_of(content) -> str:
    """message.content 可能是 str 或 [{type:text,text:...}, ...]，统一取文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text" and b.get("text"):
                    parts.append(b["text"])
                elif b.get("type") == "tool_use":
                    parts.append(f"[tool_use {b.get('name','')}]")
                elif b.get("type") == "tool_result":
                    parts.append("[tool_result]")
        return "\n".join(parts)
    return ""


class ClaudeCodeAdapter(Adapter):
    name = "claude-code"

    def detect(self) -> bool:
        return PROJECTS.is_dir() and any(PROJECTS.glob("*/*.jsonl"))

    def _session_path(self, conv_id: str) -> Path:
        hits = list(PROJECTS.glob(f"*/{conv_id}.jsonl"))
        if not hits:
            raise FileNotFoundError(f"找不到会话 {conv_id} (在 {PROJECTS})")
        return hits[0]

    def list_conversations(self) -> list[ConvRef]:
        refs = []
        for f in PROJECTS.glob("*/*.jsonl"):
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            cwd = detect_cwd(lines)
            title = None
            for ln in lines:
                try:
                    o = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if o.get("type") == "user" and isinstance(o.get("message"), dict):
                    t = _text_of(o["message"].get("content")).strip().replace("\n", " ")
                    if t:
                        title = (t[:60] + "…") if len(t) > 60 else t
                        break
            refs.append(ConvRef(id=f.stem, platform=self.name, title=title,
                                cwd=cwd, mtime=f.stat().st_mtime,
                                extra={"project_dir": f.parent.name}))
        refs.sort(key=lambda r: r.mtime or 0, reverse=True)
        return refs

    def export_ir(self, conv_id: str) -> Conversation:
        f = self._session_path(conv_id)
        lines = f.read_text(encoding="utf-8").splitlines()
        cwd = detect_cwd(lines)
        msgs = []
        for ln in lines:
            try:
                o = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if o.get("type") in ("user", "assistant") and isinstance(o.get("message"), dict):
                m = o["message"]
                msgs.append(Message(role=m.get("role", o["type"]),
                                    content=_text_of(m.get("content")),
                                    timestamp=o.get("timestamp")))
        return Conversation(id=conv_id, platform=self.name, cwd=cwd,
                            created=msgs[0].timestamp if msgs else None,
                            messages=msgs, raw_meta={"project_dir": f.parent.name})

    # ---- 同平台无损迁移 ----
    def export_package(self, conv_id: str, out_path: str) -> None:
        f = self._session_path(conv_id)
        lines = f.read_text(encoding="utf-8").splitlines()
        cwd = detect_cwd(lines) or ""
        manifest = {"format": "chatmove/claude-code/1", "session_id": conv_id,
                    "orig_cwd": cwd, "project_dir": f.parent.name}
        with tarfile.open(out_path, "w:gz") as tar:
            # 会话 jsonl
            tar.add(f, arcname=f"{conv_id}.jsonl")
            # manifest
            data = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
            ti = tarfile.TarInfo("manifest.json"); ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
            # 该项目的 memory/(若有)
            mem = f.parent / "memory"
            if mem.is_dir():
                tar.add(mem, arcname="memory")
        print(f"已打包 -> {out_path} (orig_cwd={cwd})")

    def import_package(self, pkg_path: str, target_cwd: str | None = None, **_) -> str:
        with tarfile.open(pkg_path, "r:gz") as tar:
            manifest = json.loads(tar.extractfile("manifest.json").read())
            conv_id = manifest["session_id"]
            orig_cwd = manifest.get("orig_cwd", "")
            new_cwd = target_cwd or orig_cwd
            # 目标项目目录
            proj = PROJECTS / sanitize_cwd(new_cwd)
            proj.mkdir(parents=True, exist_ok=True)
            # 写 jsonl + 路径重映射
            jl = tar.extractfile(f"{conv_id}.jsonl").read().decode("utf-8").splitlines()
            out = "\n".join(remap_line_cwd(ln, orig_cwd, new_cwd) for ln in jl) + "\n"
            (proj / f"{conv_id}.jsonl").write_text(out, encoding="utf-8")
            # memory(若有)
            members = [m for m in tar.getmembers() if m.name.startswith("memory/")]
            for m in members:
                m.name = m.name  # 解到 proj 下
            if members:
                tar.extractall(path=proj, members=members)
        print(f"已导入会话 {conv_id} -> {proj}")
        print(f"路径重映射: {orig_cwd or '(空)'} -> {new_cwd}")
        print(f"在目标机 `cd {new_cwd} && claude --resume` 即可续接。")
        return conv_id
