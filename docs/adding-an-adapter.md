# 添加一个新平台适配器

每个平台 = 一个 `Adapter` 子类(放在 `chatmove/adapters/`)，围绕统一 IR 工作。

## 必须实现
- `name`: 平台标识，如 `"chatgpt"`。
- `list_conversations() -> list[ConvRef]`：列出本机/导出文件里的会话。
- `export_ir(conv_id) -> Conversation`：原生格式 → 统一 IR(`chatmove/ir.py`)。

## 可选(同平台无损迁移)
- `export_package(conv_id, out_path)`：打包原始文件(保真)。
- `import_package(pkg_path, **target_opts)`：解包 + 必要的路径/ID 重映射。
> 无损迁移仅适用于"同平台跨机"(如 Claude Code → 另一台 Claude Code)。跨平台只能走 IR。

## 注册
在 `chatmove/adapters/__init__.py` 的 `ADAPTERS` 列表里加上你的适配器实例。

## 候选平台(欢迎贡献)
- **chatgpt**：用户从 ChatGPT 导出的 `conversations.json`(已有公开格式)。
- **claude.ai**：网页端导出。
- **cursor / 其它 CLI agent**：多半也是本地 jsonl/sqlite，思路同 claude-code。

## 设计原则
- 同平台优先无损(原样搬+重映射)；跨平台才降到 IR(保文本)。
- 适配器只管"读写自己的格式"，不关心其它平台——N 个平台 = N 个适配器。
- 注意各平台格式可能随版本变，做容错 + 记录来源 version。
