from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


def slugify(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "item"


def base_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    return True


def is_probably_pdf_url(url: str) -> bool:
    return ".pdf" in url.lower().split("?")[0]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_whitespace(text: str) -> str:
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compact_text(text: str, max_chars: int = 4000) -> str:
    normalized = normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def extract_year(text: str) -> int | None:
    match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    return int(match.group(1)) if match else None


_ANNUAL_KEYWORDS = (
    "annual report",
    "integrated report",
    "rapport annuel",
    "geschäftsbericht",
    "relazione finanziaria annuale",
    "informe anual",
    "jaarverslag",
)
_URD_KEYWORDS = (
    "universal registration",
    "document d'enregistrement universel",
    "document de reference",
)
_RESULTS_KEYWORDS = (
    "results",
    "earnings",
    "full year",
    "fy20",
    "half-year",
    "interim report",
    "résultats",
    "résultats annuels",
)
_PRESENTATION_KEYWORDS = (
    "presentation",
    "investor presentation",
    "capital markets day",
    "cmd",
)
_DEBT_KEYWORDS = (
    "bond",
    "credit",
    "rating",
    "financing",
    "debt",
)
_SUSTAINABILITY_KEYWORDS = (
    "sustainability",
    "esg",
    "csrd",
    "durabilité",
)


def guess_category(title: str, url: str) -> str:
    haystack = f"{title} {url}".lower()
    if any(keyword in haystack for keyword in _URD_KEYWORDS):
        return "universal_registration_document"
    if any(keyword in haystack for keyword in _ANNUAL_KEYWORDS):
        return "annual_report"
    if any(keyword in haystack for keyword in _RESULTS_KEYWORDS):
        return "results_release"
    if "capital markets day" in haystack:
        return "capital_markets_day"
    if any(keyword in haystack for keyword in _PRESENTATION_KEYWORDS):
        return "investor_presentation"
    if any(keyword in haystack for keyword in _DEBT_KEYWORDS):
        return "debt_or_credit"
    if any(keyword in haystack for keyword in _SUSTAINABILITY_KEYWORDS):
        return "sustainability"
    return "other"


def score_source(title: str, url: str, is_official_domain: bool = True) -> float:
    category = guess_category(title, url)
    base_scores = {
        "annual_report": 120.0,
        "universal_registration_document": 115.0,
        "results_release": 80.0,
        "investor_presentation": 70.0,
        "capital_markets_day": 68.0,
        "debt_or_credit": 60.0,
        "sustainability": 45.0,
        "other": 20.0,
    }
    score = base_scores[category]
    year = extract_year(f"{title} {url}")
    if year:
        score += max(0, year - 2018) * 2
    if is_official_domain:
        score += 25.0
    if is_probably_pdf_url(url):
        score += 10.0
    if "investor" in url.lower() or "finance" in url.lower() or "results" in url.lower():
        score += 5.0
    return score


def dedupe_by_url(items: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    output: list[dict] = []
    for item in items:
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        output.append(item)
    return output


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_payload(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty model output, expected JSON payload.")

    fence_match = _CODE_FENCE_RE.search(stripped)
    if fence_match:
        return json.loads(fence_match.group(1))

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("Top-level JSON payload must be an object.")
    except json.JSONDecodeError:
        pass

    candidate = _extract_balanced_json_object(stripped)
    if candidate is None:
        raise ValueError("Could not locate a valid JSON object in model output.")
    return json.loads(candidate)


def _extract_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None
