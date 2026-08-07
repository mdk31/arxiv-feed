import logging
import os
import re

import requests
import yaml
from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)

PDF_URL_TEMPLATE = "https://arxiv.org/pdf/{arxiv_id}"


def load_institutions(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    flat = {}
    for section in raw.values():
        for canonical, spec in (section or {}).items():
            flat[canonical] = {
                "aliases": spec.get("aliases", []),
                "domains": spec.get("domains", []),
            }
    return flat


def _alias_pattern(alias):
    if isinstance(alias, dict):
        text = alias["text"]
        lookahead = "".join(f"(?!{re.escape(excl)})" for excl in alias.get("not_followed_by", []))
        flags = 0 if alias.get("case_sensitive") else re.IGNORECASE
        return re.compile(r"\b" + re.escape(text) + lookahead + r"\b", flags)
    return re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)


def _domain_pattern(domain):
    return re.compile(r"[@.]" + re.escape(domain) + r"\b", re.IGNORECASE)


_ABSTRACT_SPLIT = re.compile(r"\babstract\b", re.IGNORECASE)


def extract_header_text(page_text):
    match = _ABSTRACT_SPLIT.search(page_text)
    return page_text[: match.start()] if match else page_text


def match_institutions(page_text, institutions):
    header = extract_header_text(page_text)
    matched = []
    for canonical, spec in institutions.items():
        found = any(_alias_pattern(alias).search(header) for alias in spec["aliases"]) or any(
            _domain_pattern(domain).search(header) for domain in spec["domains"]
        )
        if found:
            matched.append(canonical)
    return matched


def split_authors(authors_str):
    if not authors_str:
        return []
    return [a.strip() for a in authors_str.split(",") if a.strip()]


def download_pdf(arxiv_id, dest_path, timeout=20):
    url = PDF_URL_TEMPLATE.format(arxiv_id=arxiv_id)
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "arxiv-feed personal filter (contact: n/a)"})
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(response.content)


def extract_first_page_text(pdf_path):
    reader = PdfReader(pdf_path)
    if not reader.pages:
        return ""
    return reader.pages[0].extract_text() or ""


def check_pdf(arxiv_id, scratch_dir, institutions, timeout=20):
    os.makedirs(scratch_dir, exist_ok=True)
    dest_path = os.path.join(scratch_dir, f"{arxiv_id}.pdf")
    try:
        download_pdf(arxiv_id, dest_path, timeout=timeout)
        page_text = extract_first_page_text(dest_path)
    finally:
        if os.path.exists(dest_path):
            os.remove(dest_path)
    return match_institutions(page_text, institutions)


def check_affiliation(paper, institutions, scratch_dir, timeout=20):
    authors_str = paper.get("authors", "")
    arxiv_id = paper["arxiv_id"]

    try:
        matched = check_pdf(arxiv_id, scratch_dir, institutions, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {
            "included": False,
            "matched_institutions": [],
            "matched_authors": [],
            "error": str(exc),
        }

    return {
        "included": bool(matched),
        "matched_institutions": matched,
        "matched_authors": split_authors(authors_str) if matched else [],
        "error": None,
    }
