"""EPO prosecution document parsing — ZIP → toc.xml + PDF text → MD/JSON."""

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── EPO 문서 코드 분류 ────────────────────────────────────────────────────────

# 심사 의견 / 통지 코드
OA_CODES: set[str] = {
    "COMDIV", "2001", "2003", "2004", "2005", "2006", "2066",
    "1082", "1703", "WRITOPIN", "SOPN",
    # EPO 실제 코드
    "2004", "2568",  # Communication / Response to enquiry
    "1224",          # Invitation / Written Opinion
}
OA_PREFIXES: tuple[str, ...] = ("COM",)

# 보정 / 응답 코드
AMENDMENT_CODES: set[str] = {
    "FORAREPLY", "CLMSNEW", "DESCNEW", "DRWNEW", "REMARK",
    # EPO 실제 코드
    "ABEX",           # Amendments received before examination
    "CLMSABEX",       # Amended claims filed after search report
    "DESCABEX",       # Amended description filed after search report
    "CLMS-HWA",       # Amended claims with annotations
    "DESC-HWA",       # Amended description with annotations
    "DRWNEW",         # Amended drawings
    "IGRA7",          # Filing of translations (grant step)
    "CLMSTRAN-FR",    # French translation of claims
    "CLMSTRAN-DE",    # German translation of claims
    "AMENDMT",        # Generic amendment
    "1038",           # Letter accompanying filed items (applicant)
    "1200P",          # Request for entry into European phase
    "1012",           # Enquiry (applicant)
}
AMENDMENT_PREFIXES: tuple[str, ...] = ("A",)
# "A1PAMPHLET" 등 제외 - 이 코드들은 publication document
AMENDMENT_EXCLUDE: set[str] = {
    "A1PAMPHLET", "A2PAMPHLET", "A3PAMPHLET", "ABST",
}

# 특허 허여 코드
GRANT_CODES: set[str] = {
    "GRANT", "2110", "2111", "2006A",
    "2047",   # Transmission of certificate
    "2066",   # Communication re intention to grant (Rule 71(3))
    "EPC",    # Grant certificate
    "EDREX",  # Text intended for grant
    "EDREXFINAL",
    "2035-4",  # Intention to grant (signatures)
    "2906I",   # Annex to intention to grant
    "2056",    # Bibliographic data
    "2004",    # Communication about intention to grant ← 이 경우 grant로 취급
}
# 2004가 OA_CODES와 GRANT_CODES 중복 → 파일명에 "intention to grant" 포함 시 grant로

# 검색 보고서 코드
SEARCH_CODES: set[str] = {
    "1503", "1703", "SRCHSTRAEP",
    "1503SS",   # Supplementary European search report
    "1507",     # Communication re search report
    "ISR",      # International Search Report
    "IPRP",     # International Preliminary Report on Patentability
    "SRCH-START", "EX-START",
}

# 면담 코드
INTERVIEW_CODES: set[str] = {
    "INTERV", "EXIN",
}

# 코드 → 레이블 (파일명에서 description 추출이 실패할 경우 사용)
CODE_LABELS: dict[str, str] = {
    # 심사 통지
    "COMDIV": "Communication from Examining Division",
    "2001": "First Examination Report",
    "2003": "Communication from Examining Division",
    "2004": "Communication from Examining Division",
    "2005": "Communication from Examining Division",
    "2006": "Communication from Examining Division",
    "2006A": "Decision to Grant",
    "2066": "Communication Rule 71(3) — Intention to Grant",
    "1082": "Invitation / Written Opinion",
    "1703": "European Search Opinion",
    "WRITOPIN": "Written Opinion",
    "SOPN": "Search Opinion",
    "1224": "Invitation to Correct Deficiencies (Written Opinion)",
    "2568": "Response to Enquiry from Examining Division",
    # 검색
    "1503": "European Search Report",
    "1503SS": "Supplementary European Search Report",
    "1507": "Communication re Search Report",
    "SRCHSTRAEP": "Information on Search Strategy",
    "SRCH-START": "Search Started",
    "EX-START": "Examination Started",
    "ISR": "International Search Report",
    "IPRP": "International Preliminary Report on Patentability",
    # 보정 / 응답
    "FORAREPLY": "Reply to Invitation",
    "CLMSNEW": "Amended Claims",
    "CLMSABEX": "Amended Claims (after Search Report)",
    "CLMS-HWA": "Amended Claims (with Annotations)",
    "DESCNEW": "Amended Description",
    "DESCABEX": "Amended Description (after Search Report)",
    "DESC-HWA": "Amended Description (with Annotations)",
    "DRWNEW": "Amended Drawings",
    "REMARK": "Remarks / Observations",
    "ABEX": "Amendments Received before Examination",
    "AMENDMT": "Amendment",
    "1038": "Letter Accompanying Filed Items",
    "1200P": "Request for Entry into European Phase",
    "IGRA7": "Filing of Translations of Claims",
    "CLMSTRAN-FR": "French Translation of Claims",
    "CLMSTRAN-DE": "German Translation of Claims",
    "1012": "Enquiry re Processing of File",
    # 허여
    "GRANT": "Decision to Grant",
    "2110": "Notice of Grant",
    "2111": "Grant Document",
    "2047": "Transmission of Grant Certificate (Rule 74 EPC)",
    "2906I": "Annex to Communication re Intention to Grant",
    "2056": "Bibliographic Data",
    "2035-4": "Intention to Grant (Signatures)",
    "EDREX": "Text Intended for Grant (Version for Approval)",
    "EDREXFINAL": "Text Intended for Grant (Clean Copy)",
    "EPC": "Grant Certificate",
    # 기타
    "REF": "Refusal / Rejection",
    "RFEE": "Refund of Fees",
    "INTERV": "Interview Summary",
    "EXIN": "Examiner Interview",
    "EXAMREQ": "Request for Examination",
    "PRIODOC-X": "Priority Document",
    "INCANNEX": "Annex",
    "2522": "Renewal Fee Notice",
    "2907": "Refund of Fees",
    "1099": "Application Withdrawn",
    "1133": "Notification of Publication",
    "1219": "Notification on Forthcoming Publication",
    "1195": "Confirmation of Receipt",
    "1048": "Communication to Inventor",
    "1050B": "Deficiencies in Application",
    "1001": "Acknowledgement of Receipt",
    "1001P": "Request for Grant",
    "1001-6E": "Acknowledgement (Electronic)",
    "1002": "Designation of Inventor",
    "1201-1": "Information on Entry into European Phase",
    "1232": "Confirmation of Effective Date of Early Entry",
    "DESC": "Description",
    "CLMS": "Claims",
    "DRAW": "Drawings",
    "ABST": "Abstract",
    "A1PAMPHLET": "Published Application (A1)",
    "A2PAMPHLET": "Published Application (A2)",
    "RECEIPT-OLF": "(Electronic) Receipt",
    "PRIODOC": "Priority Document",
    "COMINSP": "Communication re Inspection",
}


def _classify(code: str, filename: str = "") -> str:
    """코드와 파일명을 기반으로 문서 카테고리 분류."""
    # 명시적 코드 우선 판단
    if code in INTERVIEW_CODES:
        return "interview"

    # "intention to grant" 또는 "decision to grant" 가 파일명에 있으면 grant
    fn_lower = filename.lower()
    if "intention to grant" in fn_lower or "decision to grant" in fn_lower or "certificate" in fn_lower:
        return "grant"
    if code in GRANT_CODES or code.startswith("EPC"):
        return "grant"

    if code in SEARCH_CODES:
        return "search"

    if code in OA_CODES or any(code.startswith(p) for p in OA_PREFIXES):
        return "office_action"

    # Amendment 판별 (prefix 'A'는 ABST, A1PAMPHLET 등 제외)
    if code in AMENDMENT_CODES:
        return "amendment"
    if code not in AMENDMENT_EXCLUDE and code.startswith("A") and not code.startswith("ABST"):
        return "amendment"
    # 파일명에 "amended" 또는 "amendment" 가 있으면 amendment
    if "amended" in fn_lower or "amendments received" in fn_lower:
        return "amendment"

    return "other"


def _description_from_filename(filename: str, code: str) -> str:
    """파일명에서 코드 다음 부분(description)만 추출.

    포맷: {appnum}-{YYYY}-{MM}-{DD}-{CODE}-{description}.pdf
    """
    stem = Path(filename).stem  # 확장자 제거
    # appnum(1) + YYYY(1) + MM(1) + DD(1) = 최소 4개 '-' 구분자 후 code-description
    parts = stem.split("-", 4)
    if len(parts) < 5:
        return stem
    remainder = parts[4]  # "{CODE}-{description}" 또는 "{description}"
    # code 접두사 제거 (예: "ISR-Copy of..." → "Copy of...")
    if remainder.upper().startswith(code.upper() + "-"):
        remainder = remainder[len(code) + 1:]
    elif remainder.upper().startswith(code.upper()):
        remainder = remainder[len(code):]
    return remainder.replace("_", " ").strip()


def _extract_pdf_text(pdf_path: Path) -> Optional[str]:
    """pypdf로 PDF에서 텍스트 추출. 이미지 PDF면 None 반환."""
    try:
        import pypdf
    except ImportError:
        logger.warning("pypdf not installed — skipping PDF text extraction")
        return None

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        pages_text = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                pages_text.append(text)

        if not pages_text:
            return None

        combined = "\n\n".join(pages_text)
        if len(combined.strip()) < 50:
            return None

        combined = re.sub(r"\n{3,}", "\n\n", combined)
        combined = re.sub(r" {3,}", "  ", combined)
        return combined.strip()

    except Exception as e:
        logger.debug(f"PDF text extraction failed for {pdf_path.name}: {e}")
        return None


def parse_toc_xml(toc_path: Path) -> list[dict]:
    """toc.xml 파싱 → 문서 메타데이터 목록 (날짜 오름차순)."""
    try:
        tree = ET.parse(toc_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"toc.xml parse error: {e}")
        return []

    documents = []
    for doc_el in root.findall(".//document"):
        date = (doc_el.findtext("date") or "").strip()
        code = (doc_el.findtext("type") or "").strip()
        filename = (doc_el.findtext("file") or "").strip()
        description = _description_from_filename(filename, code)
        label = CODE_LABELS.get(code, description) if code in CODE_LABELS else description

        documents.append({
            "date": date,
            "code": code,
            "filename": filename,
            "label": label,
            "category": _classify(code, filename),
        })

    return sorted(documents, key=lambda x: x["date"])


def _infer_from_pdfs(base_dir: Path) -> list[dict]:
    """toc.xml 없을 때 PDF 파일명에서 메타데이터 추출.

    포맷: {appnum}-{YYYY}-{MM}-{DD}-{CODE}-{description}.pdf
    """
    docs = []
    for pdf in sorted(base_dir.glob("*.pdf")):
        name = pdf.stem
        parts = name.split("-", 4)
        if len(parts) >= 5:
            date = f"{parts[1]}-{parts[2]}-{parts[3]}"
            code_and_rest = parts[4]
            # 첫 번째 '-' 이전이 코드
            sub = code_and_rest.split("-", 1)
            code = sub[0]
            description = sub[1].replace("_", " ") if len(sub) > 1 else code
        else:
            date = ""
            code = "UNKNOWN"
            description = name

        label = CODE_LABELS.get(code, description)
        docs.append({
            "date": date,
            "code": code,
            "filename": pdf.name,
            "label": label,
            "category": _classify(code, pdf.name),
        })
    return docs


def build_timeline(app_number: str, file_dir: str) -> list[dict]:
    """
    압축 해제된 디렉토리에서 toc.xml + PDF 텍스트 추출 → 타임라인 반환.

    반환 형식 (항목 당):
    {
        "date": "2023-10-30",
        "code": "1703",
        "label": "European Search Opinion",
        "category": "office_action",  # office_action | amendment | grant | search | interview | other
        "filename": "21841218-2023-10-30-1703-European search opinion.pdf",
        "path": "/abs/path/to/file.pdf",
        "text": "...",        # PDF 텍스트 (추출 성공 시), 없으면 None
        "text_available": False,
    }
    """
    base_dir = Path(file_dir)
    toc_path = base_dir / "toc.xml"

    docs = parse_toc_xml(toc_path) if toc_path.exists() else _infer_from_pdfs(base_dir)

    timeline = []
    for doc in docs:
        pdf_path = base_dir / doc["filename"] if doc.get("filename") else None
        text: Optional[str] = None
        if pdf_path and pdf_path.exists():
            text = _extract_pdf_text(pdf_path)

        timeline.append({
            **doc,
            "path": str(pdf_path) if pdf_path else "",
            "text": text,
            "text_available": text is not None,
        })

    return timeline


# ── Markdown 렌더러 ────────────────────────────────────────────────────────────

_CAT_ICON = {
    "office_action": "🔴",
    "amendment":     "🔵",
    "grant":         "✅",
    "search":        "🔍",
    "interview":     "💬",
    "other":         "⚪",
}
_CAT_LABEL = {
    "office_action": "Office Action",
    "amendment":     "Amendment / Response",
    "grant":         "Grant / Decision",
    "search":        "Search Report",
    "interview":     "Interview",
    "other":         "Other",
}


def _md_header(app_number: str, timeline: list[dict]) -> list[str]:
    total = len(timeline)
    with_text = sum(1 for e in timeline if e["text_available"])
    pdf_only = total - with_text
    oa = sum(1 for e in timeline if e["category"] == "office_action")
    amd = sum(1 for e in timeline if e["category"] == "amendment")
    grant = sum(1 for e in timeline if e["category"] == "grant")
    return [
        f"# EPO Prosecution Analysis — {app_number}",
        "",
        "## Summary",
        "",
        f"| Item | Count |",
        f"|------|-------|",
        f"| Total documents | {total} |",
        f"| 🔴 Office Actions / Exam Reports | {oa} |",
        f"| 🔵 Amendments / Responses | {amd} |",
        f"| ✅ Grant / Decision | {grant} |",
        f"| 📄 Text extracted | {with_text} |",
        f"| 🖼️ Image-only PDF (OCR required) | {pdf_only} |",
        "",
        "> **Note for AI agents:** Image-only PDFs require OCR.",
        "> Run `epo-oa ocr {app_number}` then `epo-oa extract {app_number} --with-ocr` to embed text.".format(app_number=app_number),
        "",
    ]


def _md_timeline(timeline: list[dict]) -> list[str]:
    lines = ["## Timeline", ""]
    lines += ["| Date | Cat | Document | Pages | File |"]
    lines += ["|------|-----|----------|:-----:|------|"]
    for e in timeline:
        icon = _CAT_ICON.get(e["category"], "⚪")
        text_flag = "📄" if e["text_available"] else "🖼️"
        lines.append(
            f"| {e['date']} | {icon} | {e['label']} (`{e['code']}`) {text_flag}"
            f" | | `{e['filename']}` |"
        )
    lines += [""]
    return lines


def _md_doc_entry(e: dict) -> list[str]:
    lines = [f"### {e['label']} — {e['date']}", ""]
    lines += [
        f"- **Code:** `{e['code']}`",
        f"- **File:** `{e['filename']}`",
        f"- **Path:** `{e['path']}`",
        "",
    ]
    if e["text_available"] and e["text"]:
        lines += ["**Extracted Text:**", ""]
        lines += ["```text"]
        text = e["text"]
        if len(text) > 8000:
            text = text[:8000] + "\n\n[... truncated — see full file for remainder ...]"
        lines += [text, "```", ""]
    elif e.get("ocr_text"):
        lines += ["**OCR Text:**", ""]
        lines += ["```text"]
        text = e["ocr_text"]
        if len(text) > 8000:
            text = text[:8000] + "\n\n[... truncated — see full file for remainder ...]"
        lines += [text, "```", ""]
    else:
        lines += [
            f"> 🖼️ **Image-only PDF** — direct text extraction not available.",
            f"> To analyze this document, pass the file path directly to an AI agent:",
            f"> `{e['path']}`",
            "",
        ]
    return lines


def render_md(app_number: str, timeline: list[dict]) -> str:
    lines: list[str] = []
    lines += _md_header(app_number, timeline)
    lines += _md_timeline(timeline)

    for cat in ("office_action", "search", "amendment", "interview", "grant"):
        docs = [e for e in timeline if e["category"] == cat]
        if not docs:
            continue
        cat_label = _CAT_LABEL.get(cat, cat)
        lines += ["---", f"## {_CAT_ICON.get(cat, '')} {cat_label} Documents", ""]
        for doc in docs:
            lines += _md_doc_entry(doc)

    # 기타
    other = [e for e in timeline if e["category"] == "other"]
    if other:
        lines += ["---", "## Other Documents", ""]
        lines += ["| Date | Document | File |"]
        lines += ["|------|----------|------|"]
        for e in other:
            lines.append(f"| {e['date']} | {e['label']} (`{e['code']}`) | `{e['filename']}` |")
        lines += [""]

    return "\n".join(lines)


def render_json(app_number: str, timeline: list[dict]) -> str:
    data = {
        "application_number": app_number,
        "summary": {
            "total": len(timeline),
            "office_actions": sum(1 for e in timeline if e["category"] == "office_action"),
            "amendments": sum(1 for e in timeline if e["category"] == "amendment"),
            "grant": sum(1 for e in timeline if e["category"] == "grant"),
            "text_available": sum(1 for e in timeline if e["text_available"]),
        },
        "timeline": [
            {
                "date": e["date"],
                "code": e["code"],
                "label": e["label"],
                "category": e["category"],
                "filename": e["filename"],
                "path": e["path"],
                "text_available": e["text_available"],
                "text": e.get("text"),
                "ocr_text": e.get("ocr_text"),
            }
            for e in timeline
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def enrich_with_ocr(timeline: list[dict], file_dir: Path) -> list[dict]:
    """_ocr.pdf 파일이 있는 항목에 OCR 텍스트를 주입."""
    try:
        import pypdf
    except ImportError:
        logger.warning("pypdf not installed — skipping OCR enrichment")
        return timeline

    enriched = []
    for entry in timeline:
        if entry.get("text_available"):
            enriched.append(entry)
            continue

        pdf_path = Path(entry["path"]) if entry.get("path") else None
        if not pdf_path:
            enriched.append(entry)
            continue

        ocr_path = pdf_path.with_stem(pdf_path.stem + "_ocr")
        if not ocr_path.exists():
            enriched.append(entry)
            continue

        try:
            reader = pypdf.PdfReader(str(ocr_path))
            text = "\n\n".join(
                (page.extract_text() or "").strip() for page in reader.pages
            ).strip()
            if text and len(text) > 50:
                entry = {**entry, "ocr_text": text, "ocr_path": str(ocr_path)}
        except Exception as e:
            logger.warning(f"OCR text extract failed for {ocr_path.name}: {e}")

        enriched.append(entry)
    return enriched


def extract(
    app_number: str,
    file_dir: str,
    output_path: Optional[str] = None,
    fmt: str = "md",
    with_ocr: bool = False,
) -> str:
    """타임라인 구성 → MD/JSON 렌더링. output_path 지정 시 파일 저장."""
    timeline = build_timeline(app_number, file_dir)

    if with_ocr:
        timeline = enrich_with_ocr(timeline, Path(file_dir))

    content = render_json(app_number, timeline) if fmt == "json" else render_md(app_number, timeline)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(content, encoding="utf-8")
        logger.info(f"Saved: {output_path}")

    return content
