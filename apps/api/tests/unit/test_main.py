from fastapi.testclient import TestClient

from app.main import create_app


def test_root_identifies_api() -> None:
    response = TestClient(create_app()).get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Creative Loop API",
        "status": "ok",
        "health": "/healthz",
        "docs": "/docs",
    }
