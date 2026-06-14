# chatmove

> 跨设备 · 跨平台的 AI 对话迁移工具。把一个会话从一台机器/一个平台**迁出(export)**，**迁入(import)**到另一台机器/另一个平台，原样续接。

[English](README.md) · **中文**

**要解决的问题。** Claude Code 的对话存在每台机器本地(`~/.claude/projects/<目录>/*.jsonl`)、不随账号云同步，换机器——或者从 Linux 挪到 Mac——上下文就全丢了。**chatmove** 把一个会话(连同它的项目 memory)打包成一个 `.cmove` 文件，在目标机解包并重写里面内嵌的绝对路径，让 `claude --resume` 直接能用。

## 特性
- **一键向导**——运行 `chatmove`，选数字即可。不用记参数、不用敲路径。
- **同工具无损迁移**——原样搬运会话文件并重映射每一处内嵌 `cwd`，目标机 `--resume` 上下文完整。
- **跨系统**——Linux ⇄ macOS ⇄ Windows。分隔符、盘符、项目目录命名规则都自动按目标系统转换。
- **自动定位 + 自动登记**——按本机 `$HOME` 找到 Claude 存储，登记到 `~/.claude.json`，并(尽力)补上桌面端索引，让会话在 **CLI 和桌面端 app 都能看到**。
- **纯标准库**——零第三方依赖，有 Python 3.9+ 就能跑。
- **适配器架构**——每个平台一个适配器，围绕一个统一 IR。N 个平台 = N 个适配器，而不是 N² 种两两转换。

## 安装
```bash
# 方式 A —— 安装 chatmove 命令
pip install git+https://github.com/lalala518418/chatmove.git

# 方式 B —— 直接从源码跑(纯标准库，无需安装)
git clone https://github.com/lalala518418/chatmove.git
cd chatmove
python  -m chatmove     # Windows
python3 -m chatmove     # macOS / Linux
```

## 快速上手 —— 一条命令
直接运行，跟着编号提示走(迁出 ⇆ 迁入 → 平台 → 对话)：
```bash
chatmove                # 或：python -m chatmove
```

**把一个会话从 A 机搬到 B 机：**
1. 在 **A** 机：`chatmove` → **迁出** → 选对话 → 生成 `~/<id>.cmove`。
2. 把这个 `.cmove` 拷到 **B** 机(隔空投送 / U 盘 / scp / 网盘)。
3. 在 **B** 机：`chatmove` → **迁入** → 选文件。其余全自动。
4. 续接：`cd <打印出的路径> && claude --resume`——或直接打开 Claude 桌面端 app。

## 命令行参考
```bash
chatmove platforms                          # 列出本机探测到的平台
chatmove list                               # 列出本机 Claude Code 会话
chatmove export <session_id> -o my.cmove    # 无损打包(会话 + memory)
chatmove import my.cmove                     # 自动定位 + 路径重映射 + 登记
chatmove import my.cmove --target-cwd <路径> # 手动指定目标项目路径
chatmove ir <session_id>                     # 导出统一 IR(文本预览)
```
没 `pip install` 的话，`python -m chatmove ...` 等价。

## 工作原理
```
源平台 ──(adapter.export)──► [ .cmove / IR ] ──(adapter.import)──► 目标平台
```
- **路径重映射是灵魂。** 会话的项目目录名 = 项目绝对路径里把 `[A-Za-z0-9_-]` 之外的字符都换成 `-`(`/home/a/fast_lio`→`-home-a-fast_lio`；`C:\Users\you\fast_lio`→`C--Users-you-fast_lio`)，且 `.jsonl` 内多处内嵌 `cwd`。迁入时把源家目录前缀换成本机的、并转换分隔符，使**目录名和每一行 `cwd`** 都对上目标 Claude 的预期——这样 `--resume` 才接得上。
- **两套存储，都处理。** **CLI** 读 `~/.claude/projects/`；**桌面端 app** 读它自己的 `claude-code-sessions/.../local_*.json` 索引。`import` 写前者、登记 `~/.claude.json`，并(尽力)补后者。

## 适配器状态
| 平台 | 状态 | 说明 |
|---|---|---|
| **claude-code** | ✅ | list · 无损 export+import(跨系统路径重映射) · IR 导出 |
| chatgpt · claude.ai · cursor · codex · … | ⬜ 规划中 | 脚手架已就绪——见 [`docs/adding-an-adapter.md`](docs/adding-an-adapter.md) |

## 已知局限(诚实告知)
- **CLI `--resume` 是 100% 可靠的路径。** 它直接读 `~/.claude/projects/`，迁入后必然能用。
- **桌面端 app 的可见性是尽力而为。** app 自己管理会话索引，可能会清掉它不认识的条目。如果重启后会话出现在 *Recents* 里，点开一次让它"收编"就稳了；否则用 CLI。
- `.jsonl` 格式可能随 Claude Code 版本变化——适配器带 `version` 字段并做容错。

## 贡献
新增一个平台 = 围绕统一 IR 写**一个**适配器(读/写它的原生格式)。见 [`docs/adding-an-adapter.md`](docs/adding-an-adapter.md)。完整改动见 [`docs/CHANGELOG.md`](docs/CHANGELOG.md)。

## 状态
早期但可用：Claude Code 的**跨机 + 跨系统**无损迁移已经稳了。跨*平台*(不同 AI 工具之间)经由 IR 是下一步。
