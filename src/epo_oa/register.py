"""EPO Register web scraping — document list and download."""

import logging
import random
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://register.epo.org/"
DOCLIST_URL = "https://register.epo.org/application"
DOWNLOAD_URL = "https://register.epo.org/download"

# EPO 심사과정 핵심 문서 타입 코드 (정확 일치)
PROSECUTION_CODES_EXACT: set[str] = {
    # 심사 통지
    "COMDIV", "2001", "2003", "2004", "2005", "2006", "2066",
    # 서면 심사의견 / 검색
    "1082", "1703", "WRITOPIN", "SOPN",
    "1503", "SRCHSTRAEP",
    # 보정/응답 (출원인)
    "FORAREPLY", "CLMSNEW", "DESCNEW", "DRWNEW", "ABST", "REMARK",
    "COMINSP",
    # 허여/거절
    "GRANT", "2110", "2111", "REF", "RFEE",
    # 면담
    "INTERV", "EXIN",
    # RCE 상당
    "EXAMREQ",
}

# 이 접두사로 시작하는 코드 모두 포함
PROSECUTION_CODE_PREFIXES: tuple[str, ...] = ("A", "COM", "REP", "CLM", "REMARK")

# 코드 → 사람이 읽기 쉬운 레이블
CODE_LABELS: dict[str, str] = {
    "COMDIV": "Communication from Examining Division",
    "2001": "First examination report",
    "2003": "Communication from Examining Division",
    "2004": "Communication from Examining Division",
    "2005": "Communication from Examining Division",
    "2006": "Communication from Examining Division",
    "2066": "Communication (Rule 71(3) EPC)",
    "1082": "Invitation / Written Opinion",
    "1703": "European Search Opinion",
    "WRITOPIN": "Written Opinion",
    "SOPN": "Search Opinion",
    "1503": "European Search Report",
    "1507": "Communication re Search Report",
    "SRCHSTRAEP": "Search Strategy",
    "SRCH-START": "Search Started",
    "FORAREPLY": "Reply to Invitation",
    "CLMSNEW": "Amended Claims",
    "DESCNEW": "Amended Description",
    "DRWNEW": "Amended Drawings",
    "ABST": "Abstract",
    "REMARK": "Remarks / Observations",
    "GRANT": "Decision to Grant",
    "2110": "Notice of Grant",
    "2111": "Grant Document",
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
    "1195": "Confirmation of Receipt",
    "1048": "Communication to Inventor",
    "1050B": "Deficiencies in Application",
    "1001": "Acknowledgement of Receipt",
    "1001P": "Request for Grant",
    "1001-6E": "Acknowledgement (Electronic)",
    "1002": "Designation of Inventor",
    "DESC": "Description",
    "CLMS": "Claims",
    "DRAW": "Drawings",
}


def normalize_app_number(raw: str) -> str:
    """EP21841218 → EP21841218 (정규화: EP 접두사 보존, 공백/하이픈 제거)."""
    cleaned = raw.strip().upper().replace(" ", "").replace("-", "")
    if not cleaned.startswith("EP"):
        cleaned = "EP" + cleaned
    return cleaned


def _make_session(
    proxies: dict | None = None,
    verify: str | bool = True,
) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BASE_URL,
    })
    if proxies:
        session.proxies.update(proxies)
    session.verify = verify
    return session


def _politeness_delay(min_sec: float = 1.5, max_sec: float = 3.0) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def fetch_document_list(
    app_number: str,
    proxies: dict | None = None,
    verify: str | bool = True,
) -> list[dict]:
    """EPO Register의 doclist 탭을 파싱해 문서 목록 반환."""
    url = f"{DOCLIST_URL}?number={app_number}&tab=doclist"
    session = _make_session(proxies=proxies, verify=verify)

    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch document list: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "row"})
    if not table:
        logger.warning(f"Document table not found for {app_number}")
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    documents = []
    for idx, row in enumerate(tbody.find_all("tr"), 1):
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        checkbox = cols[0].find("input", {"name": "identivier"})
        if not checkbox:
            continue

        doc_id = checkbox.get("value", "")
        date = cols[1].text.strip()

        # anchor의 href에서 코드 추출 시도
        doc_type_el = cols[2].find("a")
        doc_type = doc_type_el.text.strip() if doc_type_el else cols[2].text.strip()
        href = doc_type_el.get("href", "") if doc_type_el else ""
        code = _extract_code_from_href_or_text(href, doc_type)

        procedure = cols[3].text.strip().replace("\xa0", " ")
        pages = cols[4].text.strip()

        documents.append({
            "index": idx,
            "id": doc_id,
            "date": date,
            "type": doc_type,
            "code": code,
            "procedure": procedure,
            "pages": pages,
            "label": doc_type,  # 전체 텍스트를 레이블로 사용
        })

    return documents


def _extract_code_from_href_or_text(href: str, doc_type: str) -> str:
    """href URL 또는 문서 타입 텍스트에서 EPO 문서 코드 추출."""
    # href에서 코드 추출 (예: ?documentId=XXX&tab=doclist)
    if href:
        # documentCode 파라미터가 있는 경우
        match = re.search(r"[?&](?:documentCode|type)=([^&]+)", href)
        if match:
            return match.group(1)

    # 역방향 레이블 → 코드 매핑
    lower = doc_type.lower().strip()
    for code, label in CODE_LABELS.items():
        if label.lower() == lower:
            return code

    # 숫자 코드가 포함된 경우 (예: "1503", "1703")
    match = re.search(r"^\s*(\d{3,4}[A-Z]?)\b", doc_type)
    if match:
        return match.group(1)

    # 알려진 영문 키워드 패턴으로 분류
    lower_ws = lower.replace("-", " ")
    if "search opinion" in lower_ws or "written opinion" in lower_ws:
        return "1703"
    if "search report" in lower_ws and "supplementary" in lower_ws:
        return "SREP-SUPP"
    if "search report" in lower_ws:
        return "1503"
    if "search strategy" in lower_ws:
        return "SRCHSTRAEP"
    if "decision to grant" in lower_ws:
        return "GRANT"
    if "intention to grant" in lower_ws:
        return "2066"
    if "examination report" in lower_ws or "communication" in lower_ws and "examining" in lower_ws:
        return "COMDIV"
    if "amended claim" in lower_ws:
        return "CLMSNEW"
    if "amended description" in lower_ws:
        return "DESCNEW"
    if "amendment" in lower_ws or "amendments" in lower_ws:
        return "AMENDMT"
    if "interview" in lower_ws:
        return "INTERV"
    if "response" in lower_ws or "reply" in lower_ws:
        return "REPLY"
    if "request for examination" in lower_ws:
        return "EXAMREQ"
    if "priority document" in lower_ws:
        return "PRIODOC"
    if "international search" in lower_ws:
        return "ISR"
    if "preliminary report" in lower_ws:
        return "IPRP"
    if "withdrawn" in lower_ws or "withdrawal" in lower_ws:
        return "1099"
    if "grant" in lower_ws and "certificate" in lower_ws:
        return "EPC"

    # 대문자 코드 패턴 (예: "SRCH-START", "COMDIV")
    match = re.search(r"\b([A-Z][A-Z0-9]{2,}(?:-[A-Z0-9]+)?)\b", doc_type)
    if match and match.group(1) not in {"EPC", "EP", "PCT", "PDF", "XML"}:
        return match.group(1)

    return "—"


def download_zip(
    app_number: str,
    documents: list[dict],
    output_dir: str,
    *,
    force: bool = False,
) -> str | None:
    """모든 문서를 ZIP으로 다운로드. 이미 존재하면 스킵 (force=True면 재다운로드)."""
    zip_path = Path(output_dir) / f"{app_number}_all_documents.zip"

    if zip_path.exists() and not force:
        logger.info(f"ZIP already exists: {zip_path}")
        return str(zip_path)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    doc_ids = [doc["id"] for doc in documents]
    payload = {
        "documentIdentifiers": "+".join(doc_ids),
        "number": app_number,
        "unip": "false",
        "output": "zip",
    }

    session = _make_session()
    _politeness_delay(1.0, 2.0)

    try:
        response = session.post(DOWNLOAD_URL, data=payload, stream=True, timeout=60)
        response.raise_for_status()

        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Downloaded: {zip_path}")
        return str(zip_path)

    except requests.RequestException as e:
        logger.error(f"ZIP download failed: {e}")
        return None


def extract_zip(zip_path: str, output_dir: str) -> str:
    """ZIP을 output_dir/{app_number}/ 디렉토리에 압축 해제."""
    import zipfile

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target_dir)

    logger.info(f"Extracted to: {target_dir}")
    return str(target_dir)
