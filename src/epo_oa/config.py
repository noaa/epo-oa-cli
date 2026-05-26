import tomllib
from pathlib import Path

CONFIG_PATH = Path.home() / ".epo-oa.toml"


def load() -> dict:
    """~/.epo-oa.toml을 읽어 dict 반환. 파일 없으면 빈 dict."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def save(config: dict) -> None:
    """config dict를 ~/.epo-oa.toml에 저장."""
    CONFIG_PATH.write_text(_dump_toml(config), encoding="utf-8")


def get_request_kwargs(config: dict) -> dict:
    """config에서 requests용 proxies, verify 값을 추출하여 반환.

    설정이 없는 키는 포함하지 않으므로 requests가 환경변수로 fallback한다.
    """
    kwargs: dict = {}

    proxy_cfg = config.get("proxy", {})
    proxies: dict = {}
    if proxy_cfg.get("https"):
        proxies["https"] = proxy_cfg["https"]
    if proxy_cfg.get("http"):
        proxies["http"] = proxy_cfg["http"]
    if proxies:
        kwargs["proxies"] = proxies

    ca_bundle = config.get("ssl", {}).get("ca_bundle")
    if ca_bundle:
        kwargs["verify"] = ca_bundle

    return kwargs


def _dump_toml(config: dict) -> str:
    """config dict를 TOML 문자열로 직렬화 (tomllib은 read-only라 직접 구현)."""
    lines: list[str] = []
    for section, values in config.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, val in values.items():
            if val is None or val == "":
                continue
            escaped = str(val).replace("\\", "\\\\")
            lines.append(f'{key} = "{escaped}"')
        lines.append("")
    return "\n".join(lines)
