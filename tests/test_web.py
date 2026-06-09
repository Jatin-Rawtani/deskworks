"""Web smoke tests — no network, no model endpoint touched.

Covers the home page (incl. the thread-export control) and the /open
path guard. The /ask route is intentionally not exercised here because it
talks to the model endpoint (see CONTRIBUTING: no network in unit tests).

Flask is an optional/lazy dep (CI installs only numpy + pytest), so this
module skips cleanly when Flask isn't present.
"""
import pytest

pytest.importorskip("flask")

from deskworks.config import load
from deskworks.web import create_app


def _client():
    app = create_app(load())          # built-in defaults; corpus paths empty
    app.config.update(TESTING=True)
    return app.test_client()


def test_home_page_renders_with_export_control():
    r = _client().get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Deskworks" in body
    # the new thread-download feature is present in the UI
    assert "downloadThread" in body
    assert "Save" in body


def test_open_rejects_paths_outside_corpus():
    # with no corpus paths configured, every path is outside the allowed roots
    r = _client().get("/open", query_string={"path": "/etc/passwd"})
    assert r.status_code == 403
