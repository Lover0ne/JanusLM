---
name: privacy-mode
description: Install and configure privacy mode for local PII anonymization. Activated by natural language ("enable privacy mode", "anonymize everything", "don't send data externally") or via /privacy-mode. Downloads the OpenAI Privacy Filter model and sets up the maskzone/ pipeline.
---

# Privacy Mode

> *No PII leaves the machine.*

You have been invoked to set up, toggle, or verify privacy mode.
Follow these steps exactly.

## Step 0 — Check current state

Run:

```bash
python tools/privacy_filter.py --status
```

This tells you:
- Whether privacy mode is currently active or inactive
- Whether dependencies are installed (`.privacy-deps-ok` exists)
- Whether `maskzone/` exists and how many files are pending

Based on the result, follow the appropriate flow below:

| Current state | User wants | → Flow |
|---|---|---|
| inactive + deps NOT installed | enable | **First-time activation** |
| inactive + deps installed | enable | **Reactivation** |
| active | disable | **Deactivation** |
| active | enable | Already active — just confirm to the user |

---

## Flow A — First-time activation

### A1 — Explain and confirm

Tell the user what will happen:
- Privacy mode anonymizes all PII locally before any data reaches external agents
- Documents go in `maskzone/` instead of `raw/`
- A local model (OpenAI Privacy Filter, Apache 2.0) runs on-device via ONNX Runtime
- Originals stay in `maskzone/` after processing — the user removes them manually when ready
- First-time setup requires downloading the model (~17 GB, cached in `~/.cache/huggingface/`)
  and installing Python dependencies

**Ask the user for confirmation before proceeding.**

### A2 — Install dependencies

Run:

```bash
pip install -r requirements-privacy.txt
```

If `pip` is not found, try `pip3` or `python -m pip`.

If the installation fails:
- Report the exact error to the user
- On Windows with permission errors, suggest: `pip install --user -r requirements-privacy.txt`
- Do NOT proceed to A3 if installation failed

### A3 — Verify imports

Run:

```bash
python -c "import transformers, docx, pdfplumber, pptx, openpyxl, bs4; print('ALL_PRIVACY_DEPS_OK')"
```

If the output contains `ALL_PRIVACY_DEPS_OK`, proceed to A4.

If any import fails, report which package failed and re-run
`pip install <package>` for that specific package. Then verify again.

**Note:** `onnxruntime` and `optimum` are optional (ONNX acceleration). The script
automatically falls back to standard PyTorch inference if they are unavailable.

### A4 — Download model and activate

Run:

```bash
python tools/privacy_filter.py --setup
```

This downloads the model, runs a test inference, creates `.privacy-deps-ok`,
sets `can_anonymize_pii` to `true` in `wiki/.protect`, and creates `maskzone/`.

If setup fails:
- Network error → check internet connection, retry
- Model error → report and suggest retrying
- Do NOT proceed if setup failed

### A5 — Report

Tell the user:
- Privacy mode is now active
- Place files in `maskzone/` instead of `raw/`
- All files will be anonymized locally before any external agent or service can access them
- Originals stay in `maskzone/` — remove them manually when no longer needed
- To disable: say "disable privacy mode"
- To check status: `python tools/privacy_filter.py --status`

---

## Flow B — Reactivation

Dependencies and model are already installed. No download needed.

### B1 — Explain and confirm

Tell the user:
- Privacy mode will be reactivated
- Dependencies and model are already cached — no reinstallation needed
- Documents will go in `maskzone/` and be anonymized locally

**Ask the user for confirmation before proceeding.**

### B2 — Toggle flag

Run:

```bash
python tools/wiki_protect.py --toggle can_anonymize_pii
```

### B3 — Report

Tell the user privacy mode is active again. Same usage as A5.

---

## Flow C — Deactivation

### C1 — Explain and confirm

Tell the user:
- Privacy mode will be disabled
- Ingest workflow returns to normal (files go in `raw/`)
- Dependencies and model stay cached (no re-download needed to reactivate)

**Ask the user for confirmation before proceeding.**

### C2 — Toggle flag

Run:

```bash
python tools/wiki_protect.py --toggle can_anonymize_pii
```

### C3 — Report

Tell the user privacy mode is disabled and can be reactivated at any time.
