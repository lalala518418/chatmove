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


def cmd_wizard(args):
    """无参数一键模式：列出对话→选一个→选操作→打包。给不熟命令行的人用。"""
    a = get_adapter(args.platform)
    refs = a.list_conversations()
    if not refs:
        print("没找到对话。"); return
    print("== chatmove 一键迁移 ==\n请选择要迁移的对话：")
    for i, r in enumerate(refs, 1):
        ts = time.strftime("%m-%d %H:%M", time.localtime(r.mtime)) if r.mtime else "?"
        print(f"  [{i}] {ts}  {r.title or r.id}")
    sel = input("\n输入编号: ").strip()
    try:
        ref = refs[int(sel) - 1]
    except (ValueError, IndexError):
        print("编号无效。"); return
    print("\n选择操作：\n  [1] 无损打包(搬到另一台机的同款应用，可续接)\n  [2] 导出为通用IR(跨平台预览)")
    act = input("输入编号: ").strip()
    if act == "1":
        out = input(f"输出文件名 [默认 {ref.id}.cmove]: ").strip() or f"{ref.id}.cmove"
        a.export_package(ref.id, out)
        print(f"\n完成。把 {out} 拷到目标机，运行:\n  chatmove import {out} --target-cwd <目标机项目路径>")
    elif act == "2":
        conv = a.export_ir(ref.id)
        out = f"{ref.id}.ir.json"
        open(out, "w", encoding="utf-8").write(conv.to_json())
        print(f"已导出 IR -> {out} ({len(conv.messages)} 条消息)")
    else:
        print("未选择有效操作。")


def main(argv=None):
    p = argparse.ArgumentParser(prog="chatmove", description="跨设备/跨平台 AI 对话迁移")
    p.add_argument("--platform", default="claude-code")
    sub = p.add_subparsers(dest="cmd")   # 不强制：无子命令时进一键向导
    sub.add_parser("platforms").set_defaults(func=cmd_platforms)
    sub.add_parser("list").set_defaults(func=cmd_list)
    pe = sub.add_parser("export"); pe.add_argument("session_id"); pe.add_argument("-o", "--out", required=True); pe.set_defaults(func=cmd_export)
    pi = sub.add_parser("import"); pi.add_argument("package"); pi.add_argument("--target-cwd", default=None); pi.set_defaults(func=cmd_import)
    pr = sub.add_parser("ir"); pr.add_argument("session_id"); pr.set_defaults(func=cmd_ir)
    sub.add_parser("wizard").set_defaults(func=cmd_wizard)
    args = p.parse_args(argv)
    if not getattr(args, "func", None):   # 无子命令 → 一键向导
        args.func = cmd_wizard
    args.func(args)


if __name__ == "__main__":
    main()
