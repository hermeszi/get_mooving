"""
refresh_onemap_token.py talks to a real login endpoint and rewrites a
real file — both mocked/redirected here. requests.post is mocked
(same pattern as test_onemap.py); ENV_FILE is redirected to a tmp_path
file so a test run never touches the project's actual .env.
"""

import requests
import pytest

import refresh_onemap_token as rt


def _response(status_code=200, json_data=None, http_error=False):
    response = requests.Response()
    response.status_code = status_code

    if http_error:
        error = requests.exceptions.HTTPError(f"HTTP {status_code}")
        error.response = response

        def raise_for_status():
            raise error

        response.raise_for_status = raise_for_status
    else:
        response.raise_for_status = lambda: None

    response.json = lambda: json_data or {}
    return response


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setattr(rt, "ENV_FILE", path)
    return path


def test_refresh_missing_credentials(monkeypatch, env_file):
    monkeypatch.delenv("ONEMAP_EMAIL", raising=False)
    monkeypatch.delenv("ONEMAP_PASSWORD", raising=False)
    monkeypatch.setattr(rt, "load_dotenv", lambda: None)

    result = rt.refresh()

    assert result == {
        "error": "missing_credentials",
        "message": "Set ONEMAP_EMAIL and ONEMAP_PASSWORD in .env first (see SETUP.md step 5).",
    }


def test_refresh_success_writes_token_in_place(monkeypatch, env_file, mocker):
    env_file.write_text("ONEMAP_TOKEN=old-token\nSOME_OTHER_VAR=keep-me\n")
    monkeypatch.setenv("ONEMAP_EMAIL", "you@example.com")
    monkeypatch.setenv("ONEMAP_PASSWORD", "hunter2")
    monkeypatch.setattr(rt, "load_dotenv", lambda: None)

    mocker.patch(
        "refresh_onemap_token.requests.post",
        return_value=_response(json_data={"access_token": "new-token", "expiry_timestamp": "1789488744"}),
    )

    result = rt.refresh()

    assert result["status"] == "refreshed"
    assert result["expires_at"] is not None

    contents = env_file.read_text()
    assert "ONEMAP_TOKEN=new-token\n" in contents
    assert "SOME_OTHER_VAR=keep-me\n" in contents
    assert "old-token" not in contents


def test_refresh_adds_token_line_if_missing(monkeypatch, env_file, mocker):
    env_file.write_text("SOME_OTHER_VAR=keep-me\n")
    monkeypatch.setenv("ONEMAP_EMAIL", "you@example.com")
    monkeypatch.setenv("ONEMAP_PASSWORD", "hunter2")
    monkeypatch.setattr(rt, "load_dotenv", lambda: None)

    mocker.patch(
        "refresh_onemap_token.requests.post",
        return_value=_response(json_data={"access_token": "new-token"}),
    )

    rt.refresh()

    contents = env_file.read_text()
    assert "ONEMAP_TOKEN=new-token" in contents
    assert "SOME_OTHER_VAR=keep-me" in contents


def test_refresh_bad_credentials_raises_login_failed(monkeypatch, env_file, mocker):
    monkeypatch.setenv("ONEMAP_EMAIL", "you@example.com")
    monkeypatch.setenv("ONEMAP_PASSWORD", "wrong-password")
    monkeypatch.setattr(rt, "load_dotenv", lambda: None)

    mocker.patch(
        "refresh_onemap_token.requests.post",
        return_value=_response(status_code=401, http_error=True),
    )

    result = rt.refresh()

    assert result["error"] == "onemap_login_failed"


def test_refresh_network_error_raises_unreachable(monkeypatch, env_file, mocker):
    monkeypatch.setenv("ONEMAP_EMAIL", "you@example.com")
    monkeypatch.setenv("ONEMAP_PASSWORD", "hunter2")
    monkeypatch.setattr(rt, "load_dotenv", lambda: None)

    mocker.patch(
        "refresh_onemap_token.requests.post",
        side_effect=requests.exceptions.ConnectionError("no route to host"),
    )

    result = rt.refresh()

    assert result["error"] == "onemap_unreachable"


def test_refresh_response_missing_access_token(monkeypatch, env_file, mocker):
    monkeypatch.setenv("ONEMAP_EMAIL", "you@example.com")
    monkeypatch.setenv("ONEMAP_PASSWORD", "hunter2")
    monkeypatch.setattr(rt, "load_dotenv", lambda: None)

    mocker.patch(
        "refresh_onemap_token.requests.post",
        return_value=_response(json_data={"unexpected": "shape"}),
    )

    result = rt.refresh()

    assert result["error"] == "onemap_login_failed"


def test_write_token_to_env_creates_file_if_missing(env_file):
    assert not env_file.exists()

    rt.write_token_to_env("brand-new-token")

    assert env_file.read_text() == "ONEMAP_TOKEN=brand-new-token\n"
