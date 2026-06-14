# 改动日志

## v0.3.1 — 修复目录名把下划线错改成 '-'（带 '_' 的项目 --resume 对不上）

**背景**：把一台 Mac（`/Users/aolos/Downloads/secret_subject`）的会话迁到 Windows，
项目目录被建成 `C--Users-yunlong-Downloads-secret-subject`（下划线变成了 '-'），
而 Claude Code 实际找的是 `...secret_subject`，于是 `--resume` 对不上、桌面端也错位。

- **根因**：`sanitize_cwd` 用了 `[^A-Za-z0-9]→'-'`，把下划线也替换了。
- **真相**：从本机 Claude Code 二进制里挖出它自己的编码器是
  `replace(/[^a-zA-Z0-9\-_]/g, "-")` —— **保留下划线 '_' 和连字符 '-'**，其余才变 '-'。
- **修复**：`sanitize_cwd` 改为 `[^A-Za-z0-9_-]→'-'`，与 Claude Code 完全一致。
- 验证：Mac→Windows 带下划线路径 import 后，目录名为 `...secret_subject`，cwd 全部正确
  重映射（非家目录下的路径如 `/private/tmp` 按设计保持不变），桌面端索引也正常生成。

### 同版附带：桌面端索引检测加固
- **现象**：有时 import 报"未发现桌面端 app 数据"，但目录其实存在。根因：桌面 app 会
  把"活动会话"的 `local_*.json` 动态清掉，目录瞬时为空；旧检测要求"目录里已有 local 文件"
  才认，空目录被跳过。
- **修复**：`_find_desktop_session_dir` 不再要求已有 local 文件，改用
  `cowork-enabled-cli-ops.json` 的 `ownerAccountId` + workspace 目录结构定位（空目录也行），
  并在跳过时**打印具体原因**而非笼统的"未发现"，便于排查。
- **已知局限(诚实告知)**：桌面 app 会主动清理它不认识的"孤儿"索引——注入的索引若在用户
  点开前被 app 同步剪掉就会丢。CLI `claude --resume` 不受此影响，始终可用。

## v0.3.0 — 桌面端 app 也能"看见"迁移的会话（跨 Win/macOS/Linux）

**背景**：v0.2 修好后，CLI `claude --resume` 能续接，但 **Claude 桌面端 app 的
Recents 列表里还是看不到**迁移的会话。挖下去发现：

- **桌面端 app 不扫 `~/.claude/projects/`**。它的会话列表读自己的索引文件：
  `<配置根>/claude-code-sessions/<accountId>/<workspaceId>/local_<uuid>.json`，
  每个文件一条会话，靠 `cliSessionId` 指回 projects 里的 jsonl。CLI 放进 projects/
  的会话，桌面端因为没这条索引而不显示。

### 修复：import 自动补桌面端索引
- 新增 `register_desktop_session()`：import 时自动在桌面端的会话目录里生成一条
  `local_*.json`（`cliSessionId` 指向迁入的会话、`cwd` 用重映射后的本机路径、
  `lastFocusedAt` 设为当前时间好排在顶部）。重启 app 后即出现在 Recents。
- **去重**：已存在同 `cliSessionId` 的索引则不重复创建。
- **安全**：样本里的 `permissionMode:auto` + `chromePermissionMode:skip_all_permission_checks`
  是"跳过所有权限确认"的后门，**新建索引绝不照抄**——用 `permissionMode:"default"`、
  不写 chromePermissionMode。
- **跨系统配置根**（`_desktop_config_roots`）：
  - Windows：`%APPDATA%\Claude`
  - macOS：`~/Library/Application Support/Claude`
  - Linux：`~/.config/Claude`（或 `$XDG_CONFIG_HOME/Claude`）
- 不猜 `accountId/workspaceId`，直接复用 app 已建好、且已有 `local_*.json` 的目录
  （取最近活跃的那个），最稳。桌面端没装/没用过则跳过，不影响 CLI `--resume`。

## v0.2.0 — 跨系统（Linux ↔ Windows）迁移修复

**背景**：用 v0.1 把一台 Linux 机（`/home/a/fastlio`）的 Claude Code 会话导出成
`.cmove`，拿到 Windows 上 `import`，会失败/放错位置，而且即使文件放对了，会话
也不出现在 Claude Code 的 app/CLI 列表里。定位到三个根因，逐个修掉：

### 1. 项目目录命名只支持 Linux（致命）
- **问题**：`pathmap.sanitize_cwd` 只把 `/` 换成 `-`。但 Windows 上 Claude Code 的
  项目目录名是把**盘符冒号 `:`、反斜杠 `\`、点 `.`** 等非字母数字字符都换成 `-`
  （例：`C:\Users\you\Downloads` → `C--Users-you-Downloads`）。Linux 规则套到
  Windows 会生成非法目录名，落不到正确位置。
- **修复**：`sanitize_cwd` 改为逐字符把 `[^A-Za-z0-9]` 替换成 `-`，与本机 Claude Code
  一致，三个平台通吃。

### 2. 家目录重映射不转分隔符（致命）
- **问题**：`remap_home` 直接字符串拼接 `new_home + tail`，把 Linux 的 `/home/a/fastlio`
  映射成 `C:\Users\you/fastlio`（混合斜杠），路径无效。
- **修复**：新增 `remap_path`：剥掉源家目录前缀后，按 `[/\\]` 拆成路径段，再用
  `os.path.join` 以**本机分隔符**重组，跨系统双向都对。`remap_home` 保留为别名向后兼容。
- 顺带：`import` 现在对 jsonl **每一行的 cwd** 都按家目录前缀重映射（之前只精确匹配
  主 cwd），所以子目录 cwd（如 `.../FAST_LIO-main`）也能正确改写。

### 3. 没登记到 `~/.claude.json`（会话"看不见"的真凶）
- **问题**：会话 jsonl 放对了，但 Claude Code 的 app/CLI 靠 `~/.claude.json` 的
  `projects` 表识别项目。没登记 → 会话不出现在列表/Recents 里，用户以为没迁成功。
- **修复**：新增 `register_project(cwd)`，`import` 时自动把目标 cwd 写进 `projects` 表
  （带 `hasTrustDialogAccepted: true`，免信任弹窗）；首次改动会留 `.chatmove-bak` 备份；
  表缺失/解析失败则跳过并提示（不致命，`--resume` 仍可用）。

### 4. 杂项 polish
- `__main__.py`：Windows 控制台切 UTF-8，修中文输出乱码。
- 解包 memory/ 增加 tar 路径穿越防护（`_safe_members`：拒绝绝对路径和 `..`）。

**结论**：现在 `python -m chatmove import x.cmove` 在 Windows 上能一键自动完成
Linux→Windows 的无损迁移并自动出现在列表里，无需手填路径。
