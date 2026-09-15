"""Tests never consume an operator's live Alchemy credentials."""
import pytest
from app.core.config import settings


@pytest.fixture(autouse=True)
def isolate_alchemy_credentials(monkeypatch):
    monkeypatch.delenv('ALCHEMY_API_KEY', raising=False)
    monkeypatch.setattr(settings, 'ALCHEMY_API_KEY', None)
