# Installing the Oniesoft Auto-Pilot Claude Code Plugin

This guide walks through installing **auto-pilot by Oniesoft** — a Claude Code plugin that connects Claude to the Oniesoft test automation platform via MCP tools.

---

## What you need before you start

| Requirement | Why | Download / docs |
|---|---|---|
| **Claude Code CLI** | Runs the plugin and Claude sessions | [Install Claude Code](https://code.claude.com/docs/en/install) |
| **uv** | The plugin's MCP server is launched with `uv run` (dependency install + Python runtime) | [uv installation](https://docs.astral.sh/uv/getting-started/installation/) |
| **Python 3.10+** | Required by the MCP server | Usually auto-installed by `uv` on first run; you can also install manually from [python.org](https://www.python.org/downloads/) |
| **Oniesoft platform access** | The plugin calls your platform API | A running Oniesoft instance (cloud or self-hosted) |
| **Personal API key** | Authenticates every API call (`x-api-key` header) | Generate in the platform: **Users → API Keys** |

### Install Claude Code CLI

**Recommended — native installer** (no Node.js required):

```bash
# macOS / Linux / WSL
curl -fsSL https://claude.ai/install.sh | bash

# Windows (PowerShell)
irm https://claude.ai/install.ps1 | iex
```

Other options: [Homebrew](https://brew.sh/), [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/), or the [npm package](https://www.npmjs.com/package/@anthropic-ai/claude-code) (requires Node.js 22+).

Verify:

```bash
claude --version
```

Full details: [code.claude.com/docs/en/install](https://code.claude.com/docs/en/install)

### Install uv

**Recommended — standalone installer:**

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternatives:**

```bash
# Homebrew (macOS)
brew install uv

# pip / pipx
pip install uv
# or
pipx install uv
```

Verify:

```bash
uv --version
```

Full details: [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/)

### Python 3.10+

You do **not** need to pre-install Python in most cases. On first session start, the plugin's bootstrap hook runs:

```bash
uv run --with-requirements server/requirements.txt --python ">=3.10" ...
```

`uv` downloads a compatible Python automatically if one is not already available.

To pre-install Python with uv (optional):

```bash
uv python install 3.12
```

Manual install: [python.org/downloads](https://www.python.org/downloads/) (choose 3.10 or newer).

---

## Install the plugin from the marketplace

The plugin is distributed through the **oniesoft** marketplace in this repository.

### Step 1 — Start Claude Code

Open a terminal in any project folder and start an interactive session:

```bash
cd /path/to/your/project
claude
```

### Step 2 — Add the marketplace

Inside the Claude Code session, register the marketplace catalog:

```
/plugin marketplace add https://bitbucket.org/onie-soft/auto-pilot-claude-plugin.git
```

**Shortcuts:** `/plugin market add` also works.

You can also add the marketplace from your shell (outside a session):

```bash
claude plugin marketplace add https://bitbucket.org/onie-soft/auto-pilot-claude-plugin.git
```

To use a local clone during development, point at the repo directory instead:

```
/plugin marketplace add /path/to/auto-pilot-claude-plugin
```

Verify the marketplace was added:

```
/plugin marketplace list
```

### Step 3 — Install the plugin

Inside a Claude Code session:

```
/plugin install auto-pilot@oniesoft
```

When prompted, choose an installation scope:

| Scope | Who gets the plugin |
|---|---|
| **User** | Only you, on this machine |
| **Project** | Everyone who clones this repo (written to `.claude/settings.json`) |
| **Local** | Only you, only in this project folder |

From the shell (non-interactive):

```bash
# User scope (available everywhere)
claude plugin install auto-pilot@oniesoft --scope user

# Project scope (shared with the team via git)
claude plugin install auto-pilot@oniesoft --scope project
```

### Step 4 — Enter your API key

The plugin declares one required setting: your **Oniesoft API key**.

#### Option A — Prompt on install (default)

When you enable the plugin for the first time, Claude Code prompts for **API key**. Because this field is marked `sensitive`, the value is stored securely (macOS Keychain, or `~/.claude/.credentials.json` on other platforms) — **not** in plain-text `settings.json`.

#### Option B — Pass the key during CLI install

```bash
claude plugin install auto-pilot@oniesoft --scope user --config platform_api_key=YOUR_API_KEY_HERE
```

#### Option C — Update later in the plugin UI

1. Run `/plugin` inside a Claude Code session.
2. Open the **Installed** tab.
3. Select **auto-pilot by Oniesoft**.
4. Edit the **API key** field and save.

> **Generate a key:** In the Oniesoft platform UI, go to **Profile → API Keys**. Create a key. A `401` from any tool means the key is missing or expired; a `403` means it lacks the required scope.

### Step 5 — Reload plugins (if needed)

After installation or config changes:

```
/reload-plugins
```

Or restart your Claude Code session.

On the first session start after install, the plugin automatically:

1. Bootstraps Python dependencies via `uv` (SessionStart hook).
2. Registers the MCP server with Claude Desktop (if installed).

---

## Configure your project

The API key is the **only** global plugin setting. Everything else is **per-project** and lives in a `config.json` file in the root of the project you are working in.

Download `config.json` and place it in your project folder. The downloaded file looks like this:

```json
{
  "companyId": "your-company-uuid",
  "projectId": "your-project-uuid",
  "userId": "your-user-uuid",
  "platformApiUrl": "https://your-platform-api.example.com",
  "backendUrl": "https://your-backend.example.com"
}
```

| Field | Description |
|---|---|
| `companyId` | Your Oniesoft company UUID |
| `projectId` | The test project UUID |
| `userId` | Your user/register UUID |
| `platformApiUrl` | Platform API base URL (e.g. `http://localhost:8000` for local dev) |
| `backendUrl` | Execution backend URL (e.g. `http://localhost:8088` for local dev) |

Claude reads this file at the start of each session. Pass these IDs explicitly on MCP tool calls — they are not auto-injected into every request.

To Download `config.json`:

1. Go to your Oniesoft platform and navigate to the project (Workspace) you want to work on.
2. Click the **Download config** button to download `config.json`.

---

## Verify the installation

### 1. Check the plugin is enabled

```
/plugin
```

Go to **Installed** → confirm **auto-pilot by Oniesoft** is listed and enabled.

### 2. Check MCP tools are available

Ask Claude in your session:

> List the available auto-pilot MCP tools.

You should see tools like `save_claude_test_cases`, `run_test_case`, `fetch_test_run_results`, etc.

### 3. Smoke-test an API call

With `config.json` in place, ask Claude:

> Call `get_projects_assigned_to_user` for my user.

A successful response confirms the API key, URLs, and project config are wired up correctly.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `uv: command not found` | uv not installed or not on `PATH` | Install uv (see above) and restart your shell |
| MCP server fails to start | Python/deps not bootstrapped | Start a new session (SessionStart hook runs bootstrap); or run manually: `uv run --with-requirements server/requirements.txt --python ">=3.10" server/launch.py --bootstrap-only` from the plugin root |
| `401` on tool calls | Missing or expired API key | Re-enter the key via `/plugin` → Installed → auto-pilot |
| `403` on tool calls | API key lacks scope | Regenerate the key with `generate` / `run` / `read` scopes |
| `No project_id given...` | Missing `config.json` | Add `config.json` to your project root with `projectId`, `companyId`, `userId` |
| Plugin not found after install | Marketplace cache stale | `/plugin marketplace update oniesoft`, then retry install |
| Marketplace not found | Marketplace not registered | Run `/plugin marketplace add` with the repo URL again |

For more on Claude Code plugins: [Discover and install plugins](https://code.claude.com/docs/en/discover-plugins)

---

## Quick reference

```bash
# 1. Prerequisites
curl -fsSL https://claude.ai/install.sh | bash    # Claude Code
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv

# 2. Inside a Claude Code session
/plugin marketplace add https://bitbucket.org/onie-soft/auto-pilot-claude-plugin.git
/plugin install auto-pilot@oniesoft
# → enter API key when prompted
/reload-plugins

# 3. In your project folder — create config.json with company/project/user IDs and API URLs
```
