"""路径重映射工具——chatmove 的灵魂。

Claude Code 把会话存在 ~/.claude/projects/<项目路径名>/，其中目录名是把
项目绝对路径里的非字母数字字符都换成 '-'（不同操作系统的分隔符 / \\ : 都算）。
会话 jsonl 内部也多处嵌入 cwd 绝对路径。跨机/跨系统迁移时，若项目在目标机
路径不同，必须把这些路径改写，否则 --resume 对不上。

跨系统要点（v0.2 修复）：
- Linux 用 '/'、Windows 用 '\\' 和盘符 'C:'，不能只处理 '/'。
- 目录名规则**对齐 Claude Code 自身**：把不属于 [A-Za-z0-9_-] 的字符换成 '-'，
  即**保留下划线 '_' 和连字符 '-'**，其余(分隔符 / \\ :、点 . 等)逐字符变 '-'
  （不合并、不改大小写）。Claude Code 源码里就是 `replace(/[^a-zA-Z0-9\\-_]/g,"-")`。
  例：C:\\Users\\you\\my_proj -> C--Users-you-my_proj，/home/a/fast_lio -> -home-a-fast_lio。
"""
from __future__ import annotations
import json, os, re


def sanitize_cwd(cwd: str) -> str:
    """绝对路径 -> Claude Code 项目目录名（跨平台）。
    把非 [A-Za-z0-9_-] 的字符替换为 '-'，**保留下划线和连字符**，与 Claude Code 一致
    (`replace(/[^a-zA-Z0-9\\-_]/g,"-")`)：
      /home/a/fast_lio         -> -home-a-fast_lio
      C:\\Users\\you\\my_proj   -> C--Users-you-my_proj
    早期版本用了 [^A-Za-z0-9] 会把 '_' 也错改成 '-'，导致带下划线的项目 --resume 对不上。
    """
    return re.sub(r"[^A-Za-z0-9_-]", "-", cwd)


def remap_path(path: str, orig_home: str, new_home: str) -> str:
    """把路径里的"源家目录前缀"换成本机家目录，并把分隔符转成本机风格。
    跨系统也对：/home/a/fastlio (orig_home=/home/a) 在 Windows 上 ->
    C:\\Users\\you\\fastlio；反向亦然。
    前缀对不上（非家目录下的项目）就原样返回。
    """
    if orig_home and path.startswith(orig_home):
        tail = path[len(orig_home):]                  # 形如 /fastlio 或 \\fastlio\\sub
        rel = [p for p in re.split(r"[/\\]+", tail) if p]
        return os.path.join(new_home, *rel) if rel else new_home
    return path


# 向后兼容旧名字（旧代码/测试里叫 remap_home）
remap_home = remap_path


def remap_line_cwd(line: str, remap) -> str:
    """把一行 jsonl 里的 'cwd' 字段用 remap(old)->new 改写（保留其它内容不变）。

    只改结构化的 'cwd' 键，避免误伤正文里碰巧出现的路径字符串。
    remap 通常是 functools.partial(remap_path, orig_home=..., new_home=...)，
    对不在家目录下的 cwd 会原样返回，因此能安全地对每一行无脑调用。
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return line  # 非 JSON 行原样返回
    if isinstance(obj, dict) and isinstance(obj.get("cwd"), str):
        obj["cwd"] = remap(obj["cwd"])
    return json.dumps(obj, ensure_ascii=False)


def detect_cwd(lines: list[str]) -> str | None:
    """从会话 jsonl 中嗅探原始 cwd(取第一条带 cwd 的行)。"""
    for ln in lines:
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("cwd"):
            return obj["cwd"]
    return None
