import asyncio

import pytest


def test_python_amazon_paapi_exports_amazon_api():
    module = pytest.importorskip("python_amazon_paapi")
    assert hasattr(
        module, "AmazonApi"
    ), "python-amazon-paapi installation missing AmazonApi; check package version."


def test_get_external_trends_requires_credentials(monkeypatch):
    pytest.importorskip("python_amazon_paapi")
    monkeypatch.delenv("AMAZON_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AMAZON_SECRET_KEY", raising=False)
    monkeypatch.delenv("AMAZON_ASSOC_TAG", raising=False)
    monkeypatch.delenv("AMAZON_COUNTRY", raising=False)
    monkeypatch.setenv("AMAZON_ACCESS_KEY", "")
    monkeypatch.setenv("AMAZON_SECRET_KEY", "")
    monkeypatch.setenv("AMAZON_ASSOC_TAG", "")

    from app.research_api import get_external_trends

    with pytest.raises(ValueError):
        asyncio.run(get_external_trends("test keyword"))
