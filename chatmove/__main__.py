import sys

# Windows 控制台默认 GBK，会把中文输出变乱码；尽量切到 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from .cli import main

main()
