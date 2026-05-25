"""EPO patent prosecution CLI."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from epo_oa import __version__
from epo_oa.register import (
    download_zip,
    extract_zip,
    fetch_document_list,
    normalize_app_number,
)

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="epo-oa")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose logging.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """EPO patent prosecution history CLI.

    \b
    Quick start:
      epo-oa list EP21841218            # List documents
      epo-oa download EP21841218        # Download ZIP archive
      epo-oa extract EP21841218         # Parse PDFs → prosecution.md
      epo-oa run EP21841218             # All-in-one: download + extract
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(stream=sys.stderr, level=level, format="%(levelname)s  %(message)s")

    if ctx.invoked_subcommand is None:
        console.print(Panel(
            f"[bold green]EPO Patent Prosecution CLI[/bold green]  v{__version__}\n"
            "[dim]European Patent Register document downloader & analyzer[/dim]\n\n"
            "  [bold cyan]epo-oa list[/bold cyan] EP21841218\n"
            "  [bold cyan]epo-oa download[/bold cyan] EP21841218\n"
            "  [bold cyan]epo-oa extract[/bold cyan] EP21841218\n"
            "  [bold cyan]epo-oa run[/bold cyan] EP21841218",
            title="epo-oa",
            border_style="green",
        ))


# ── list ─────────────────────────────────────────────────────────────────────

@main.command("list")
@click.argument("application")
@click.option("--format", "fmt", default="table",
              type=click.Choice(["table", "json"]), help="Output format (default: table).")
def list_docs(application: str, fmt: str) -> None:
    """List prosecution documents from EPO Register.

    \b
    Examples:
      epo-oa list EP21841218
      epo-oa list EP21841218 --format json
    """
    import json as _json

    from rich.console import Console as _Console

    app_num = normalize_app_number(application)
    err_console = _Console(stderr=True)
    err_console.print(f"[dim]Fetching document list for {app_num}...[/dim]")

    docs = fetch_document_list(app_num)
    if not docs:
        err_console.print(f"[red]No documents found for {app_num}.[/red]")
        raise SystemExit(1)

    if fmt == "json":
        click.echo(_json.dumps(
            [{"index": d["index"], "date": d["date"], "code": d["code"],
              "label": d["label"], "procedure": d["procedure"], "pages": d["pages"]}
             for d in docs],
            indent=2, ensure_ascii=False,
        ))
        return

    table = Table(
        title=f"EPO Register — {app_num}  ({len(docs)} documents)",
        title_style="bold cyan",
        header_style="bold magenta",
        border_style="dim blue",
        expand=True,
    )
    table.add_column("#", justify="center", style="dim", width=5)
    table.add_column("Date", justify="center", style="green", width=12)
    table.add_column("Document Type", style="white")
    table.add_column("Procedure", style="yellow")
    table.add_column("Pages", justify="right", style="cyan", width=6)

    for d in docs:
        table.add_row(
            str(d["index"]),
            d["date"],
            d["label"],
            d["procedure"],
            d["pages"],
        )

    console.print(table)
    console.print(f"[bold green]Total: {len(docs)} documents[/bold green]")


# ── download ──────────────────────────────────────────────────────────────────

@main.command()
@click.argument("application")
@click.option("--output-dir", default=None, metavar="DIR",
              help="Output directory (default: ./file/{app_num}/).")
@click.option("--force", is_flag=True, default=False,
              help="Re-download even if file already exists.")
@click.option("--no-extract", is_flag=True, default=False,
              help="Keep ZIP without extracting.")
def download(application: str, output_dir: str | None, force: bool, no_extract: bool) -> None:
    """Download all documents as ZIP archive.

    \b
    Examples:
      epo-oa download EP21841218
      epo-oa download EP21841218 --output-dir ./my_patents
      epo-oa download EP21841218 --force
    """
    app_num = normalize_app_number(application)
    out_dir = output_dir or str(Path.cwd() / "file" / app_num)
    zip_dir = str(Path(out_dir).parent)  # ZIP은 상위에 저장
    extract_dir = out_dir  # PDF는 app_num 폴더에 저장

    console.print(f"[bold]Application:[/] {app_num}")
    console.print(f"[bold]Output:[/] {extract_dir}")
    console.print()

    # 문서 목록 조회
    with console.status("[yellow]Fetching document list...[/yellow]"):
        docs = fetch_document_list(app_num)

    if not docs:
        console.print(f"[red]No documents found for {app_num}.[/red]")
        raise SystemExit(1)

    console.print(f"[green]Found {len(docs)} documents[/green]")

    # ZIP 다운로드 (Progress bar)
    zip_path_str = Path(zip_dir) / f"{app_num}_all_documents.zip"
    if zip_path_str.exists() and not force:
        console.print(f"[dim]ZIP already exists: {zip_path_str}[/dim]")
    else:
        from epo_oa.register import _make_session, _politeness_delay, DOWNLOAD_URL

        doc_ids = [d["id"] for d in docs]
        payload = {
            "documentIdentifiers": "+".join(doc_ids),
            "number": app_num,
            "unip": "false",
            "output": "zip",
        }

        Path(zip_dir).mkdir(parents=True, exist_ok=True)
        _politeness_delay(1.0, 2.0)
        session = _make_session()

        try:
            response = session.post(DOWNLOAD_URL, data=payload, stream=True, timeout=60)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Downloading {app_num}_all_documents.zip",
                    total=total_size or None,
                )
                with open(zip_path_str, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))

            console.print(f"\n[green]Downloaded:[/] {zip_path_str}")

        except Exception as e:
            console.print(f"[red]Download failed:[/] {e}")
            raise SystemExit(1)

    if no_extract:
        console.print("[dim]Skipping extraction (--no-extract).[/dim]")
        return

    # ZIP 압축 해제
    with console.status(f"[yellow]Extracting to {extract_dir}...[/yellow]"):
        extract_zip(str(zip_path_str), extract_dir)

    console.print(f"[green]Extracted:[/] {extract_dir}")
    console.print(
        f"\n[dim]Next step:[/dim] [bold]epo-oa extract {app_num}[/bold]"
    )


# ── extract ───────────────────────────────────────────────────────────────────

@main.command()
@click.argument("application")
@click.option("--file-dir", default=None, metavar="DIR",
              help="Directory containing extracted files (default: ./file/{app_num}/).")
@click.option("--format", "fmt", default="md",
              type=click.Choice(["md", "json"]), help="Output format (default: md).")
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Output file path (default: {file_dir}/{app_num}_prosecution.md).")
@click.option("--with-ocr", is_flag=True, default=False,
              help="Embed OCR text from *_ocr.pdf files (requires prior 'epo-oa ocr' run).")
def extract(
    application: str,
    file_dir: str | None,
    fmt: str,
    output: str | None,
    with_ocr: bool,
) -> None:
    """Parse downloaded PDFs and generate prosecution.md for AI analysis.

    \b
    Reads toc.xml + PDFs from the extracted ZIP directory.
    EPO PDFs are image-based scans — run 'epo-oa ocr' first to enable text embedding.

    \b
    Examples:
      epo-oa extract EP21841218
      epo-oa extract EP21841218 --format json
      epo-oa extract EP21841218 --with-ocr
      epo-oa extract EP21841218 --output ./analysis/EP21841218.md
    """
    from epo_oa.parse import extract as do_extract

    app_num = normalize_app_number(application)
    src_dir = file_dir or str(Path.cwd() / "file" / app_num)
    out_ext = "json" if fmt == "json" else "md"
    out_path = output or str(Path(src_dir) / f"{app_num}_prosecution.{out_ext}")

    if not Path(src_dir).exists():
        console.print(f"[red]Directory not found:[/] {src_dir}")
        console.print(f"[dim]Run 'epo-oa download {app_num}' first.[/dim]")
        raise SystemExit(1)

    console.print(f"[bold]Application:[/] {app_num}")
    console.print(f"[bold]Source:[/] {src_dir}")
    console.print(f"[bold]Output:[/] {out_path}")
    if with_ocr:
        console.print("[dim]OCR text embedding: enabled[/dim]")
    console.print()

    with console.status("[yellow]Parsing documents and extracting text...[/yellow]"):
        content = do_extract(
            app_num, file_dir=src_dir, output_path=out_path, fmt=fmt, with_ocr=with_ocr
        )

    console.print(f"[bold green]Done:[/] {out_path}")
    console.print(
        "[dim]Pass this file to Claude or another AI agent for prosecution analysis.[/dim]"
    )


# ── ocr ───────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("application")
@click.option("--file-dir", default=None, metavar="DIR",
              help="Directory containing PDFs (default: ./file/{app_num}/).")
@click.option("--force", is_flag=True, default=False,
              help="Re-OCR even if *_ocr.pdf already exists.")
@click.option("--in-place", is_flag=True, default=False,
              help="Overwrite original PDFs instead of creating *_ocr.pdf copies.")
@click.option("--codes", default=None, metavar="CODES",
              help="Comma-separated codes to OCR (e.g. 1703,ABEX). All PDFs if omitted.")
def ocr(
    application: str,
    file_dir: str | None,
    force: bool,
    in_place: bool,
    codes: str | None,
) -> None:
    """OCR image-based PDFs → searchable PDFs (requires: pip install ocrmypdf).

    \b
    EPO PDFs are full-page image scans — standard text extraction fails.
    This command runs OCR (English) on every PDF in the directory and produces
    searchable *_ocr.pdf files that 'epo-oa extract --with-ocr' can read.

    \b
    Examples:
      epo-oa ocr EP21841218
      epo-oa ocr EP21841218 --codes 1703,ABEX,1503SS
      epo-oa ocr EP21841218 --force
      epo-oa ocr EP21841218 --in-place
    """
    try:
        import ocrmypdf  # noqa: F401
    except ImportError:
        console.print("[red]ocrmypdf is not installed.[/]")
        console.print("[dim]Run: uv pip install 'epo-oa-cli[ocr]'  (or: pip install ocrmypdf)[/dim]")
        raise SystemExit(1)

    import warnings
    import logging as _logging

    app_num = normalize_app_number(application)
    src_dir = Path(file_dir or (Path.cwd() / "file" / app_num))

    if not src_dir.exists():
        console.print(f"[red]Directory not found:[/] {src_dir}")
        console.print(f"[dim]Run 'epo-oa download {app_num}' first.[/dim]")
        raise SystemExit(1)

    filter_codes = {c.strip().upper() for c in codes.split(",")} if codes else None

    pdfs = sorted(p for p in src_dir.glob("*.pdf") if not p.stem.endswith("_ocr"))
    if filter_codes:
        pdfs = [p for p in pdfs if _pdf_code(p) in filter_codes]

    if not pdfs:
        console.print("[yellow]No PDF files to process.[/yellow]")
        return

    console.print(f"[bold]Application:[/] {app_num}")
    console.print(f"[bold]Directory:[/] {src_dir}")
    console.print(f"[bold]Files to OCR:[/] {len(pdfs)}")
    console.print()

    for name in ("ocrmypdf", "ocrmypdf.stats", "pikepdf", "pikepdf._core"):
        _logging.getLogger(name).setLevel(_logging.ERROR)

    table = Table(title=f"OCR Results — {app_num}", show_lines=False)
    table.add_column("Input", style="cyan")
    table.add_column("Output")
    table.add_column("Status", justify="center")

    done = skipped = errors = 0
    for pdf in pdfs:
        if in_place:
            out_path = pdf
        else:
            out_path = pdf.with_stem(pdf.stem + "_ocr")

        if out_path.exists() and not force and not in_place:
            table.add_row(pdf.name, f"[dim]{out_path.name}[/dim]", "[dim]skipped[/dim]")
            skipped += 1
            continue

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import ocrmypdf as _ocr
                _ocr.ocr(
                    str(pdf), str(out_path),
                    language="eng",
                    deskew=True,
                    progress_bar=False,
                    quiet=True,
                )
            table.add_row(pdf.name, out_path.name, "[green]done[/green]")
            done += 1
        except Exception as e:
            table.add_row(pdf.name, f"[red]{str(e)[:40]}[/red]", "[red]error[/red]")
            errors += 1

    console.print(table)
    console.print(
        f"\n[bold green]{done} done[/] / [dim]{skipped} skipped[/] / "
        + (f"[red]{errors} errors[/]" if errors else "[dim]0 errors[/dim]")
    )
    if done > 0:
        console.print(
            f"\n[dim]Next step:[/dim] [bold]epo-oa extract {app_num} --with-ocr[/bold]"
        )


def _pdf_code(pdf_path: Path) -> str:
    """파일명에서 코드 추출: {appnum}-{YYYY}-{MM}-{DD}-{CODE}-{desc}.pdf."""
    parts = pdf_path.stem.split("-", 4)
    if len(parts) >= 5:
        return parts[4].split("-")[0].upper()
    return ""


# ── run (all-in-one) ──────────────────────────────────────────────────────────

@main.command()
@click.argument("application")
@click.option("--output-dir", default=None, metavar="DIR",
              help="Output directory (default: ./file/{app_num}/).")
@click.option("--format", "fmt", default="md",
              type=click.Choice(["md", "json"]), help="Extract output format.")
@click.option("--force", is_flag=True, default=False, help="Re-download if exists.")
def run(application: str, output_dir: str | None, fmt: str, force: bool) -> None:
    """Download + extract in one step.

    \b
    Equivalent to running:
      epo-oa download EP21841218
      epo-oa extract EP21841218

    \b
    Examples:
      epo-oa run EP21841218
      epo-oa run EP21841218 --format json
    """
    from epo_oa.parse import extract as do_extract

    app_num = normalize_app_number(application)
    out_dir = output_dir or str(Path.cwd() / "file" / app_num)
    zip_dir = str(Path(out_dir).parent)
    zip_path_str = Path(zip_dir) / f"{app_num}_all_documents.zip"
    out_ext = "json" if fmt == "json" else "md"
    out_path = str(Path(out_dir) / f"{app_num}_prosecution.{out_ext}")

    console.print(Panel(
        f"[bold]Application:[/] {app_num}\n"
        f"[bold]Output dir:[/] {out_dir}\n"
        f"[bold]Analysis:[/] {out_path}",
        title="EPO Prosecution Analysis",
        border_style="cyan",
    ))
    console.print()

    # 1. 문서 목록
    with console.status("[yellow]Fetching document list...[/yellow]"):
        docs = fetch_document_list(app_num)

    if not docs:
        console.print(f"[red]No documents found for {app_num}.[/red]")
        raise SystemExit(1)

    console.print(f"[green]✓ Found {len(docs)} documents[/green]")

    # 2. ZIP 다운로드
    if zip_path_str.exists() and not force:
        console.print(f"[dim]✓ ZIP already exists — skipping download[/dim]")
    else:
        from epo_oa.register import _make_session, _politeness_delay, DOWNLOAD_URL

        doc_ids = [d["id"] for d in docs]
        payload = {
            "documentIdentifiers": "+".join(doc_ids),
            "number": app_num,
            "unip": "false",
            "output": "zip",
        }
        Path(zip_dir).mkdir(parents=True, exist_ok=True)
        _politeness_delay(1.0, 2.0)
        session = _make_session()

        try:
            response = session.post(DOWNLOAD_URL, data=payload, stream=True, timeout=60)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading ZIP...", total=total_size or None)
                with open(zip_path_str, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))

            console.print(f"[green]✓ Downloaded:[/] {zip_path_str}")

        except Exception as e:
            console.print(f"[red]✗ Download failed:[/] {e}")
            raise SystemExit(1)

    # 3. 압축 해제
    with console.status(f"[yellow]Extracting...[/yellow]"):
        extract_zip(str(zip_path_str), out_dir)
    console.print(f"[green]✓ Extracted to:[/] {out_dir}")

    # 4. PDF 파싱 + MD 생성
    with console.status("[yellow]Parsing PDFs and extracting text...[/yellow]"):
        content = do_extract(app_num, file_dir=out_dir, output_path=out_path, fmt=fmt, with_ocr=False)

    lines = content.split("\n")
    summary_line = next((l for l in lines if l.startswith(">")), "")
    if summary_line:
        console.print(f"[dim]{summary_line.lstrip('> ')}[/dim]")

    console.print(f"\n[bold green]✓ Analysis ready:[/] {out_path}")
    console.print(
        "[dim]Pass this file to Claude or another AI agent for prosecution analysis.[/dim]"
    )
