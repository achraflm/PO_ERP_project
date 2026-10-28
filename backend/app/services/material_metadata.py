"""Read material classification and units from current persisted BOM rows."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions.base import ValidationException
from app.models import BOM, BOMLine


def bom_material_metadata(db: Session) -> dict[str, tuple[str, str]]:
    rows = db.execute(select(BOMLine.material_part_number, BOMLine.part_type, BOMLine.source_unit)
                      .join(BOM, BOM.bom_id == BOMLine.bom_id).where(BOM.is_current.is_(True))).all()
    result = {}
    for part, kind, unit in rows:
        if not kind or not unit:
            continue
        value = (kind.strip().upper(), unit.strip())
        if part in result and result[part] != value:
            raise ValidationException(f"Conflicting type or unit in current BOMs for {part}. Correct the BOM before using this material.")
        result[part] = value
    return result
