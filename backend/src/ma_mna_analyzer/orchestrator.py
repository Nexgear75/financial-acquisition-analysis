from __future__ import annotations

from .config import Settings
from .discovery import DocumentDiscoveryService
from .document_fetcher import DocumentFetchService
from .models import AnalyzeRequest, AnalyzeResponse
from .openai_service import OpenAIReportService


class MnaAnalyzer:
    """Coordinate discovery, document download, extraction, and final analysis."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.discovery = DocumentDiscoveryService(settings)
        self.fetcher = DocumentFetchService(settings)
        self.openai = OpenAIReportService(settings)

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        max_docs = request.max_documents_per_company or self.settings.max_documents_per_company
        max_pages = (
            request.max_web_snippets_per_company or self.settings.max_web_snippets_per_company
        )

        acquirer_discovery = self.discovery.discover(
            request.acquirer,
            years=request.years,
            max_documents=max_docs,
            max_web_snippets=max_pages,
            strict_official_sources_only=request.strict_official_sources_only,
            manual_sources_only=request.manual_sources_only,
        )
        target_discovery = self.discovery.discover(
            request.target,
            years=request.years,
            max_documents=max_docs,
            max_web_snippets=max_pages,
            strict_official_sources_only=request.strict_official_sources_only,
            manual_sources_only=request.manual_sources_only,
        )

        acquirer_bundle = self.fetcher.materialize(
            acquirer_discovery,
            force_refresh=request.force_refresh,
        )
        target_bundle = self.fetcher.materialize(
            target_discovery,
            force_refresh=request.force_refresh,
        )

        acquirer_bundle = acquirer_bundle.model_copy(
            update={
                "documents": self.openai.upload_documents(
                    acquirer_bundle.documents,
                    force_refresh=request.force_refresh,
                )
            }
        )
        target_bundle = target_bundle.model_copy(
            update={
                "documents": self.openai.upload_documents(
                    target_bundle.documents,
                    force_refresh=request.force_refresh,
                )
            }
        )

        acquirer_extraction = self.openai.extract_company(
            company=request.acquirer,
            bundle=acquirer_bundle,
            years=request.years,
            language=request.language,
            model=request.extraction_model or self.settings.extraction_model,
        )
        target_extraction = self.openai.extract_company(
            company=request.target,
            bundle=target_bundle,
            years=request.years,
            language=request.language,
            model=request.extraction_model or self.settings.extraction_model,
        )

        analysis_markdown, response_id = self.openai.generate_analysis(
            request=request,
            acquirer_bundle=acquirer_bundle,
            target_bundle=target_bundle,
            acquirer_extraction=acquirer_extraction,
            target_extraction=target_extraction,
        )

        warnings = []
        warnings.extend(acquirer_bundle.warnings)
        warnings.extend(target_bundle.warnings)
        status = "warning" if warnings else "ok"

        return AnalyzeResponse(
            status=status,
            acquirer_discovery=acquirer_bundle,
            target_discovery=target_bundle,
            acquirer_extraction=acquirer_extraction,
            target_extraction=target_extraction,
            analysis_markdown=analysis_markdown,
            analysis_response_id=response_id,
            warnings=warnings,
        )
