from __future__ import annotations

from typing import Sequence

from openai import OpenAI

from .config import Settings
from .models import AnalyzeRequest, CompanyDiscoveryBundle, CompanyExtraction, DownloadedDocument
from .prompt_builder import build_analysis_prompt, build_extraction_prompt
from .utils import extract_json_payload


class OpenAIReportService:
    """Thin wrapper around the OpenAI Responses API and Files API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)

    def upload_documents(
        self,
        documents: Sequence[DownloadedDocument],
        *,
        force_refresh: bool = False,
    ) -> list[DownloadedDocument]:
        uploaded: list[DownloadedDocument] = []
        for document in documents:
            if document.openai_file_id and not force_refresh:
                uploaded.append(document)
                continue
            if not document.local_path:
                uploaded.append(document)
                continue
            with open(document.local_path, "rb") as handle:
                file_obj = self.client.files.create(file=handle, purpose="user_data")
            uploaded.append(
                DownloadedDocument(
                    **document.model_dump(exclude={"openai_file_id"}),
                    openai_file_id=file_obj.id,
                )
            )
        return uploaded

    def extract_company(
        self,
        *,
        company,
        bundle: CompanyDiscoveryBundle,
        years: int,
        language: str,
        model: str | None = None,
    ) -> CompanyExtraction:
        prompt = build_extraction_prompt(
            company=company,
            bundle=bundle,
            years=years,
            language=language,
        )
        raw_text, _ = self.request_text(
            prompt=prompt,
            documents=bundle.documents,
            model=model or self.settings.extraction_model,
            allow_web_search=False,
        )
        try:
            payload = extract_json_payload(raw_text)
        except Exception:
            payload = self._repair_json_payload(raw_text=raw_text, company_name=company.name)
        payload = self._coerce_extraction_payload(payload=payload, company_name=company.name)
        extraction = CompanyExtraction.model_validate(payload)
        if bundle.warnings:
            extraction.warnings.extend(bundle.warnings)
        return extraction

    def generate_analysis(
        self,
        *,
        request: AnalyzeRequest,
        acquirer_bundle: CompanyDiscoveryBundle,
        target_bundle: CompanyDiscoveryBundle,
        acquirer_extraction: CompanyExtraction,
        target_extraction: CompanyExtraction,
    ) -> tuple[str, str | None]:
        prompt = build_analysis_prompt(
            request=request,
            acquirer_bundle=acquirer_bundle,
            target_bundle=target_bundle,
            acquirer_extraction=acquirer_extraction,
            target_extraction=target_extraction,
        )
        documents = list(acquirer_bundle.documents) + list(target_bundle.documents)
        return self.request_text(
            prompt=prompt,
            documents=documents,
            model=request.model or self.settings.openai_model,
            allow_web_search=request.allow_openai_web_search,
        )

    def request_text(
        self,
        *,
        prompt: str,
        documents: Sequence[DownloadedDocument],
        model: str,
        allow_web_search: bool,
    ) -> tuple[str, str | None]:
        content: list[dict] = [{"type": "input_text", "text": prompt}]
        for document in documents:
            if document.openai_file_id:
                content.append({"type": "input_file", "file_id": document.openai_file_id})

        kwargs: dict = {
            "model": model,
            "input": [{"role": "user", "content": content}],
        }
        if allow_web_search:
            kwargs["tools"] = [{"type": "web_search"}]

        response = self.client.responses.create(**kwargs)
        output_text = getattr(response, "output_text", None) or self._fallback_output_text(response)
        return output_text, getattr(response, "id", None)

    def _repair_json_payload(self, *, raw_text: str, company_name: str) -> dict:
        repair_prompt = f"""
Transforme le texte suivant en un objet JSON valide pour l'entreprise {company_name}.
Règles :
- retourne UNIQUEMENT un objet JSON,
- garde uniquement des faits étayés ; sinon mets null ou liste vide,
- respecte cette structure minimale :
  company_name, business_description, reporting_currency, fiscal_year_end,
  segments, geographies, key_risks, shareholding_notes, capital_structure_notes,
  historical_metrics, latest_snapshot, source_table, warnings.
- latest_snapshot doit contenir au moins {{"period": "latest_public"}}.

Texte à réparer :
{raw_text}
""".strip()
        repaired_text, _ = self.request_text(
            prompt=repair_prompt,
            documents=[],
            model=self.settings.extraction_model,
            allow_web_search=False,
        )
        return extract_json_payload(repaired_text)

    def _coerce_extraction_payload(self, *, payload: dict, company_name: str) -> dict:
        payload.setdefault("company_name", company_name)
        payload.setdefault("business_description", None)
        payload.setdefault("reporting_currency", None)
        payload.setdefault("fiscal_year_end", None)
        payload.setdefault("segments", [])
        payload.setdefault("geographies", [])
        payload.setdefault("key_risks", [])
        payload.setdefault("shareholding_notes", [])
        payload.setdefault("capital_structure_notes", [])
        payload.setdefault("historical_metrics", [])
        payload.setdefault("source_table", [])
        payload.setdefault("warnings", [])
        latest_snapshot = payload.get("latest_snapshot") or {"period": "latest_public"}
        latest_snapshot.setdefault("period", "latest_public")
        latest_snapshot.setdefault("notes", [])
        latest_snapshot.setdefault("source_refs", [])
        payload["latest_snapshot"] = latest_snapshot
        return payload

    def _fallback_output_text(self, response) -> str:
        chunks: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(text)
        return "\n".join(chunks)
