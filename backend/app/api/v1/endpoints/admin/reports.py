"""CSV/Excel exports and validated catalogue imports."""
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from app.api.v1.dependencies import require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.models.user import User
from app.schemas.admin_ops import ExportQuery
from app.services import analytics, exports, imports

router=APIRouter()
DATASETS={"products":"Products","inventory":"Inventory","inventory_history":"Stock movement history","orders":"Orders","order_items":"Order line items","customers":"Customers","sales":"Sales by period"}

@router.get("/datasets", dependencies=[Depends(require_permission(Permission.REPORTS_VIEW))])
def datasets(): return [{"key":k,"label":v} for k,v in DATASETS.items()]

@router.get("/export/{filename}")
def export_data(filename:str,query:Annotated[ExportQuery,Query()],actor:User=Depends(require_permission(Permission.REPORTS_VIEW)),db:Session=Depends(get_db)):
    if "." not in filename: from app.services.exceptions import InvalidRequestError; raise InvalidRequestError("Use a .csv or .xlsx filename")
    dataset,fmt=filename.rsplit(".",1)
    if dataset not in DATASETS or fmt not in {"csv","xlsx"}: from app.services.exceptions import InvalidRequestError; raise InvalidRequestError("Unknown export")
    window=analytics.resolve_range(query.preset,date_from=query.date_from,date_to=query.date_to)
    header,rows=exports.build_dataset(db,dataset,window=window,granularity=query.granularity,include_inactive=query.include_inactive)
    if fmt=="csv":
        return StreamingResponse(exports.stream_csv(header,rows),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{exports.timestamped_filename(dataset,"csv")}"'})
    body,truncated=exports.build_excel(header,rows,title=dataset.title())
    headers={"Content-Disposition":f'attachment; filename="{exports.timestamped_filename(dataset,"xlsx")}"'}
    if truncated: headers["X-Export-Truncated"]="true"
    return Response(body,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers=headers)

@router.get("/import/template.csv")
def import_template(actor:User=Depends(require_permission(Permission.PRODUCT_CREATE))):
    import csv,io
    from app.services.imports import TEMPLATE_COLUMNS
    out=io.StringIO(); csv.writer(out).writerow(TEMPLATE_COLUMNS)
    return Response("\ufeff"+out.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=product-import-template.csv"})

@router.post("/import")
async def upload_import(file:UploadFile=File(...),actor:User=Depends(require_permission(Permission.PRODUCT_CREATE)),db:Session=Depends(get_db)):
    content=await file.read()
    if len(content)>10*1024*1024: from app.services.exceptions import InvalidRequestError; raise InvalidRequestError("Import files are limited to 10 MB")
    batch=imports.create_batch(db,file.filename or "products.csv",content,actor=actor)
    return _batch_read(batch)

def _batch_read(batch):
    return {"id":batch.id,"filename":batch.filename,"status":batch.status,"total_rows":batch.total_rows,"valid_rows":batch.valid_rows,"warning_rows":batch.warning_rows,"error_rows":batch.error_rows,"created_count":batch.created_count,"updated_count":batch.updated_count,"error_summary":batch.error_summary,"rows":batch.rows_json or []}

@router.post("/import/{batch_id}/commit")
def commit_import(batch_id:uuid.UUID,actor:User=Depends(require_permission(Permission.PRODUCT_CREATE)),db:Session=Depends(get_db)):
    return _batch_read(imports.commit_batch(db,batch_id,actor=actor))

@router.post("/import/{batch_id}/cancel")
def cancel_import(batch_id:uuid.UUID,actor:User=Depends(require_permission(Permission.PRODUCT_CREATE)),db:Session=Depends(get_db)):
    return {"detail":f"Import batch {imports.cancel_batch(db,batch_id).status}"}

@router.get("/import/{batch_id}/errors.csv")
def import_errors(batch_id:uuid.UUID,actor:User=Depends(require_permission(Permission.PRODUCT_CREATE)),db:Session=Depends(get_db)):
    from app.services.imports import get_batch
    header,rows=imports.error_report_rows(get_batch(db,batch_id))
    import itertools
    return StreamingResponse(exports.stream_csv(header,iter(rows)),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="import-errors-{batch_id}.csv"'})
