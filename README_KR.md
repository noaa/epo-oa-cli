# epo-oa-cli

**EPO 유럽 특허 심사과정 분석 CLI** — 유럽 특허청(EPO) 심사 문서를 다운로드·파싱하여 AI 분석에 최적화된 `prosecution.md`를 생성합니다.

```bash
pip install epo-oa-cli
epo-oa run EP21841218
```

---

## 개요

`epo-oa`는 [EPO Register](https://register.epo.org/)에서 EP 특허의 전체 심사 이력을 가져오고, PDF 텍스트를 추출(OCR 선택)하여 AI 에이전트(Claude, GPT-4 등)가 바로 분석할 수 있는 구조화된 마크다운 파일을 생성합니다.

```
epo-oa run EP21841218
  → 40개 문서를 ZIP으로 다운로드
  → toc.xml 파싱으로 문서 메타데이터 구성
  → file/EP21841218/EP21841218_prosecution.md 생성
```

---

## 설치

```bash
# 기본 설치
pip install epo-oa-cli

# OCR 지원 포함 (이미지 PDF 텍스트 추출)
pip install "epo-oa-cli[ocr]"
```

Python 3.12 이상이 필요합니다.

---

## 빠른 시작

```bash
# 1. 문서 목록 조회
epo-oa list EP21841218

# 2. ZIP 다운로드 + 압축 해제
epo-oa download EP21841218

# 3. PDF 파싱 → prosecution.md 생성
epo-oa extract EP21841218

# 4. 다운로드 + 추출 한 번에
epo-oa run EP21841218
```

### OCR을 이용한 텍스트 추출

EPO PDF는 전체 이미지 스캔 방식입니다. OCR을 먼저 실행하면 AI 분석 파일에 텍스트를 포함시킬 수 있습니다:

```bash
# 핵심 문서만 선택 OCR
epo-oa ocr EP21841218 --codes 1703,1224,ABEX

# 전체 OCR
epo-oa ocr EP21841218

# OCR 텍스트 포함 추출
epo-oa extract EP21841218 --with-ocr
```

---

## 명령어 목록

| 명령어 | 설명 |
|--------|------|
| `epo-oa list <EP번호>` | EPO Register 문서 목록 조회 |
| `epo-oa download <EP번호>` | 전체 문서 ZIP 다운로드 |
| `epo-oa extract <EP번호>` | PDF 파싱 → `prosecution.md` / `prosecution.json` |
| `epo-oa ocr <EP번호>` | 이미지 PDF → OCR 텍스트 PDF 변환 |
| `epo-oa run <EP번호>` | 다운로드 + 추출 한 번에 실행 |

### 주요 옵션

```bash
epo-oa list EP21841218 --format json            # JSON 형식으로 출력
epo-oa download EP21841218 --force              # 기존 파일 무시하고 재다운로드
epo-oa extract EP21841218 --format json         # JSON 출력
epo-oa extract EP21841218 --with-ocr            # OCR 텍스트 포함
epo-oa ocr EP21841218 --codes 1703,ABEX         # 특정 코드 문서만 OCR
epo-oa ocr EP21841218 --in-place               # 원본 PDF 덮어쓰기
```

---

## 출력 파일: `prosecution.md`

AI 에이전트가 바로 사용할 수 있도록 구조화된 마크다운 파일을 생성합니다:

```markdown
# EPO Prosecution Analysis — EP21841218

## Summary
| 항목 | 건수 |
|------|------|
| 전체 문서 수 | 40 |
| 🔴 심사 통지 (Office Action) | 2 |
| 🔵 보정/응답 (Amendment) | 13 |
| ✅ 허여/결정 (Grant) | 8 |

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
1.1 D1 discloses an electronic device...
` `` `
```

---

## 문서 카테고리

| 아이콘 | 카테고리 | 설명 |
|--------|----------|------|
| 🔴 | Office Action | 심사 통지, 검색의견서 (1224, 1703, 2003~2006 등) |
| 🔵 | Amendment | 보정서, 의견서, 응답서 (CLMSABEX, DESCABEX, ABEX 등) |
| ✅ | Grant | 허여 결정, 증서 (2006A, 2066, 2047 등) |
| 🔍 | Search | 검색 보고서 (1503, 1503SS, ISR, IPRP 등) |
| 💬 | Interview | 면담 기록 (INTERV, EXIN) |
| ⚪ | Other | 수령증, 통지서 등 기타 행정 문서 |

---

## 과도한 접속 방지

이 도구는 **공개 EPO 서버**를 이용합니다. 다음 원칙을 준수합니다:
- 요청 사이에 1.5~3.0초 랜덤 대기
- 브라우저와 동일한 헤더 설정
- ZIP 아카이브 방식으로 HTTP 요청 최소화

CI/CD 파이프라인 등에서 반복 실행 시 적절한 간격을 두어 사용해 주세요.

---

## AI 에이전트 활용 팁

- **이미지 PDF** (`🖼️`): `path` 필드의 경로를 비전 지원 모델에 직접 전달하세요
- **OCR 실행 후** `--with-ocr`: 텍스트 기반 LLM에서 문서 내용을 직접 분석 가능
- **JSON 출력** (`--format json`): `path`·`text` 필드 포함 — 프로그래밍 연동에 활용
- **prosecution.md**: 소규모 사건은 단일 컨텍스트 창 내에서 LLM 분석 가능

---

## 라이선스

MIT
