"""路径重映射工具——chatmove 的灵魂。

Claude Code 把会话存在 ~/.claude/projects/<项目路径名>/，其中目录名是
项目绝对路径把 '/' 换成 '-'。会话 jsonl 内部也多处嵌入 cwd 绝对路径。
跨机迁移时，若项目在目标机路径不同，必须把这些路径改写，否则 --resume 对不上。
"""
from __future__ import annotations
import json


def sanitize_cwd(cwd: str) -> str:
    """绝对路径 -> Claude Code 项目目录名。/home/a/fastlio -> -home-a-fastlio"""
    return cwd.replace("/", "-")


def remap_line_cwd(line: str, old_cwd: str, new_cwd: str) -> str:
    """把一行 jsonl 里的 cwd 字段从 old_cwd 改成 new_cwd(保留其它内容不变)。

    只改结构化的 'cwd' 键，避免误伤正文里碰巧出现的路径字符串。
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return line  # 非 JSON 行原样返回
    if isinstance(obj, dict) and obj.get("cwd") == old_cwd:
        obj["cwd"] = new_cwd
    return json.dumps(obj, ensure_ascii=False)


def remap_home(cwd: str, orig_home: str, new_home: str) -> str:
    """把路径里的"源家目录前缀"换成本机家目录，实现跨机自动定位。
    /home/a/fastlio  (orig_home=/home/a, new_home=/home/lalala) -> /home/lalala/fastlio
    不同机器用户名/家目录不同时，这样会自动落到对应位置，无需用户手填。"""
    if orig_home and cwd.startswith(orig_home):
        return new_home + cwd[len(orig_home):]
    return cwd  # 前缀对不上(非家目录下的项目)就原样保留


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
