---
name: janus-setup
description: Install and verify Python dependencies for JanusLM wiki tools. Invoked automatically when the UserPromptSubmit hook detects missing dependencies, or manually via /setup.
---

# 🏛️ JanusLM — First-Run Setup

> *"One face looks back at what's missing. The other looks forward to what's possible."*

You have been invoked because Python dependencies are not installed.
Follow these steps exactly, in order.

## Step 1 — Install

Run:

```bash
pip install -r requirements.txt
```

If `pip` is not found, try `pip3` or `python -m pip`.

If the installation fails:
- Report the exact error to the user
- Suggest creating a virtual environment: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- On Windows with permission errors, suggest: `pip install --user -r requirements.txt`
- Do NOT proceed to Step 2 if installation failed

## Step 2 — Verify

Run:

```bash
python -c "import networkx, sklearn, frontmatter, rapidfuzz; print('ALL_DEPS_OK')"
```

If the output contains `ALL_DEPS_OK`, proceed to Step 3.

If any import fails, report which package failed and re-run `pip install <package>` for that specific package. Then verify again.

## Step 3 — Create marker

Run:

```bash
python tools/scaffold.py --mark-deps
```

This marker file tells the hook to skip dependency checks in future sessions.

## Step 4 — Report

Print this banner, then list what was installed:

```
🏛️ JanusLM is ready.
   Knowledge and action, in a loop.
```

Tell the user:
- Dependencies installed successfully
- They can now use all wiki tools (`/wiki-ingest`, `/wiki-query`, `/wiki-health`, `/wiki-graph`)
- If they ever need to reinstall, they can run `/setup` or delete `.deps-ok`

Then proceed with whatever the user originally asked for.
