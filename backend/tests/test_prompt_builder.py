from ma_mna_analyzer.models import AnalyzeRequest, CompanyDiscoveryBundle, CompanyExtraction, CompanyRequest
from ma_mna_analyzer.prompt_builder import build_analysis_prompt


def test_analysis_prompt_mentions_both_companies() -> None:
    request = AnalyzeRequest(
        acquirer=CompanyRequest(name="Buyer SA"),
        target=CompanyRequest(name="Target NV"),
    )
    bundle_a = CompanyDiscoveryBundle(company_name="Buyer SA")
    bundle_t = CompanyDiscoveryBundle(company_name="Target NV")
    extraction_a = CompanyExtraction(company_name="Buyer SA")
    extraction_t = CompanyExtraction(company_name="Target NV")

    prompt = build_analysis_prompt(
        request=request,
        acquirer_bundle=bundle_a,
        target_bundle=bundle_t,
        acquirer_extraction=extraction_a,
        target_extraction=extraction_t,
    )
    assert "Buyer SA" in prompt
    assert "Target NV" in prompt
