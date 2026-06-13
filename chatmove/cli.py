"""chatmove 命令行入口。stdlib only。

  python3 -m chatmove platforms
  python3 -m chatmove list [--platform claude-code]
  python3 -m chatmove export <session_id> -o out.cmove [--platform claude-code]
  python3 -m chatmove import out.cmove --target-cwd /path/on/new/machine
  python3 -m chatmove ir <session_id>        # 导出统一IR(跨平台用)看看
"""
from __future__ import annotations
import argparse, time
from .adapters import ADAPTERS, get_adapter
from .adapters.base import Adapter


def cmd_platforms(args):
    for name, a in ADAPTERS.items():
        lossless = type(a).export_package is not Adapter.export_package
        print(f"  {name:14s} [{'无损迁移✓' if lossless else '仅IR'}]")


def cmd_list(args):
    a = get_adapter(args.platform)
    refs = a.list_conversations()
    if not refs:
        print("(没找到会话)"); return
    for r in refs:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.mtime)) if r.mtime else "?"
        print(f"{r.id}  {ts}  cwd={r.cwd}")
        if r.title:
            print(f"    {r.title}")


def cmd_export(args):
    get_adapter(args.platform).export_package(args.session_id, args.out)


def cmd_import(args):
    get_adapter(args.platform).import_package(args.package, target_cwd=args.target_cwd)


def cmd_ir(args):
    conv = get_adapter(args.platform).export_ir(args.session_id)
    print(f"# {conv.platform} {conv.id}  ({len(conv.messages)} 条消息)  cwd={conv.cwd}")
    for m in conv.messages[:6]:
        print(f"\n[{m.role}] {m.content[:200]}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="chatmove", description="跨设备/跨平台 AI 对话迁移")
    p.add_argument("--platform", default="claude-code")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("platforms").set_defaults(func=cmd_platforms)
    sub.add_parser("list").set_defaults(func=cmd_list)
    pe = sub.add_parser("export"); pe.add_argument("session_id"); pe.add_argument("-o", "--out", required=True); pe.set_defaults(func=cmd_export)
    pi = sub.add_parser("import"); pi.add_argument("package"); pi.add_argument("--target-cwd", default=None); pi.set_defaults(func=cmd_import)
    pr = sub.add_parser("ir"); pr.add_argument("session_id"); pr.set_defaults(func=cmd_ir)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
