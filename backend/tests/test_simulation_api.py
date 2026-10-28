"""Browser workflow: database options, preview, document upload and saved allocations."""
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import simulation as simulation_api
from app.dependencies.db import get_db
from app.main import create_app
from app.models import Material, Simulation, StockAllocation, StockUnit
from tests.test_cutting_reports_api import db_session
from tests.test_simulation_database import seeded_db, TEST_USER_ID


def test_simulation_browser_workflow(db_session, seeded_db, tmp_path, monkeypatch):
    monkeypatch.setattr(simulation_api, "MEETING_UPLOAD_ROOT", tmp_path)
    for material in db_session.scalars(select(Material)).all():
        db_session.add(StockUnit(material_part_number=material.material_part_number,
                                quantity=10000, status="WAREHOUSE", created_at=datetime.now()))
    db_session.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    headers = {"X-ERP-User-Id": str(TEST_USER_ID)}
    with TestClient(app) as client:
        options = client.get("/simulations/options/1", headers=headers)
        assert options.status_code == 200
        line = options.json()["lines"][0]
        assert line["po_line_id"] and line["outstanding_quantity"]
        request = {"project_id": 1, "fgpns": [{"po_id": line["po_id"], "fgpn_id": line["fgpn_id"],
                   "po_line_id": line["po_line_id"], "priority": 1, "requested_quantity": 1}],
                   "allocation_strategy": "PRIORITY", "safety_coefficient": 1, "stock_scope_mode": "ALL"}
        preview = client.post("/simulations/preview", headers=headers, json=request)
        assert preview.status_code == 200, preview.text
        assert preview.json()["allocation_details"]
        upload = client.post("/simulations/meeting-documents", headers=headers,
                             files={"file": ("meeting.pdf", b"%PDF-1.4\n test meeting minutes")})
        assert upload.status_code == 201
        document = upload.json()
        assert document in client.get("/simulations/meeting-documents", headers=headers).json()
        payload = {"preview_request": request, "target_date": "2026-10-28", "mtg_minutes_document_id": document["document_id"]}
        invalid = client.post("/simulations", headers=headers, json={**payload, "mtg_minutes_document_id": 999999})
        assert invalid.status_code == 422
        saved = client.post("/simulations", headers=headers, json=payload)
        assert saved.status_code == 201, saved.text
        sim_id = saved.json()["simulation_id"]
        db_session.expire_all()
        assert db_session.get(Simulation, sim_id).mtg_minutes_document_id == document["document_id"]
        allocations = db_session.scalars(select(StockAllocation).where(StockAllocation.simulation_id == sim_id)).all()
        assert allocations and all(row.allocation_type == "SIMULATION" for row in allocations)
        detail = client.get(f"/simulations/{sim_id}", headers=headers)
        assert detail.status_code == 200
        assert len(detail.json()["allocations"]) == len(allocations)
        assert any(row["simulation_id"] == sim_id for row in client.get("/simulations", headers=headers).json()["items"])
        assert client.get("/simulations/999999", headers=headers).status_code == 404
        denied = client.post("/simulations", headers={"X-ERP-Role": "WAREHOUSE_PERSONNEL"}, json=payload)
        assert denied.status_code == 403
