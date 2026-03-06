from __future__ import annotations

import re
from collections import deque
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .models import CompanyDiscoveryBundle, CompanyRequest, DocumentSource, WebSnippet
from .utils import (
    base_domain,
    compact_text,
    extract_year,
    guess_category,
    is_allowed_url,
    is_probably_pdf_url,
    normalize_whitespace,
    score_source,
)


_SEARCH_EXCLUSION_DOMAINS = {
    "linkedin.com",
    "wikipedia.org",
    "bloomberg.com",
    "reuters.com",
    "yahoo.com",
    "marketscreener.com",
    "annualreports.com",
    "morningstar.com",
    "ft.com",
    "wsj.com",
    "zonebourse.com",
    "tradingview.com",
}

_GENERIC_COMPANY_TOKENS = {
    "group",
    "holding",
    "holdings",
    "sa",
    "ag",
    "nv",
    "plc",
    "spa",
    "se",
    "sas",
    "company",
}


class DocumentDiscoveryService:
    """Find public investor-relations documents and web pages for a company.

    The service is deliberately heuristic: official IR archives differ widely across
    European issuers. The class therefore prioritizes:
      1. URLs supplied by the caller,
      2. likely official websites and investor-relations pages,
      3. same-domain PDFs discovered by crawling a small set of pages.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def discover(
        self,
        company: CompanyRequest,
        *,
        years: int,
        max_documents: int,
        max_web_snippets: int,
        strict_official_sources_only: bool = False,
        manual_sources_only: bool = False,
    ) -> CompanyDiscoveryBundle:
        warnings: list[str] = []
        documents: list[DocumentSource] = []
        pages: list[WebSnippet] = []

        official_website = str(company.official_website) if company.official_website else None
        investor_relations_url = (
            str(company.investor_relations_url) if company.investor_relations_url else None
        )

        if company.extra_document_urls:
            for url in company.extra_document_urls:
                documents.append(
                    DocumentSource(
                        company_name=company.name,
                        title=f"Manual source {url}",
                        url=str(url),
                        source_kind="manual",
                        category=guess_category(str(url), str(url)),
                        discovered_from="manual extra_document_urls",
                        is_official_domain=True,
                        year=extract_year(str(url)),
                        score=200.0,
                    )
                )
        if company.extra_page_urls:
            for url in company.extra_page_urls:
                pages.append(
                    WebSnippet(
                        company_name=company.name,
                        title=f"Manual page {url}",
                        url=str(url),
                        source_kind="manual",
                        category=guess_category(str(url), str(url)),
                        discovered_from="manual extra_page_urls",
                        is_official_domain=True,
                        year=extract_year(str(url)),
                        score=150.0,
                    )
                )

        if manual_sources_only:
            if not documents and not pages:
                warnings.append(
                    "manual_sources_only=True mais aucune source manuelle n'a été fournie."
                )
            return CompanyDiscoveryBundle(
                company_name=company.name,
                official_website=official_website,
                investor_relations_url=investor_relations_url,
                documents=self._select_documents(documents, max_documents=max_documents, years=years),
                web_snippets=self._select_pages(pages, max_web_snippets=max_web_snippets),
                warnings=warnings,
            )

        search_results: list[dict] = []
        for query in self._build_queries(company):
            try:
                search_results.extend(self._duckduckgo_search(query))
            except Exception as exc:  # pragma: no cover - depends on network
                warnings.append(f"Recherche web indisponible pour '{query}': {exc}")

        if official_website is None:
            official_website = self._select_official_website(company, search_results)
            if official_website is None:
                warnings.append(
                    "Impossible d'identifier automatiquement un site officiel fiable. "
                    "Fournir official_website ou investor_relations_url améliorera fortement la robustesse."
                )

        allowed_domains = {base_domain(official_website)} if official_website else set()
        if investor_relations_url:
            allowed_domains.add(base_domain(investor_relations_url))
        allowed_domains.discard("")

        if investor_relations_url is None and official_website is not None:
            investor_relations_url = self._select_ir_page(company, search_results, official_website)

        # Include direct PDF results from search.
        for result in search_results:
            url = result["url"]
            same_domain = not allowed_domains or base_domain(url) in allowed_domains
            if strict_official_sources_only and not same_domain:
                continue
            if is_probably_pdf_url(url):
                documents.append(
                    DocumentSource(
                        company_name=company.name,
                        title=result["title"],
                        url=url,
                        source_kind="search_result",
                        category=guess_category(result["title"], url),
                        discovered_from=result["query"],
                        is_official_domain=same_domain,
                        year=extract_year(f"{result['title']} {url}"),
                        score=score_source(result["title"], url, same_domain),
                    )
                )
            else:
                if same_domain or not strict_official_sources_only:
                    pages.append(
                        WebSnippet(
                            company_name=company.name,
                            title=result["title"],
                            url=url,
                            source_kind="search_result",
                            category=guess_category(result["title"], url),
                            discovered_from=result["query"],
                            is_official_domain=same_domain,
                            year=extract_year(f"{result['title']} {url}"),
                            score=score_source(result["title"], url, same_domain),
                        )
                    )

        crawl_roots = [url for url in [investor_relations_url, official_website] if url]
        crawled_documents, crawled_pages = self._crawl(
            company_name=company.name,
            start_urls=crawl_roots,
            allowed_domains=allowed_domains,
            strict_official_sources_only=strict_official_sources_only,
        )
        documents.extend(crawled_documents)
        pages.extend(crawled_pages)

        return CompanyDiscoveryBundle(
            company_name=company.name,
            official_website=official_website,
            investor_relations_url=investor_relations_url,
            documents=self._select_documents(documents, max_documents=max_documents, years=years),
            web_snippets=self._select_pages(pages, max_web_snippets=max_web_snippets),
            warnings=warnings,
        )

    def _build_queries(self, company: CompanyRequest) -> list[str]:
        country_suffix = f" {company.country}" if company.country else ""
        name = company.name
        return [
            f'"{name}" investor relations{country_suffix}',
            f'"{name}" annual report pdf{country_suffix}',
            f'"{name}" results presentation pdf{country_suffix}',
            f'"{name}" universal registration document pdf{country_suffix}',
        ]

    def _duckduckgo_search(self, query: str) -> list[dict]:
        response = self.session.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=(self.settings.connect_timeout_seconds, self.settings.request_timeout_seconds),
            verify=self.settings.verify_ssl,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        results: list[dict] = []
        for anchor in soup.select("a.result__a")[: self.settings.max_search_results]:
            href = anchor.get("href")
            target = self._decode_search_result_url(href)
            if not target or not is_allowed_url(target):
                continue
            title = normalize_whitespace(anchor.get_text(" ", strip=True))
            results.append({"query": query, "title": title or target, "url": target})
        return results

    def _decode_search_result_url(self, href: str | None) -> str | None:
        if not href:
            return None
        if href.startswith("//"):
            href = f"https:{href}"
        parsed = urlparse(href)
        if parsed.netloc.endswith("duckduckgo.com"):
            target = parse_qs(parsed.query).get("uddg")
            if target:
                return unquote(target[0])
        return href

    def _select_official_website(self, company: CompanyRequest, search_results: list[dict]) -> str | None:
        company_tokens = self._company_tokens(company.name)
        ranked: list[tuple[float, str]] = []
        for result in search_results:
            url = result["url"]
            domain = base_domain(url)
            if not domain or domain in _SEARCH_EXCLUSION_DOMAINS:
                continue
            score = 0.0
            if parsed_host := urlparse(url).hostname:
                host_l = parsed_host.lower()
                score += sum(12.0 for token in company_tokens if token in host_l)
                if host_l.startswith("ir.") or host_l.startswith("investors."):
                    score += 15.0
            path_l = (urlparse(url).path or "").lower()
            if path_l in {"", "/", "/home", "/en", "/fr"}:
                score += 10.0
            if any(keyword in path_l for keyword in ("investor", "finance", "shareholder")):
                score += 8.0
            title_l = result["title"].lower()
            score += sum(4.0 for token in company_tokens if token in title_l)
            ranked.append((score, url))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1] if ranked and ranked[0][0] > 0 else None

    def _select_ir_page(
        self,
        company: CompanyRequest,
        search_results: list[dict],
        official_website: str,
    ) -> str | None:
        allowed = base_domain(official_website)
        candidates: list[tuple[float, str]] = []
        for result in search_results:
            url = result["url"]
            if base_domain(url) != allowed:
                continue
            path_l = (urlparse(url).path or "").lower()
            title_l = result["title"].lower()
            score = 0.0
            if any(word in path_l for word in ("investor", "finance", "shareholder", "results")):
                score += 15.0
            if any(word in title_l for word in ("investor", "finance", "shareholder", "results")):
                score += 10.0
            if score > 0:
                candidates.append((score, url))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1] if candidates else official_website

    def _crawl(
        self,
        *,
        company_name: str,
        start_urls: Iterable[str],
        allowed_domains: set[str],
        strict_official_sources_only: bool,
    ) -> tuple[list[DocumentSource], list[WebSnippet]]:
        documents: list[DocumentSource] = []
        pages: list[WebSnippet] = []
        queue = deque(url for url in start_urls if url and is_allowed_url(url))
        visited: set[str] = set()

        while queue and len(visited) < self.settings.max_crawl_pages:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            if strict_official_sources_only and allowed_domains and base_domain(url) not in allowed_domains:
                continue

            try:
                response = self.session.get(
                    url,
                    timeout=(
                        self.settings.connect_timeout_seconds,
                        self.settings.request_timeout_seconds,
                    ),
                    verify=self.settings.verify_ssl,
                )
                response.raise_for_status()
            except Exception:
                continue

            content_type = response.headers.get("content-type", "").lower()
            same_domain = not allowed_domains or base_domain(url) in allowed_domains
            if "pdf" in content_type or is_probably_pdf_url(url):
                documents.append(
                    DocumentSource(
                        company_name=company_name,
                        title=url.split("/")[-1] or url,
                        url=url,
                        source_kind="pdf",
                        category=guess_category(url, url),
                        discovered_from="crawler",
                        is_official_domain=same_domain,
                        year=extract_year(url),
                        score=score_source(url, url, same_domain),
                    )
                )
                continue

            if "html" not in content_type and "text/" not in content_type:
                continue

            soup = BeautifulSoup(response.text, "lxml")
            title = normalize_whitespace(soup.title.get_text(" ", strip=True)) if soup.title else url
            text_excerpt = compact_text(soup.get_text(" ", strip=True), max_chars=2200)
            pages.append(
                WebSnippet(
                    company_name=company_name,
                    title=title,
                    url=url,
                    source_kind="html",
                    category=guess_category(title, url),
                    discovered_from="crawler",
                    is_official_domain=same_domain,
                    year=extract_year(f"{title} {url}"),
                    score=score_source(title, url, same_domain),
                    text_excerpt=text_excerpt,
                )
            )

            for anchor in soup.select("a[href]"):
                href = anchor.get("href")
                if not href:
                    continue
                target = urljoin(url, href)
                if not is_allowed_url(target):
                    continue
                target_domain = base_domain(target)
                if allowed_domains and target_domain not in allowed_domains:
                    continue
                anchor_text = normalize_whitespace(anchor.get_text(" ", strip=True)).lower()
                if is_probably_pdf_url(target):
                    documents.append(
                        DocumentSource(
                            company_name=company_name,
                            title=anchor_text or target.split("/")[-1] or target,
                            url=target,
                            source_kind="pdf",
                            category=guess_category(anchor_text, target),
                            discovered_from=url,
                            is_official_domain=True,
                            year=extract_year(f"{anchor_text} {target}"),
                            score=score_source(anchor_text, target, True),
                        )
                    )
                    continue
                if self._should_follow(target, anchor_text):
                    if target not in visited:
                        queue.append(target)

        return documents, pages

    def _should_follow(self, target_url: str, anchor_text: str) -> bool:
        path = (urlparse(target_url).path or "").lower()
        haystack = f"{anchor_text} {path}"
        keywords = (
            "investor",
            "finance",
            "financial",
            "results",
            "reports",
            "publications",
            "documents",
            "annual",
            "shareholder",
            "media",
            "newsroom",
        )
        if any(keyword in haystack for keyword in keywords):
            return True
        # Keep crawling shallow archive pages likely to host PDFs.
        return path.count("/") <= 3 and any(token in path for token in ("ir", "news", "media"))

    def _select_documents(
        self,
        candidates: list[DocumentSource],
        *,
        max_documents: int,
        years: int,
    ) -> list[DocumentSource]:
        deduped = self._dedupe_sources(candidates)
        deduped.sort(key=lambda doc: doc.score, reverse=True)

        selected: list[DocumentSource] = []
        selected_urls: set[str] = set()
        selected_years: set[int] = set()

        annual_like = [
            doc
            for doc in deduped
            if doc.category in {"annual_report", "universal_registration_document"}
        ]
        for doc in annual_like:
            if len(selected) >= min(years, max_documents):
                break
            if doc.url in selected_urls:
                continue
            if doc.year is not None and doc.year in selected_years:
                continue
            selected.append(doc)
            selected_urls.add(doc.url)
            if doc.year is not None:
                selected_years.add(doc.year)

        for category in (
            "results_release",
            "investor_presentation",
            "capital_markets_day",
            "debt_or_credit",
            "sustainability",
            "other",
        ):
            for doc in deduped:
                if len(selected) >= max_documents:
                    break
                if doc.url in selected_urls or doc.category != category:
                    continue
                selected.append(doc)
                selected_urls.add(doc.url)
            if len(selected) >= max_documents:
                break

        return selected[:max_documents]

    def _select_pages(self, candidates: list[WebSnippet], *, max_web_snippets: int) -> list[WebSnippet]:
        deduped = [WebSnippet.model_validate(item.model_dump()) for item in self._dedupe_sources(candidates)]
        deduped.sort(key=lambda page: page.score, reverse=True)
        return deduped[:max_web_snippets]

    def _dedupe_sources(self, sources: list[DocumentSource | WebSnippet]) -> list[DocumentSource | WebSnippet]:
        best_by_url: dict[str, DocumentSource | WebSnippet] = {}
        for source in sources:
            current = best_by_url.get(source.url)
            if current is None or source.score > current.score:
                best_by_url[source.url] = source
        return list(best_by_url.values())

    def _company_tokens(self, company_name: str) -> list[str]:
        tokens = [
            token
            for token in re.split(r"[^a-z0-9]+", company_name.lower())
            if len(token) > 2 and token not in _GENERIC_COMPANY_TOKENS
        ]
        return tokens[:5]
