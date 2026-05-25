# epo-oa-cli

**EPO patent prosecution history CLI** — Download, parse, and analyze European Patent Office (EPO) prosecution documents for AI-assisted patent analysis.

```bash
pip install epo-oa-cli
epo-oa run EP21841218
```

---

## Overview

`epo-oa` fetches the complete prosecution history of any EP patent from the [EPO Register](https://register.epo.org/), extracts PDF text (with optional OCR), and generates a structured `prosecution.md` file ready for AI analysis (Claude, GPT-4, etc.).

```
epo-oa run EP21841218
  → Downloads 40 documents as ZIP
  → Extracts & parses toc.xml
  → Generates file/EP21841218/EP21841218_prosecution.md
```

---

## Installation

```bash
pip install epo-oa-cli

# With OCR support (for image-based PDFs)
pip install "epo-oa-cli[ocr]"
```

Requires Python 3.13+.

---

## Quick Start

```bash
# 1. List all documents
epo-oa list EP21841218

# 2. Download as ZIP + extract
epo-oa download EP21841218

# 3. Parse PDFs → prosecution.md
epo-oa extract EP21841218

# 4. All-in-one
epo-oa run EP21841218
```

### With OCR (for image-based PDFs)

EPO PDFs are full-page image scans. Run OCR first to embed text into the analysis file:

```bash
# OCR key documents only
epo-oa ocr EP21841218 --codes 1703,1224,ABEX

# OCR all documents
epo-oa ocr EP21841218

# Extract with OCR text embedded
epo-oa extract EP21841218 --with-ocr
```

---

## Commands

| Command | Description |
|---------|-------------|
| `epo-oa list <EP>` | List prosecution documents from EPO Register |
| `epo-oa download <EP>` | Download all documents as ZIP archive |
| `epo-oa extract <EP>` | Parse PDFs → `prosecution.md` / `prosecution.json` |
| `epo-oa ocr <EP>` | OCR image-based PDFs → searchable `*_ocr.pdf` |
| `epo-oa run <EP>` | Download + extract in one step |

### Options

```bash
epo-oa list EP21841218 --format json          # JSON output
epo-oa download EP21841218 --force            # Re-download
epo-oa extract EP21841218 --format json       # JSON output
epo-oa extract EP21841218 --with-ocr          # Embed OCR text
epo-oa ocr EP21841218 --codes 1703,ABEX       # Selective OCR
epo-oa ocr EP21841218 --in-place              # Overwrite originals
```

---

## Output: `prosecution.md`

The generated markdown file is structured for AI agents:

```markdown
# EPO Prosecution Analysis — EP21841218

## Summary
| Item | Count |
|------|-------|
| Total documents | 40 |
| 🔴 Office Actions | 2 |
| 🔵 Amendments | 13 |
| ✅ Grant / Decision | 8 |

## Timeline
| Date | Cat | Document | File |
|------|-----|----------|------|
| 2023-10-30 | 🔍 | European Search Opinion (1703) 🖼️ | ... |
| 2024-02-15 | 🔵 | Amended Claims (CLMSABEX) 🖼️ | ... |
| 2026-02-05 | ✅ | Decision to Grant (2006A) 🖼️ | ... |

## 🔴 Office Action Documents
### European Search Opinion — 2023-10-30
**OCR Text:**
```text
D1 WO 2020/138918 A1 (SAMSUNG ELECTRONICS CO LTD)
1.1 D1 discloses an electronic device with the following features...
` `` `
```

---

## Politeness & Rate Limiting

This tool accesses a **public EPO server**. It enforces:
- Random delays (1.5–3.0s) between requests
- Browser-like headers
- ZIP archive download (minimises HTTP requests)

Please do not run this tool in tight loops or CI pipelines without appropriate throttling.

---

## Notes for AI Agents

- Image-only PDFs show `🖼️` — provide the `path` field directly to vision-capable models
- Run `epo-oa ocr` + `--with-ocr` to embed text for language models
- JSON output (`--format json`) includes full `path` and `text` fields for programmatic access
- The `prosecution.md` is designed to fit within typical LLM context windows for smaller dockets

---

## License

MIT
