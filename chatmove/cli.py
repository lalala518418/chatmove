"""chatmove 命令行入口。stdlib only。

  python3 -m chatmove platforms
  python3 -m chatmove list [--platform claude-code]
  python3 -m chatmove export <session_id> -o out.cmove [--platform claude-code]
  python3 -m chatmove import out.cmove --target-cwd /path/on/new/machine
  python3 -m chatmove ir <session_id>        # 导出统一IR(跨平台用)看看
"""
from __future__ import annotations
import argparse, time, os
from pathlib import Path
from .adapters import ADAPTERS, get_adapter, detected_adapters
from .adapters.base import Adapter


def cmd_platforms(args):
    for name, a in ADAPTERS.items():
        lossless = type(a).export_package is not Adapter.export_package
        print(f"  {name:14s} [{'lossless ✓' if lossless else 'IR only'}]")


def cmd_list(args):
    a = get_adapter(args.platform)
    refs = a.list_conversations()
    if not refs:
        print("(no sessions found)"); return
    for r in refs:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.mtime)) if r.mtime else "?"
        print(f"{r.id}  {ts}  cwd={r.cwd}")
        if r.title:
            print(f"    {r.title}")


def cmd_export(args):
    get_adapter(args.platform).export_package(args.session_id, args.out)


def cmd_import(args):
    # 不填 --target-cwd 时传 None：适配器自动把"源家目录前缀"换成本机家目录(全自动定位)
    get_adapter(args.platform).import_package(args.package, target_cwd=args.target_cwd)


def cmd_ir(args):
    conv = get_adapter(args.platform).export_ir(args.session_id)
    print(f"# {conv.platform} {conv.id}  ({len(conv.messages)} messages)  cwd={conv.cwd}")
    for m in conv.messages[:6]:
        print(f"\n[{m.role}] {m.content[:200]}")


def _choose(prompt, options):
    """显示带编号的选项，循环直到选到有效项；输入 q 取消返回 None。
    options: [(label, value), ...]"""
    for i, (label, _) in enumerate(options, 1):
        print(f"  [{i}] {label}")
    while True:
        s = input(f"{prompt} (1-{len(options)}, q to cancel): ").strip().lower()
        if s == "q":
            return None
        if s.isdigit() and 1 <= int(s) <= len(options):
            return options[int(s) - 1][1]
        print("  ↳ invalid input, try again.")


def _wizard_export():
    # 1) 源平台：自动探测本机装了哪些平台(不写死 claude)
    found = detected_adapters()
    if not found:
        return print("No supported platform data found on this machine.")
    if len(found) == 1:
        platform = next(iter(found))
        print(f"Detected platform: {platform}\n")
    else:
        print("Multiple platforms detected — export from which one?")
        platform = _choose("Source platform", [(f"{p}", p) for p in found])
        if not platform:
            return print("Cancelled.")
    a = ADAPTERS[platform]

    # 2) 选对话(未实现的适配器会抛 NotImplementedError，友好提示)
    try:
        refs = a.list_conversations()
    except NotImplementedError as e:
        return print(f"⚠ {e}")
    if not refs:
        return print(f"No conversations found for {platform}.")
    print(f"\n{platform}: {len(refs)} conversation(s), pick one to migrate:")
    opts = [(f"{time.strftime('%m-%d %H:%M', time.localtime(r.mtime)) if r.mtime else '?'}  {r.title or r.id}", r)
            for r in refs]
    ref = _choose("Conversation", opts)
    if not ref:
        return print("Cancelled.")

    # 3) 操作/目标
    print("\nHow do you want to migrate it?")
    act = _choose("Action", [
        ("Lossless package -> .cmove (same tool on another machine, resumable)", "pkg"),
        ("Export shared IR (JSON) -> cross-platform transfer / human review", "ir"),
    ])
    if not act:
        return print("Cancelled.")
    if act == "pkg":
        out = str(Path.home() / f"{ref.id}.cmove")   # 自动命名+存到家目录，不用用户敲
        a.export_package(ref.id, out)
        print(f"\n✅ Done. Saved to: {out}")
        print(f"   Copy it to the target machine and run `chatmove import {Path(out).name}` —")
        print("   it auto-locates the target Claude store (by this machine's home); no cd / paths needed.")
    else:
        conv = a.export_ir(ref.id)
        out = f"{ref.id}.ir.json"
        open(out, "w", encoding="utf-8").write(conv.to_json())
        print(f"\n✅ Exported IR -> {out} ({len(conv.messages)} messages)")


def _find_cmove_files():
    """自动扫常见位置的 .cmove，让用户选数字而不用敲路径。"""
    spots = [Path.cwd(), Path.home() / "Downloads", Path.home()]
    seen, files = set(), []
    for d in spots:
        if d.is_dir():
            for f in sorted(d.glob("*.cmove")):
                if f.resolve() not in seen:
                    seen.add(f.resolve()); files.append(f)
    return files


def _wizard_import():
    files = _find_cmove_files()
    if files:
        print("Found these .cmove packages, pick one to import:")
        pick = _choose("File", [(str(f), f) for f in files])
        if not pick:
            return print("Cancelled.")
        pkg = str(pick)
    else:
        print("(no .cmove found in current dir / Downloads / home)")
        pkg = input("Enter .cmove path (q to cancel): ").strip()
        if pkg.lower() == "q" or not os.path.isfile(pkg):
            return print("Cancelled.")
    # 全自动定位：target_cwd=None → 适配器按本机家目录自动重映射，无需用户填路径
    ADAPTERS["claude-code"].import_package(pkg, target_cwd=None)


def cmd_wizard(args):
    """一键向导：先选迁出/迁入方向，再走对应流程。随时输入 q 取消。"""
    print("== chatmove wizard ==  (type q at any step to cancel)\n")
    direction = _choose("What do you want to do?", [
        ("Export (package a local conversation to take away)", "out"),
        ("Import (load a .cmove someone gave you into this machine)", "in"),
    ])
    if not direction:
        return print("Cancelled.")
    print()
    (_wizard_export if direction == "out" else _wizard_import)()


def main(argv=None):
    p = argparse.ArgumentParser(prog="chatmove", description="Cross-device / cross-platform AI chat migration")
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
