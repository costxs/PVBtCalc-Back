import io
import re
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.schemas import LinearExportRequest
from app.services import export_workbook_linear as ewl

router = APIRouter(prefix="/export/linear", tags=["Export Linear"])


@router.post("")
@router.post("/")
def export_linear_workbook(data: LinearExportRequest, include_images: bool = Query(True)):
    xlsx_bytes = ewl.build_linear_workbook(data, include_images=include_images)
    suffix = "" if include_images else "_TablesOnly"
    ids = [c.id for c in data.curves] or [c.id for c in data.experimental_curves]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", "_".join(ids))[:60].strip("_") or "---"
    filename = f"PVBtCalc_Linear_{stem}{suffix}_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
