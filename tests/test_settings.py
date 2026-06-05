from app.settings import Settings


def test_settings_default_model() -> None:
    settings = Settings()

    assert settings.gemini_live_model == "gemini-3.1-flash-live-preview"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_settings_accepts_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "custom-live-model")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9001")

    settings = Settings()

    assert settings.gemini_api_key == "test-key"
    assert settings.gemini_live_model == "custom-live-model"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9001
