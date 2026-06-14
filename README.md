# chatmove

> Move your AI chat sessions across machines and platforms — **export** on one box, **import** on another, and pick up exactly where you left off.

**English** · [中文](README.zh-CN.md)

**The problem.** Claude Code stores every conversation locally (`~/.claude/projects/<dir>/*.jsonl`) and never syncs it to your account. Switch laptops — or move from a Linux box to a Mac — and all that context is gone. **chatmove** packs a session (plus its project memory) into a single `.cmove` file, then unpacks it on the target machine, rewriting the embedded absolute paths so `claude --resume` just works.

## Features
- **One-command wizard** — run `chatmove`, pick a number, done. No flags, no paths to type.
- **Lossless same-tool migration** — copies the raw session files and remaps every embedded `cwd`, so the target machine can `--resume` with full context intact.
- **Cross-OS** — Linux ⇄ macOS ⇄ Windows. Path separators, drive letters and the project-dir naming rule are translated to the target OS automatically.
- **Auto-locate & auto-register** — finds the local Claude store by `$HOME`, registers the project in `~/.claude.json`, and (best-effort) adds the desktop-app index so the session appears in **both** the CLI and the desktop app.
- **Pure standard library** — zero third-party dependencies. If you have Python 3.9+, it runs.
- **Adapter architecture** — one adapter per platform around a shared IR. N platforms = N adapters, not N² converters.

## Install
```bash
# Option A — install the `chatmove` command
pip install git+https://github.com/lalala518418/chatmove.git

# Option B — run straight from a clone (no install needed, it's pure stdlib)
git clone https://github.com/lalala518418/chatmove.git
cd chatmove
python  -m chatmove     # Windows
python3 -m chatmove     # macOS / Linux
```

## Quick start — one command
Run it and follow the numbered prompts (export ⇆ import → platform → conversation):
```bash
chatmove                # or:  python -m chatmove
```

**Move a session from machine A to machine B:**
1. On **A**:  `chatmove` → **export** → pick the conversation → it writes `~/<id>.cmove`.
2. Copy that `.cmove` to **B** (AirDrop / USB / scp / cloud).
3. On **B**:  `chatmove` → **import** → pick the file. Everything else is automatic.
4. Resume:  `cd <printed path> && claude --resume`  — or just open the Claude desktop app.

## Command-line reference
```bash
chatmove platforms                          # list platforms detected on this machine
chatmove list                               # list local Claude Code sessions
chatmove export <session_id> -o my.cmove    # lossless package (session + memory)
chatmove import my.cmove                     # auto-locate + path-remap + register
chatmove import my.cmove --target-cwd <path> # override the target project path
chatmove ir <session_id>                     # dump the cross-platform IR (text preview)
```
`python -m chatmove ...` works identically if you didn't `pip install`.

## How it works
```
source platform ──(adapter.export)──► [ .cmove / IR ] ──(adapter.import)──► target platform
```
- **Path remap is the heart of it.** A session's project dir is its absolute path with every char outside `[A-Za-z0-9_-]` turned into `-` (`/home/a/fast_lio` → `-home-a-fast_lio`; `C:\Users\you\fast_lio` → `C--Users-you-fast_lio`), and the `cwd` is embedded throughout the `.jsonl`. On import, chatmove swaps the source home-prefix for the local one and converts separators, so the dir name **and** every `cwd` line match what the target Claude expects — that's what makes `--resume` line up.
- **Two stores, both handled.** The **CLI** reads `~/.claude/projects/`; the **desktop app** reads its own `claude-code-sessions/.../local_*.json` index. `import` writes the first, registers the project in `~/.claude.json`, and (best-effort) adds the second.

## Adapter status
| Platform | Status | Notes |
|---|---|---|
| **claude-code** | ✅ | list · lossless export+import (cross-OS path remap) · IR export |
| chatgpt · claude.ai · cursor · codex · … | ⬜ planned | scaffolding ready — see [`docs/adding-an-adapter.md`](docs/adding-an-adapter.md) |

## Caveats (honest)
- **CLI `--resume` is the reliable path.** It reads `~/.claude/projects/` directly; after import it always works.
- **Desktop-app visibility is best-effort.** The app manages its own session index and may prune entries it doesn't recognise. If the imported session appears in *Recents* after a restart, open it once to make it stick; otherwise fall back to the CLI.
- The `.jsonl` format can change between Claude Code versions — adapters carry a `version` field and degrade gracefully.

## Contributing
Adding a platform = writing **one** adapter (read/write its native format) around the shared IR. See [`docs/adding-an-adapter.md`](docs/adding-an-adapter.md). Full history in [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

## Status
Early but working: lossless cross-machine **and cross-OS** migration for Claude Code is solid. Cross-*platform* (between different AI tools) via the IR is the next frontier.
