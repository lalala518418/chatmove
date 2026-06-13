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


def _choose(prompt, options):
    """显示带编号的选项，循环直到选到有效项；输入 q 取消返回 None。
    options: [(label, value), ...]"""
    for i, (label, _) in enumerate(options, 1):
        print(f"  [{i}] {label}")
    while True:
        s = input(f"{prompt} (1-{len(options)}, q 取消): ").strip().lower()
        if s == "q":
            return None
        if s.isdigit() and 1 <= int(s) <= len(options):
            return options[int(s) - 1][1]
        print("  ↳ 输入无效，请重输。")


def cmd_wizard(args):
    """无参数一键模式：选源平台→选对话→选操作→打包。给不熟命令行的人用，可随时 q 取消。"""
    print("== chatmove 一键迁移向导 ==  (任意步骤输入 q 取消)\n")

    # 1) 源平台（只有一个时自动选，多个时让用户挑）
    plats = list(ADAPTERS.keys())
    if len(plats) == 1:
        platform = plats[0]
        print(f"源平台: {platform}\n")
    else:
        print("从哪个平台迁出？")
        platform = _choose("选源平台", [(p, p) for p in plats])
        if not platform:
            return print("已取消。")
    a = ADAPTERS[platform]

    # 2) 选对话
    refs = a.list_conversations()
    if not refs:
        return print(f"{platform} 没找到对话。")
    print(f"\n{platform} 共 {len(refs)} 个对话，选一个迁移：")
    opts = []
    for r in refs:
        ts = time.strftime("%m-%d %H:%M", time.localtime(r.mtime)) if r.mtime else "?"
        opts.append((f"{ts}  {r.title or r.id}", r))
    ref = _choose("选对话", opts)
    if not ref:
        return print("已取消。")

    # 3) 选操作/目标
    print("\n要怎么迁移？")
    act = _choose("选操作", [
        ("同平台无损打包 → .cmove（搬到另一台机的同款应用，可 --resume 续接）", "pkg"),
        ("导出通用 IR(JSON) → 跨平台中转/人工查看（其它平台导入适配器开发中）", "ir"),
    ])
    if not act:
        return print("已取消。")

    if act == "pkg":
        default = f"{ref.id}.cmove"
        out = input(f"输出文件名 [默认 {default}]: ").strip() or default
        a.export_package(ref.id, out)
        print(f"\n✅ 完成。把 {out} 拷到目标机，运行：\n  chatmove import {out} --target-cwd <目标机项目路径>")
    else:
        conv = a.export_ir(ref.id)
        out = f"{ref.id}.ir.json"
        open(out, "w", encoding="utf-8").write(conv.to_json())
        print(f"\n✅ 已导出 IR -> {out}（{len(conv.messages)} 条消息）")


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
