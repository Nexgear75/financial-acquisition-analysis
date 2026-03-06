from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


SourceKind = Literal["pdf", "html", "manual", "search_result"]
DocumentCategory = Literal[
    "annual_report",
    "universal_registration_document",
    "results_release",
    "investor_presentation",
    "capital_markets_day",
    "debt_or_credit",
    "sustainability",
    "other",
]


class CompanyRequest(BaseModel):
    name: str = Field(..., description="Registered or common company name")
    country: str | None = None
    ticker: str | None = None
    isin: str | None = None
    official_website: HttpUrl | None = None
    investor_relations_url: HttpUrl | None = None
    extra_document_urls: list[HttpUrl] = Field(default_factory=list)
    extra_page_urls: list[HttpUrl] = Field(default_factory=list)
    sector_hint: str | None = None


class AnalyzeRequest(BaseModel):
    acquirer: CompanyRequest
    target: CompanyRequest
    language: str = Field(default="fr")
    years: int = Field(default=5, ge=1, le=10)
    model: str | None = None
    extraction_model: str | None = None
    max_documents_per_company: int | None = Field(default=None, ge=1, le=12)
    max_web_snippets_per_company: int | None = Field(default=None, ge=0, le=12)
    allow_openai_web_search: bool = True
    strict_official_sources_only: bool = False
    manual_sources_only: bool = False
    force_refresh: bool = False
    perspective: str = Field(default="comité d’investissement")
    prudence_level: Literal["conservateur", "équilibré", "offensif"] = "conservateur"
    return_intermediate_outputs: bool = True


class DocumentSource(BaseModel):
    company_name: str
    title: str
    url: str
    source_kind: SourceKind
    category: DocumentCategory = "other"
    discovered_from: str | None = None
    is_official_domain: bool = True
    year: int | None = None
    score: float = 0.0


class DownloadedDocument(DocumentSource):
    local_path: str | None = None
    bytes_size: int | None = None
    sha256: str | None = None
    openai_file_id: str | None = None


class WebSnippet(DocumentSource):
    text_excerpt: str | None = None


class CompanyDiscoveryBundle(BaseModel):
    company_name: str
    official_website: str | None = None
    investor_relations_url: str | None = None
    documents: list[DownloadedDocument] = Field(default_factory=list)
    web_snippets: list[WebSnippet] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceTableRow(BaseModel):
    id: str | None = None
    document: str
    source_type: str | None = None
    date: str | None = None
    url: str | None = None
    pages_or_location: str | None = None
    why_used: str | None = None


class MetricObservation(BaseModel):
    period: str
    currency: str | None = None
    revenue: float | None = None
    organic_growth_pct: float | None = None
    ebitda: float | None = None
    ebit: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    capex: float | None = None
    free_cash_flow: float | None = None
    cash_and_equivalents: float | None = None
    gross_debt: float | None = None
    net_debt: float | None = None
    shares_outstanding: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    notes: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class CompanyExtraction(BaseModel):
    company_name: str
    business_description: str | None = None
    reporting_currency: str | None = None
    fiscal_year_end: str | None = None
    segments: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    shareholding_notes: list[str] = Field(default_factory=list)
    capital_structure_notes: list[str] = Field(default_factory=list)
    historical_metrics: list[MetricObservation] = Field(default_factory=list)
    latest_snapshot: MetricObservation = Field(
        default_factory=lambda: MetricObservation(period="latest_public")
    )
    source_table: list[SourceTableRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    status: Literal["ok", "warning", "error"] = "ok"
    acquirer_discovery: CompanyDiscoveryBundle
    target_discovery: CompanyDiscoveryBundle
    acquirer_extraction: CompanyExtraction
    target_extraction: CompanyExtraction
    analysis_markdown: str
    analysis_response_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
