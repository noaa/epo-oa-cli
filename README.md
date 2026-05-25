# EPO Register Document Downloader (EPO OA Downloader)

A premium, interactive CLI tool built with Python to safely and efficiently download patent prosecution history documents ("EP All documents") from the **European Patent Register (EPO)**.

This utility is carefully designed with **Rate Limiting & Politeness** mechanisms in mind to prevent overloading the public servers while providing a harmonious user experience.

---

## Features

- **Dynamic Metadata Parsing**: Fetches the complete table of documents (Date, Document Type, Procedure, Pages) for any specified European patent.
- **Harmonious Terminal UI**: Uses `rich` to render elegant status spinners, stylized metadata tables, and smooth download progress bars.
- **Three Versatile Download Modes**:
  1. **ZIP Archive (Recommended)**: Bundles all selected/complete documents into a single ZIP archive *server-side*. Highly recommended as it minimises the number of HTTP requests.
  2. **Merged PDF**: Merges all selected documents into a single, comprehensive PDF document.
  3. **Individual PDFs**: Downloads each document separately with custom, structured filenames (e.g. `01_20181212_Refund_of_fees.pdf`).
- **Politeness & Rate Limiting Built-in**:
  - Automatically simulates browser behaviour using customised headers (User-Agent, Accept-Language).
  - Enforces **random delays (1.5s ~ 3.0s)** between sequential file downloads in individual mode to safeguard against IP blocking.
- **Non-interactive Automation Support**: Supports command-line arguments to completely bypass interactive prompts for headless scripting or CI/CD pipelines.

---

## Prerequisites

This project utilizes [uv](https://github.com/astral-sh/uv), a fast Python package installer and resolver. Please ensure you have `uv` installed on your machine.

---

## Installation

You do not need to manually configure virtual environments. `uv` will automatically manage virtual environments and dependencies upon execution.

However, if you wish to pre-install dependencies, run the following in the project root:
```bash
uv pip install -r pyproject.toml
```

---

## Usage

By default, all downloaded outputs (ZIPs, PDFs) and scripts are backed up under the `./temp` directory to keep your workspace clean.

### 1. Interactive Mode
Run the script without any arguments. You will be prompted to enter the patent number and select the download mode dynamically.
```bash
uv run python main.py
```
- **Step 1**: Enter the target patent application number (e.g., `EP16183755`).
- **Step 2**: Choose a download option (0-3) from the interactive prompt.

### 2. Automated Mode (Command Line Arguments)
Bypass all interactive prompts by providing the patent number and the download option code as positional arguments:
```bash
uv run python main.py <PATENT_NUMBER> <DOWNLOAD_MODE_CODE>
```

#### Download Mode Codes:
- `1`: **ZIP Archive Download** (Highly recommended & server-friendly)
- `2`: **Merged PDF Download** (Single combined PDF)
- `3`: **Individual PDFs Download** (Downloads each file one-by-one with politeness delays)
- `0`: **Exit**

#### Examples:
```bash
# Download all documents for EP16183755 as a server-side zipped archive
uv run python main.py EP16183755 1

# Download all documents for EP16183755 as a single merged PDF
uv run python main.py EP16183755 2

# Download all documents as individual PDFs with rate-limiting protection
uv run python main.py EP16183755 3
```

---

## Backup & Directory Structure
When executed, the project maintains the following layout:
- `./temp/main.py`: Current production script.
- `./temp/pyproject.toml`: Dependency configuration.
- `./temp/EP16183755_all_documents.zip`: Downloaded ZIP archive.
- `./temp/EP16183755_individual_pdfs/`: Individual PDF files folder (when option 3 is executed).
