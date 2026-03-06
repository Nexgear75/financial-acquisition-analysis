import pytest

from ma_mna_analyzer.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_settings_raises_in_production_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_settings()


def test_get_settings_reads_dotenv_in_non_production(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = get_settings()

    assert settings.openai_api_key == "test-key"
