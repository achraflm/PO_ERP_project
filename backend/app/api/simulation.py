"""Simulation API router."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from decimal import Decimal
from app.models import Document, FGPN, LaunchFGPN, PurchaseOrder, PurchaseOrderLine, Simulation
from app.policies import policy_engine
from app.exceptions.base import NotFoundException
from app.exceptions.base import ValidationException
from pathlib import Path
from datetime import datetime
from uuid import uuid4

MEETING_UPLOAD_ROOT = Path("uploads") / "meeting-minutes"

from app.dependencies.auth import actor_user_id_or_system, get_current_policy_actor
from app.dependencies.db import get_db
from app.policies import PolicyActor
from app.schemas.simulation import (
    LaunchReviewResult,
    LaunchSimulationResponse,
    SimulationPreviewRequest,
    SimulationPreviewResult,
    SimulationSaveRequest,
    SimulationSaveResponse,
)
from app.services import material_simulation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulations", tags=["simulation"])


@router.get("/options/{project_id}")
def simulation_options(project_id: int, db: Annotated[Session, Depends(get_db)],
                       actor: Annotated[PolicyActor, Depends(get_current_policy_actor)]):
    policy_engine.require(actor, "simulation.run")
    rows = db.execute(select(PurchaseOrder, PurchaseOrderLine, FGPN)
        .join(PurchaseOrderLine, PurchaseOrderLine.po_version_id == PurchaseOrder.current_version_id)
        .join(FGPN, FGPN.fgpn_id == PurchaseOrderLine.fgpn_id)
        .where(FGPN.project_id == project_id)
        .order_by(PurchaseOrder.po_id, PurchaseOrderLine.po_line_id)).all()
    planned = dict(db.execute(select(LaunchFGPN.po_line_id, func.sum(LaunchFGPN.planned_quantity))
                             .group_by(LaunchFGPN.po_line_id)).all())
    return {"project_id": project_id, "lines": [
        {"po_id": po.po_id, "po_number": po.po_number, "po_line_id": line.po_line_id,
         "fgpn_id": fgpn.fgpn_id, "fgpn_code": fgpn.fgpn_code, "description": fgpn.description,
         "ordered_quantity": str(line.ordered_quantity), "already_planned_quantity": str(planned.get(line.po_line_id, 0)),
         "outstanding_quantity": str(max(Decimal(0), line.ordered_quantity - planned.get(line.po_line_id, 0)))}
        for po, line, fgpn in rows]}


@router.get("/meeting-documents")
def meeting_documents(db: Annotated[Session, Depends(get_db)],
                      actor: Annotated[PolicyActor, Depends(get_current_policy_actor)]):
    policy_engine.require(actor, "simulation.run")
    return [{"document_id": doc.document_id, "file_name": doc.file_name}
            for doc in db.scalars(select(Document).where(Document.document_type == "MTG_MINUTES")
                                  .order_by(Document.uploaded_at.desc())).all()]


@router.post("/meeting-documents", status_code=201)
async def upload_meeting_document(db: Annotated[Session, Depends(get_db)],
                                 actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
                                 file: UploadFile = File(...)):
    policy_engine.require(actor, "simulation.run")
    content = await file.read(20 * 1024 * 1024 + 1)
    if not content.startswith(b"%PDF-") or len(content) > 20 * 1024 * 1024:
        raise ValidationException("Upload a PDF meeting-minutes document no larger than 20 MB.")
    actor_id = actor_user_id_or_system(db, actor)
    MEETING_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    path = MEETING_UPLOAD_ROOT / f"{uuid4()}.pdf"
    path.write_bytes(content)
    try:
        doc = Document(document_type="MTG_MINUTES", file_name=Path(file.filename or "meeting.pdf").name[:255],
                       file_path=str(path), version=1, uploaded_at=datetime.now(), uploaded_by=actor_id)
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return {"document_id": doc.document_id, "file_name": doc.file_name}


def saved_result(sim):
    return {"simulation_id": sim.simulation_id, "target_date": sim.target_date,
            "created_at": sim.created_at, "is_feasible": sim.is_feasible,
            "simulation_mode": sim.simulation_mode, "safety_coefficient": str(sim.safety_coefficient),
            "mtg_minutes_document_id": sim.mtg_minutes_document_id,
            "fgpns": [{"po_number": row.purchase_order.po_number, "fgpn_code": row.fgpn.fgpn_code,
                       "quantity": str(row.simulation_quantity), "launchable_quantity": str(row.launchable_quantity)}
                      for row in sim.selected_fgpns],
            "allocations": [{"stock_unit_id": row.stock_unit_id, "quantity": str(row.allocated_quantity),
                            "source": row.source_location, "status": row.status}
                            for row in sim.stock_allocations]}


@router.get("")
def list_simulations(db: Annotated[Session, Depends(get_db)],
                     actor: Annotated[PolicyActor, Depends(get_current_policy_actor)]):
    policy_engine.require(actor, "simulation.view")
    return {"items": [saved_result(sim) for sim in db.scalars(select(Simulation)
                    .order_by(Simulation.created_at.desc())).all()]}


@router.get("/{simulation_id}")
def get_simulation(simulation_id: int, db: Annotated[Session, Depends(get_db)],
                   actor: Annotated[PolicyActor, Depends(get_current_policy_actor)]):
    policy_engine.require(actor, "simulation.view")
    sim = db.get(Simulation, simulation_id)
    if sim is None:
        raise NotFoundException("Simulation not found.")
    return saved_result(sim)


@router.post("/preview", response_model=SimulationPreviewResult)
def preview_simulation(
    request: SimulationPreviewRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationPreviewResult:
    """Run a read-only material simulation based on requested FGPNs and allocation strategy."""
    return material_simulation_service.preview_simulation(db, request, actor=actor)


@router.post("", response_model=SimulationSaveResponse, status_code=status.HTTP_201_CREATED)
def save_simulation(
    request: SimulationSaveRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationSaveResponse:
    """Save an official simulation result and its stock allocations."""
    user_id = str(actor_user_id_or_system(db, actor))
    return material_simulation_service.save_simulation(db, request, user_id, actor=actor)


@router.post("/{simulation_id}/launch-review", response_model=LaunchReviewResult)
def review_simulation_for_launch(
    simulation_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> LaunchReviewResult:
    """Review whether a saved simulation can still be launched with current stock."""
    return material_simulation_service.review_simulation_for_launch(
        db,
        simulation_id,
        actor=actor,
    )


@router.post("/{simulation_id}/launch", response_model=LaunchSimulationResponse)
def launch_saved_simulation(
    simulation_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> LaunchSimulationResponse:
    """Confirm a saved simulation as a launch and issue stock to production."""
    return material_simulation_service.launch_saved_simulation(db, simulation_id, actor=actor)
