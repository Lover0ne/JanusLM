---
name: converter
description: Convert non-markdown files to markdown for wiki ingest. Use when the ingest workflow encounters a file that is not .md (docx, xlsx, pptx, pdf, txt, csv, json, html, xml, etc.).
---

# File Converter

You are the file converter. Your job is to transform non-markdown files into clean,
faithful markdown before they enter the ingest pipeline.

## Converter Workflow

Triggered by: maintainer skill when a file in the ingest queue is not `.md`, or `/convert`

### Step 1 — Identify format

Check the file extension. Classify as:
- **Binary** (docx, xlsx, pptx, pdf, etc.) — requires a Python script to extract content
- **Text** (txt, csv, json, html, xml, etc.) — readable with Read tool

### Step 2 — Convert

**For binary files:**

1. Write a conversion script `.staging/convert_<slug>.py` that:
   - Uses an appropriate Python library for the format
   - Reads the original file
   - Extracts all text content (including tables, headings, lists)
   - Writes UTF-8 encoded markdown to `raw/<slug>.md`
2. Run the script: `python .staging/convert_<slug>.py`
3. If the library is not installed, install it: `pip install <library>`

**For text files:**

1. Read the file using the Read tool
2. Transform the content to well-structured markdown
3. Write the result to `raw/<slug>.md`

### Step 3 — Validate (ALWAYS required)

Write a validation script `.staging/validate_<slug>.py` that:
- Opens the original file (using the same library for binaries, or plain read for text)
- Opens the converted `.md` file
- Compares: line/paragraph count, encoding (must be UTF-8), structural completeness
- Outputs JSON to stdout:

```json
{
  "status": "PASS",
  "original_file": "raw/report.docx",
  "converted_file": "raw/report.md",
  "original_lines": 847,
  "converted_lines": 847,
  "encoding": "utf-8"
}
```

Or on failure:

```json
{
  "status": "FAIL",
  "original_file": "raw/report.docx",
  "converted_file": "raw/report.md",
  "original_lines": 847,
  "converted_lines": 812,
  "missing_content": [
    "Table at line 234 not converted",
    "Footnote 3 missing"
  ]
}
```

Run: `python .staging/validate_<slug>.py`

### Step 4 — Fix loop

If validation returns FAIL:
- For binary: fix the conversion script, re-run convert, re-run validate
- For text: fix the `.md` file, re-run validate
- Repeat until PASS

### Step 5 — Clean up

Delete all scripts from `.staging/` using the Recycle Bin:
```
powershell -Command "Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('<absolute_path>', 'OnlyErrorDialogs', 'SendToRecycleBin')"
```

The `.staging/` directory must be empty when you're done.

### Step 6 — Log (standalone only)

If the converter was invoked standalone (via `/convert`, not as part of ingest):

```bash
python tools/log_write.py --op convert --title "<original filename> → <slug>.md"
```

If invoked from ingest step 4, skip this — the ingest workflow logs the full operation.

### Step 7 — Return

The converted `.md` file is now in `raw/`. Return to the ingest workflow if applicable.

---

## Rules

- You are free to choose any Python library for conversion
- If a library is not installed, install it with `pip install`
- The validation script is **always mandatory** — for binary AND text files
- The validation is mechanical (line count, encoding, structure), not semantic
- Intermediate scripts are disposable — they live only during conversion
- `.staging/` must be empty at the end of the process
- Never modify the original file in `raw/`
- All output must be UTF-8 encoded
- Delete scripts using the Recycle Bin (global CLAUDE.md rule)
