import io
import re
import zipfile
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.schemas import RadialExportRequest
from app.services import export_workbook as ewb
from app.services import export_plots as ep

router = APIRouter(prefix="/export/radial", tags=["Export Radial"])


@router.post("")
@router.post("/")
def export_radial_workbook(data: RadialExportRequest, include_images: bool = Query(True)):
    xlsx_bytes = ewb.build_workbook(data, include_images=include_images)
    suffix = "" if include_images else "_TablesOnly"
    filename = f"PVBtCalc_Radial_{data.inputs.simulation_id or '---'}{suffix}_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/figures")
def export_radial_figures(data: RadialExportRequest, size: Literal["single", "double"] = Query("single")):
    figures = ewb.generate_all_figures(data, size=size)

    sim_id = re.sub(r'[\\/:*?"<>|\s]+', "_", str(data.inputs.simulation_id or "---"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for stem, png_bytes in figures.items():
            zf.writestr(f"Radial_{sim_id}_{stem}.png", png_bytes)
    buf.seek(0)

    filename = f"PVBtCalc_Radial_Figures_{data.inputs.simulation_id or '---'}_{date.today().isoformat()}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
