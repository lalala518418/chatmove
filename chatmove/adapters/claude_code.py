"""Claude Code 适配器：本机会话在 ~/.claude/projects/<项目路径名>/<uuid>.jsonl

- 同平台无损迁移：打包 jsonl(+memory) → 目标机解包 + 路径重映射。
- 跨平台：export_ir 把 jsonl 解析成统一 IR。
"""
from __future__ import annotations
import json, os, sys, glob, time, uuid, datetime, tarfile, io, shutil
from functools import partial
from pathlib import Path
from .base import Adapter, ConvRef
from ..ir import Conversation, Message
from ..pathmap import sanitize_cwd, remap_line_cwd, detect_cwd, remap_path

PROJECTS = Path.home() / ".claude" / "projects"
CLAUDE_JSON = Path.home() / ".claude.json"   # Claude Code/桌面端的项目注册表


def register_project(cwd: str) -> bool:
    """把项目 cwd 登记进 ~/.claude.json 的 projects 表。

    这是无损迁移能"被看见"的关键一步：会话 jsonl 放对了，但 Claude Code 的
    app/CLI 靠这张表识别项目，没登记就不会出现在列表/Recents 里。
    首次改动会在旁边留一份 .chatmove-bak 备份。表不存在/解析失败则跳过(返回 False)。
    """
    if not CLAUDE_JSON.is_file():
        return False
    try:
        raw = CLAUDE_JSON.read_text(encoding="utf-8")
        d = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return False
    projects = d.setdefault("projects", {})
    if cwd in projects:
        return True
    projects[cwd] = {
        "allowedTools": [], "mcpContextUris": [],
        "enabledMcpjsonServers": [], "disabledMcpjsonServers": [],
        "hasTrustDialogAccepted": True, "projectOnboardingSeenCount": 0,
        "hasClaudeMdExternalIncludesApproved": False,
        "hasClaudeMdExternalIncludesWarningShown": False,
    }
    bak = CLAUDE_JSON.with_name(CLAUDE_JSON.name + ".chatmove-bak")
    if not bak.exists():
        bak.write_text(raw, encoding="utf-8")
    CLAUDE_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _safe_members(tar: tarfile.TarFile, prefix: str):
    """只放行 prefix 下、且不含 '..'/绝对路径的成员，防 tar 路径穿越。"""
    for m in tar.getmembers():
        if not m.name.startswith(prefix):
            continue
        if os.path.isabs(m.name) or ".." in Path(m.name).parts:
            continue
        yield m


# ---- Claude 桌面端(Electron app)会话索引 ----
# 关键坑：CLI `claude --resume` 读 ~/.claude/projects/，但**桌面端 app 的 Recents
# 列表不扫 projects/**，它读自己的索引文件：
#   <配置根>/claude-code-sessions/<accountId>/<workspaceId>/local_<uuid>.json
# 每个文件 = 一条会话，靠 cliSessionId 指回 projects 里的 jsonl。
# 所以无损迁移要想在桌面端也"看得见"，得额外补一条这样的索引。跨系统配置根不同。

def _desktop_config_roots() -> list[Path]:
    """各 OS 下 Claude 桌面端的配置根目录(存在的才返回)。"""
    home = Path.home()
    roots = []
    if sys.platform == "darwin":
        roots.append(home / "Library" / "Application Support" / "Claude")
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        roots.append(Path(appdata) / "Claude" if appdata else home / "AppData" / "Roaming" / "Claude")
    else:  # linux / 其它 Electron 默认走 XDG
        xdg = os.environ.get("XDG_CONFIG_HOME")
        roots.append((Path(xdg) if xdg else home / ".config") / "Claude")
    return [r for r in roots if r.is_dir()]


def _find_desktop_session_dir():
    """定位桌面端会话索引目录 claude-code-sessions/<accountId>/<workspaceId>/。

    选取优先级：① ownerAccountId 命中 > 其它 account；② 已有 local_*.json > 空目录；
    ③ 最近修改。**不再要求目录里已有 local_*.json**——空的 workspace 目录也能定位，
    这样即使桌面端刚把"活动会话"文件清掉、目录暂时为空也能补索引。

    返回 (ws_path, files, None)；失败返回 (None, [], 原因字符串)，便于排查。
    """
    roots = _desktop_config_roots()
    if not roots:
        return None, [], "未找到 Claude 桌面端配置目录(可能没装桌面端)"
    tried = []
    best = None  # (score, ws, files)
    for root in roots:
        base = root / "claude-code-sessions"
        if not base.is_dir():
            tried.append(f"{base} 不存在")
            continue
        owner = None
        cf = root / "cowork-enabled-cli-ops.json"
        if cf.is_file():
            try:
                owner = json.loads(cf.read_text(encoding="utf-8")).get("ownerAccountId")
            except (OSError, json.JSONDecodeError):
                pass
        accs = [d for d in base.iterdir() if d.is_dir()]
        if not accs:
            tried.append(f"{base} 下无 account 目录")
            continue
        for acc in accs:
            owner_match = 1 if acc.name == owner else 0
            wss = [w for w in acc.iterdir() if w.is_dir()]
            if not wss:
                tried.append(f"{acc.name} 下无 workspace 目录")
            for ws in wss:
                files = list(ws.glob("local_*.json"))
                mtime = max((f.stat().st_mtime for f in files), default=ws.stat().st_mtime)
                score = (owner_match, 1 if files else 0, mtime)
                if best is None or score > best[0]:
                    best = (score, ws, files)
    if best is None:
        return None, [], "；".join(tried) or "claude-code-sessions 下无可用 workspace 目录"
    return best[1], best[2], None


def _iso_to_ms(iso: str) -> int:
    return int(datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def _build_desktop_entry(cli_id, cwd, title, created_ms, last_ms, turns, model="claude-opus-4-8"):
    """构造一条桌面端会话索引(纯数据，便于测试)。
    安全：permissionMode=default、不写 chromePermissionMode——绝不照抄样本里的
    `skip_all_permission_checks`(那等于关掉所有权限确认/开后门)。"""
    return {
        "sessionId": "local_" + str(uuid.uuid4()),
        "cliSessionId": cli_id,
        "cwd": cwd, "originCwd": cwd,
        "lastFocusedAt": int(time.time() * 1000),   # 设为现在 → 排在 Recents 顶部
        "createdAt": created_ms, "lastActivityAt": last_ms,
        "model": model, "effort": "high",
        "isArchived": False,
        "title": title, "titleSource": "user",
        "permissionMode": "default",                # 安全默认，不跳过权限
        "remoteMcpServersConfig": [],
        "completedTurns": turns,
        "alwaysAllowedReasons": [], "sessionPermissionUpdates": [],
        "classifierSummaryEnabled": True, "spawnSeed": {},
    }


def _session_meta(lines):
    """从 jsonl 行提取 (标题, createdAt_ms, lastActivityAt_ms, turn数)，供索引用。
    标题取第一条非空 user 文本；时间取首/末带 timestamp 的记录；turn 数数 user 消息。"""
    title, ts, turns = None, [], 0
    for ln in lines:
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        if o.get("timestamp"):
            ts.append(o["timestamp"])
        if o.get("type") == "user" and isinstance(o.get("message"), dict):
            turns += 1
            if title is None:
                t = _text_of(o["message"].get("content")).strip().replace("\n", " ")
                if t:
                    title = (t[:60] + "…") if len(t) > 60 else t
    created = _iso_to_ms(ts[0]) if ts else int(time.time() * 1000)
    last = _iso_to_ms(ts[-1]) if ts else created
    return title, created, last, turns


def register_desktop_session(cli_id, cwd, title, created_ms, last_ms, turns):
    """给桌面端 app 补一条会话索引，让迁移的会话出现在 Recents(而不只是 CLI --resume)。
    已存在同 cliSessionId 的索引则不重复创建。
    返回 (路径, None)；跳过时返回 (None, 原因)，原因会打印给用户便于排查。"""
    ws, files, reason = _find_desktop_session_dir()
    if ws is None:
        return None, reason
    for f in files:                                  # 去重：已索引就别再建
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("cliSessionId") == cli_id:
                return str(f), None
        except (OSError, json.JSONDecodeError):
            pass
    entry = _build_desktop_entry(cli_id, cwd, title, created_ms, last_ms, turns)
    out = ws / (entry["sessionId"] + ".json")
    out.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out), None


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
                    "orig_cwd": cwd, "orig_home": str(Path.home()),
                    "project_dir": f.parent.name}
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
            orig_home = manifest.get("orig_home", "")
            new_home = str(Path.home())
            # 全自动定位：没指定目标就把"源家目录前缀"换成本机家目录(跨系统会转分隔符)
            new_cwd = target_cwd or remap_path(orig_cwd, orig_home, new_home)
            # 目标项目目录(跨平台 sanitize：/ \\ : 等都 -> '-')
            proj = PROJECTS / sanitize_cwd(new_cwd)
            proj.mkdir(parents=True, exist_ok=True)
            # 写 jsonl + 路径重映射：对每一行的 cwd 统一按家目录前缀重映射，
            # 这样主目录和子目录(如 .../FAST_LIO-main)的 cwd 都能正确改写。
            remap = partial(remap_path, orig_home=orig_home, new_home=new_home)
            jl = tar.extractfile(f"{conv_id}.jsonl").read().decode("utf-8").splitlines()
            out = "\n".join(remap_line_cwd(ln, remap) for ln in jl) + "\n"
            (proj / f"{conv_id}.jsonl").write_text(out, encoding="utf-8")
            # memory(若有)，带路径穿越防护
            members = list(_safe_members(tar, "memory/"))
            if members:
                tar.extractall(path=proj, members=members)
        registered = register_project(new_cwd)
        # 从会话内容提取标题/时间/turn 数，给桌面端索引用
        title, created_ms, last_ms, turns = _session_meta(jl)
        desktop, desktop_reason = register_desktop_session(conv_id, new_cwd, title or conv_id,
                                                           created_ms, last_ms, turns)
        print(f"已导入会话 {conv_id} -> {proj}")
        print(f"路径重映射: {orig_cwd or '(空)'} -> {new_cwd}")
        if registered:
            print(f"已登记项目到 {CLAUDE_JSON.name}，CLI/桌面端能识别该项目。")
        else:
            print(f"⚠ 未能登记到 {CLAUDE_JSON.name}(文件缺失或解析失败)，"
                  f"会话可能不在列表里显示，但 `--resume` 仍可用。")
        if desktop:
            print(f"已为桌面端 app 补会话索引(重启 app 后出现在 Recents)。")
        else:
            print(f"(跳过桌面端索引：{desktop_reason}；CLI `--resume` 不受影响。)")
        print(f"在目标机 `cd {new_cwd} && claude --resume` 即可续接。")
        return conv_id
