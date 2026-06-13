# chatmove

跨设备 · 跨平台的 AI 对话迁移工具。把一个会话从一台机器/一个平台**迁出(export)**，**迁入(import)**到另一台机器/另一个平台。

> 起源：Claude Code 的对话存在每台机器本地(`~/.claude/projects/<项目路径名>/*.jsonl`)、不随账号云同步，换机器就丢上下文。chatmove 解决这个，并推广到多平台。

## 两种迁移模式（核心设计）
1. **同平台 · 无损搬运(lossless)**：原样搬运会话文件 + **重映射内嵌的绝对路径(cwd)**。保真、目标机可直接 `--resume` 续接。例：Jetson 的 Claude Code 会话 → 5080 台式机。
2. **跨平台 · IR 转换**：把会话解析成统一中间表示(IR：role/content 序列)，再写成目标平台格式。有损(主要保文本)，但能在不同 AI 工具间搬。

## 架构（适配器模式）
```
源平台 ──(adapter.export)──► [IR / 无损包] ──(adapter.import)──► 目标平台
```
每个平台一个 **adapter**，只需实现"读/写自己的格式"。N 个平台 = N 个适配器(不是 N² 种两两转换)，围绕一个 IR。

## 适配器状态
- ✅ **claude-code**：Claude Code CLI 本地会话(`~/.claude/projects/`)。支持 list / 无损 export+import(含路径重映射) / 导出到 IR。
- ⬜ 计划：chatgpt(导出的 conversations.json)、claude.ai、cursor、其它 CLI agent…(欢迎贡献，见 `docs/adding-an-adapter.md`)

## 用法
**一键模式（推荐给不熟命令行的人）**：直接运行，进交互向导，选对话→选操作→打包：
```bash
python3 -m chatmove          # 或 python3 -m chatmove wizard
```
**命令模式**：
```bash
python3 -m chatmove platforms                      # 列出可用适配器(本机探测到的)
python3 -m chatmove list                           # 列出本机 Claude Code 会话
python3 -m chatmove export <session_id> -o my.cmove   # 无损打包(会话+memory)
# 到另一台机器(全自动定位，通常不用填路径):
python3 -m chatmove import my.cmove
#   程序自动把源路径里的"家目录前缀"换成本机家目录(/home/a/x -> /home/你/x)，
#   放进本机 Claude 的位置。需要时才用 --target-cwd <path> 覆盖。
```

## 全自动定位(本工具的核心体验)
用户只选数字、不用 cd、不用敲路径：
- **平台自动探测**：`detect()` 找出本机装了哪些平台(claude-code/cursor/codex…)，多个就让你选。
- **位置自动甄别**：每个平台的存储位置由适配器按本机 `$HOME` 自动算(不同机器用户路径不同也能对)。
- **路径自动重映射**：导入时把源机的家目录前缀换成本机的，会话自动落到正确项目目录。
- **文件自动扫描**：导入向导自动扫 当前目录/下载/家目录 里的 `.cmove`，选编号即可。

## 跨系统一键分发（规划）
目标：Windows/macOS/Linux 用户都能**一键启动**，无需装 Python。
- 因为是纯标准库，用 **PyInstaller** 可打包成单文件可执行：Windows `.exe`、macOS/Linux 二进制。
- `build.sh`：在各目标系统上 `pyinstaller -F -n chatmove chatmove/__main__.py` 出对应平台的可执行(注意 PyInstaller 不能跨系统交叉打包，每个 OS 各出一个)。
- 轻量备选：`run.sh`(Linux/Mac)、`run.bat`(Windows) 启动器，对已装 Python 的用户直接 `python -m chatmove`。
- 双击/一键 → 向导列出对话 → 选对话 + 目标 → 生成包 → 拷到另一台机一键导入。

## 设计要点 / 已知坑
- **路径重映射是灵魂**：会话目录名 = 项目绝对路径 `/`→`-`(`/home/a/fastlio`→`-home-a-fastlio`)，且 jsonl 内多处嵌 `cwd`。两机路径不同必须改写，否则 `--resume` 对不上。
- jsonl 格式随 Claude Code 版本可能变 → adapter 带 `version` 字段、做容错。
- 纯 Python 标准库实现，无第三方依赖，`python3` 直接跑。

## 状态
早期 MVP 脚手架。先打通 claude-code 的无损同平台迁移，再扩跨平台。
