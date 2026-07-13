from noesis_agent.config.settings import settings
from noesis_agent.services.api_server import APIServer


def test_operator_url_converts_bind_all_address_to_browser_address(monkeypatch) -> None:
    monkeypatch.setattr(settings, "host", "0.0.0.0")
    monkeypatch.setattr(settings, "port", 8080)
    assert APIServer.operator_url() == "http://127.0.0.1:8080/operator"
