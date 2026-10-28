"""Exercise the monitoring API against persisted material records."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.dependencies.db import get_db
from app.main import create_app
from app.models import Material, MaterialType


@pytest.fixture()
def stock_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(MaterialType(material_type_id=1, name="m", unit="ME", status="Active"))
        db.add(Material(id=1, material_part_number="TEST-ROLL", description="Test roll",
                        material_type_id=1, status="Active", unit_price=Decimal("2.5"),
                        critical_threshold=None))
        db.commit()
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield client, db
    engine.dispose()


def test_summary_and_threshold_persistence(stock_client):
    client, db = stock_client
    response = client.get("/stock/summary")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["material_type"] == "m"
    assert Decimal(item["critical_threshold"]) == 0
    assert Decimal(item["unit_price"]) == Decimal("2.5")
    assert Decimal(item["warehouse_quantity"]) == 0
    response = client.patch("/stock/materials/TEST-ROLL/threshold",
                            headers={"X-ERP-Role": "LAUNCH_ENGINEER"},
                            json={"critical_threshold": "123.4567"})
    assert response.status_code == 200
    db.expire_all()
    assert db.get(Material, 1).critical_threshold == Decimal("123.4567")
    item = client.get("/stock/summary").json()["items"][0]
    assert Decimal(item["critical_threshold"]) == Decimal("123.4567")


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "1000000", "0.00001", ""])
def test_threshold_rejects_invalid_values(stock_client, value):
    client, _ = stock_client
    response = client.patch("/stock/materials/TEST-ROLL/threshold",
                            headers={"X-ERP-Role": "LAUNCH_ENGINEER"},
                            json={"critical_threshold": value})
    assert response.status_code == 422


def test_threshold_permissions_and_missing_material(stock_client):
    client, _ = stock_client
    response = client.patch("/stock/materials/TEST-ROLL/threshold",
                            headers={"X-ERP-Role": "PLANT_MANAGER"},
                            json={"critical_threshold": "10"})
    assert response.status_code == 403
    response = client.patch("/stock/materials/MISSING/threshold",
                            headers={"X-ERP-Role": "LAUNCH_MANAGER"},
                            json={"critical_threshold": "10"})
    assert response.status_code == 404
