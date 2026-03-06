from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .models import CompanyDiscoveryBundle, DownloadedDocument, WebSnippet
from .utils import compact_text, ensure_dir, is_allowed_url, sha256_bytes, slugify


class DocumentFetchService:
    """Download PDF sources and enrich HTML snippets with text excerpts."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def materialize(
        self,
        bundle: CompanyDiscoveryBundle,
        *,
        force_refresh: bool = False,
    ) -> CompanyDiscoveryBundle:
        warnings = list(bundle.warnings)
        downloaded_documents: list[DownloadedDocument] = []
        snippets: list[WebSnippet] = []

        for document in bundle.documents:
            try:
                downloaded_documents.append(
                    self._download_document(document, company_name=bundle.company_name, force_refresh=force_refresh)
                )
            except Exception as exc:  # pragma: no cover - depends on network
                warnings.append(f"Téléchargement échoué pour {document.url}: {exc}")

        for snippet in bundle.web_snippets:
            try:
                snippets.append(self._enrich_web_snippet(snippet, force_refresh=force_refresh))
            except Exception as exc:  # pragma: no cover - depends on network
                warnings.append(f"Lecture HTML échouée pour {snippet.url}: {exc}")
                snippets.append(snippet)

        return CompanyDiscoveryBundle(
            company_name=bundle.company_name,
            official_website=bundle.official_website,
            investor_relations_url=bundle.investor_relations_url,
            documents=downloaded_documents,
            web_snippets=snippets,
            warnings=warnings,
        )

    def _download_document(
        self,
        document: DownloadedDocument,
        *,
        company_name: str,
        force_refresh: bool,
    ) -> DownloadedDocument:
        if not is_allowed_url(document.url):
            raise ValueError("URL non autorisée")

        company_dir = ensure_dir(self.settings.download_dir / slugify(company_name))
        suffix = Path(urlparse(document.url).path).suffix or ".pdf"
        base_name = slugify(document.title)[:80] or "document"
        file_name = f"{document.year or 'unknown'}-{base_name}{suffix}"
        file_path = company_dir / file_name

        if file_path.exists() and not force_refresh:
            payload = file_path.read_bytes()
            return DownloadedDocument(
                **document.model_dump(),
                local_path=str(file_path),
                bytes_size=file_path.stat().st_size,
                sha256=sha256_bytes(payload),
            )

        response = self.session.get(
            document.url,
            timeout=(self.settings.connect_timeout_seconds, self.settings.request_timeout_seconds),
            verify=self.settings.verify_ssl,
            stream=True,
        )
        response.raise_for_status()

        total = 0
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=1024 * 128):
            if not chunk:
                continue
            total += len(chunk)
            if total > self.settings.max_pdf_bytes:
                raise ValueError(
                    f"Document trop volumineux ({total} octets), limite {self.settings.max_pdf_bytes}."
                )
            chunks.append(chunk)
        payload = b"".join(chunks)
        file_path.write_bytes(payload)

        return DownloadedDocument(
            **document.model_dump(),
            local_path=str(file_path),
            bytes_size=len(payload),
            sha256=sha256_bytes(payload),
        )

    def _enrich_web_snippet(self, snippet: WebSnippet, *, force_refresh: bool) -> WebSnippet:
        if snippet.text_excerpt and not force_refresh:
            return snippet
        if not is_allowed_url(snippet.url):
            return snippet

        response = self.session.get(
            snippet.url,
            timeout=(self.settings.connect_timeout_seconds, self.settings.request_timeout_seconds),
            verify=self.settings.verify_ssl,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "text/" not in content_type:
            return snippet

        soup = BeautifulSoup(response.text, "lxml")
        text = soup.get_text(" ", strip=True)
        title = soup.title.get_text(" ", strip=True) if soup.title else snippet.title
        return WebSnippet(
            **snippet.model_dump(exclude={"text_excerpt", "title"}),
            title=title,
            text_excerpt=compact_text(text, max_chars=4000),
        )
