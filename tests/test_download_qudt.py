"""The QUDT download helper writes Turtle and rejects other payloads."""

import importlib.util
import urllib.request

import pytest

from tests.conftest import ROOT


def _module():
    path = ROOT / "scripts" / "download_qudt.py"
    spec = importlib.util.spec_from_file_location("download_qudt", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_url_points_at_qudt():
    module = _module()
    assert module.QUDT_UNITS_URL == "https://qudt.org/2.1/vocab/unit"


def test_download_writes_turtle(tmp_path, monkeypatch):
    module = _module()
    payload = b"@prefix qudt: <http://qudt.org/schema/qudt/> .\n"

    class _Response:
        def read(self) -> bytes:
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        assert request.full_url == module.QUDT_UNITS_URL
        assert timeout == 120.0
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "nested" / "units.ttl"
    module.download(module.QUDT_UNITS_URL, dest)
    assert dest.read_bytes() == payload


def test_download_rejects_non_turtle(tmp_path, monkeypatch):
    module = _module()

    class _Response:
        def read(self) -> bytes:
            return b"<html>nope</html>"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: _Response())
    with pytest.raises(RuntimeError, match="Turtle"):
        module.download(module.QUDT_UNITS_URL, tmp_path / "units.ttl")
