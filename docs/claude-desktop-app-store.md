# Claude 桌面 App 的会话存储(与 CLI 不是同一套)

> 实测发现:`chatmove import` 只让会话出现在 **Claude Code CLI**(`claude --resume`),
> 但**不会**出现在 **Claude 桌面 App**(「Code」标签)的 Recents 列表里。
> 原因是两者用的是**两套独立的存储**。这里记录桌面 App 那套,供后续做 App 适配。

## 两套存储对照

| | 路径 | 会话标识 | 单条会话格式 |
|---|---|---|---|
| **CLI** | `~/.claude/projects/<项目路径名>/<uuid>.jsonl` | jsonl 文件名 = 会话 UUID | 完整 jsonl(`{"type":"user","message":{...},"cwd":...}`) |
| **桌面 App** | `~/Library/Application Support/Claude/claude-code-sessions/<账号id>/<项目id>/local_<uuid>.json` | `local_<uuid>` 元数据文件 | 一个小 JSON 索引,**指向** CLI 的 jsonl |

chatmove 目前只写 **CLI** 那一套(`projects/`)。这就是「CLI 能 `--resume`、App Recents 却看不到」的根因。

## 桌面 App 的 `local_<uuid>.json` 结构(实测,App ≈ v2.1.x)

```jsonc
{
  "sessionId": "local_39562758-e75b-4718-ad41-06d90bb077a3", // App 内部会话 id(与下面的 cli id 不同)
  "cliSessionId": "fdee1725-8fe1-48ae-83f4-6b8eec603877",     // 指向 ~/.claude/projects/<sanitize(cwd)>/<这个>.jsonl
  "cwd": "/Users/me/fastlio",
  "originCwd": "/Users/me/fastlio",
  "createdAt": 1781111386793,        // epoch 毫秒
  "lastActivityAt": 1781424526181,   // epoch 毫秒
  "lastFocusedAt": 1781424526181,    // epoch 毫秒;越大越靠 Recents 顶部
  "model": "claude-opus-4-8",
  "effort": "high",
  "title": "FAST-LIO SLAM",          // ← 这就是 Recents 里显示的标题
  "titleSource": "user",             // user / 自动生成
  "isArchived": false,
  "permissionMode": "auto",
  "completedTurns": 7,
  "remoteMcpServersConfig": [],
  "chromePermissionMode": "skip_all_permission_checks",
  "alwaysAllowedReasons": [],
  "sessionPermissionUpdates": [],
  "classifierSummaryEnabled": true,
  "spawnSeed": {}
}
```

要点:
- **App 的 Recents = 扫描这些 `local_*.json`**(逐个文件读 `title` 显示)。不是用某个数据库索引。
- `<账号id>/<项目id>` 两层目录都是 UUID,目录名里不含 cwd;同一项目下的多个会话放在同一个 `<项目id>` 目录里。
- 同目录下所有现有会话的 `cwd` 一致 → **App 很可能按项目(目录/或 cwd)分组**。跨 cwd 的会话可能落到另一个项目分组,而非当前窗口的 Recents。
- `IndexedDB/https_claude.ai_*.leveldb` 是 claude.ai 网页视图用的,**不含** Code 会话索引,排查时可忽略。

## 手动把一个已导入的 CLI 会话挂到 App(临时桥接)

`chatmove import pkg.cmove` 之后,再补一个 App 索引文件:

1. 找到账号/项目目录:
   `~/Library/Application Support/Claude/claude-code-sessions/<账号id>/<项目id>/`
   (拷贝一份同目录里已有的 `local_*.json` 当模板最省事。)
2. 新建 `local_<新uuid>.json`,改这几个字段:
   - `sessionId` → `local_<新uuid>`
   - `cliSessionId` → 导入会话的 UUID(= `projects/.../<这个>.jsonl`)
   - `cwd` / `originCwd` → 导入后的目标 cwd(要和 `projects/` 目录名 `sanitize(cwd)` 对得上)
   - `title` → 显示名
   - `createdAt` / `lastActivityAt` / `lastFocusedAt` → 毫秒时间戳
3. **完全退出 App(Cmd+Q)再重开**,Recents 才会重新扫描。

注意:这套结构是**逆向观察、未公开、随 App 版本可能变**。删掉这个 `local_*.json` 即可完全回退,不影响其它会话。

## 给 chatmove 的后续(TODO)

- 给 claude-code adapter 增加一个可选的「App 落地」步骤:CLI 导入后,自动在 `claude-code-sessions/` 下生成对应 `local_<uuid>.json`。
- 自动定位 `<账号id>/<项目id>`:扫已有 `local_*.json`,按 `cwd` 选/建对应项目目录。
- macOS 路径已知;Windows/Linux 上桌面 App 的对应目录待补(`%APPDATA%\Claude\...` / `~/.config/Claude/...` 待实测)。
