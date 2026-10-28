"""Verify CutMan browser endpoints persist uploads and consumption."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.dependencies.db import get_db
from app.main import create_app
from tests.test_simulation_database import seeded_db, TEST_USER_ID
from tests.test_cutting_reports import production, SOURCE, MATERIAL


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_cutman_database_workflow(db_session, production):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    headers = {"X-ERP-User-Id": str(TEST_USER_ID)}
    with TestClient(app) as client:
        launches = client.get("/stock/cutting-reports/launches", headers=headers)
        assert launches.status_code == 200
        assert launches.json() == [{"launch_id": production, "planned_date": "2026-08-01", "status": "IN_PROGRESS"}]
        content = SOURCE.read_bytes()
        uploaded = client.post("/stock/cutting-reports", headers=headers,
                               files={"file": (SOURCE.name, content)})
        assert uploaded.status_code == 200
        report_id = uploaded.json()["report_id"]
        # Force subsequent requests to read persisted state rather than ORM cache.
        db_session.expire_all()
        history = client.get("/stock/cutting-reports", headers=headers)
        assert history.status_code == 200
        assert history.json()[0]["report_id"] == report_id
        source = client.get(f"/stock/cutting-reports/{report_id}/source", headers=headers)
        assert source.status_code == 200 and source.content == content
        duplicate = client.post("/stock/cutting-reports", headers=headers,
                                files={"file": (SOURCE.name, content)})
        assert duplicate.json()["already_imported"] is True
        # The browser supplies no unit: the server must derive it from database metadata.
        payload = {"launch_id": production, "confirm_usage_is_consumption": True}
        posted = client.post(f"/stock/cutting-reports/{report_id}/post", headers=headers, json=payload)
        assert posted.status_code == 200
        assert posted.json()["posted_launch_id"] == production
        assert posted.json()["confirmed_usage_unit"] == "m"
        assert posted.json()["lines"][0]["unit"] == "m"
        db_session.expire_all()
        history = client.get("/stock/cutting-reports", headers=headers).json()
        assert history[0]["posted_at"] is not None
        summary = client.get("/stock/summary", headers=headers).json()
        material = next(item for item in summary["items"] if item["material_part_number"] == MATERIAL)
        assert Decimal(material["production_quantity"]) == Decimal("32.7420")
        assert client.post(f"/stock/cutting-reports/{report_id}/post", headers=headers, json=payload).status_code == 409


def test_launch_options_are_permission_checked_and_handle_empty_database(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        response = client.get("/stock/cutting-reports/launches", headers={"X-ERP-Role": "LAUNCH_ENGINEER"})
        assert response.status_code == 200 and response.json() == []
        response = client.get("/stock/cutting-reports/launches", headers={"X-ERP-Role": "WAREHOUSE_PERSONNEL"})
        assert response.status_code == 403
