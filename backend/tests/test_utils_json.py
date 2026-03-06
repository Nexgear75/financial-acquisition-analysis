from ma_mna_analyzer.utils import extract_json_payload


def test_extract_json_payload_from_fenced_block() -> None:
    raw = '```json\n{"a": 1, "b": "x"}\n```'
    assert extract_json_payload(raw) == {"a": 1, "b": "x"}


def test_extract_json_payload_from_prose() -> None:
    raw = 'Voici la sortie: {"company_name": "ABC", "segments": []} Merci.'
    assert extract_json_payload(raw)["company_name"] == "ABC"
