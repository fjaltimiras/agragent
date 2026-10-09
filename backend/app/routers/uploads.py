import logging
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from app.database import get_db
from app.services.document import parse_pdf_analysis, parse_excel_analysis, detect_analysis_type
from app.models.schemas import UploadResponse

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.ms-excel": "excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    "application/octet-stream": "auto",
    "text/plain": "text",
}

MAX_FILE_SIZE_MB = 10


@router.post("/analysis", response_model=UploadResponse)
async def upload_analysis(
    file: UploadFile = File(...),
    analysis_type: str = Form(default="auto"),
    user_id: str = Form(...),
    field_id: Optional[str] = Form(default=None),
):
    """
    Upload a soil/foliar/water analysis file (PDF or Excel).
    Parses the file, stores in Supabase Storage, and saves metadata to field_analyses table.
    Returns the analysis_id, detected type, and parsed data.
    """
    db = get_db()

    # Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo excede el tamaño máximo permitido de {MAX_FILE_SIZE_MB} MB",
        )

    if not file_bytes:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    filename = file.filename or "analysis_file"
    content_type = file.content_type or "application/octet-stream"

    # Determine file format
    filename_lower = filename.lower()
    is_pdf = filename_lower.endswith(".pdf") or content_type == "application/pdf"
    is_excel = filename_lower.endswith((".xlsx", ".xls")) or "excel" in content_type or "spreadsheet" in content_type

    if not is_pdf and not is_excel:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Por favor sube un archivo PDF o Excel (.xlsx, .xls)",
        )

    # Parse the file
    if is_pdf:
        raw_parse = parse_pdf_analysis(file_bytes, analysis_type if analysis_type != "auto" else "soil")
    else:
        raw_parse = parse_excel_analysis(file_bytes, analysis_type if analysis_type != "auto" else "soil")

    # Auto-detect analysis type if needed
    if analysis_type == "auto":
        content_preview = raw_parse.get("raw_text", "")
        detected_type = detect_analysis_type(filename, content_preview)
        # Re-parse with correct type if needed
        if detected_type != (analysis_type if analysis_type != "auto" else "soil"):
            if is_pdf:
                raw_parse = parse_pdf_analysis(file_bytes, detected_type)
            else:
                raw_parse = parse_excel_analysis(file_bytes, detected_type)
        final_type = detected_type
    else:
        final_type = analysis_type

    if final_type not in ("soil", "foliar", "water"):
        final_type = "soil"

    # Generate analysis ID
    analysis_id = str(uuid.uuid4())

    # Upload to Supabase Storage
    storage_path = f"{user_id}/{analysis_id}/{filename}"
    file_url = None
    try:
        storage_result = db.storage.from_("analyses").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )
        # Get public URL (or signed URL since bucket is private)
        file_url = storage_path
    except Exception as e:
        logger.warning(f"Storage upload failed (continuing without file URL): {str(e)}")
        file_url = None

    # Save metadata to field_analyses table
    parsed_data_to_save = {
        "parameters": raw_parse.get("parameters", {}),
        "parse_confidence": raw_parse.get("parse_confidence", "low"),
        "raw_text_preview": raw_parse.get("raw_text", "")[:500],
        "file_format": "pdf" if is_pdf else "excel",
    }
    if raw_parse.get("error"):
        parsed_data_to_save["parse_error"] = raw_parse["error"]

    try:
        insert_data = {
            "id": analysis_id,
            "user_id": user_id,
            "type": final_type,
            "file_url": file_url,
            "file_name": filename,
            "parsed_data": parsed_data_to_save,
        }
        if field_id:
            insert_data["field_id"] = field_id

        db.table("field_analyses").insert(insert_data).execute()
    except Exception as e:
        logger.error(f"Error saving analysis to DB: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al guardar análisis: {str(e)}")

    return UploadResponse(
        analysis_id=uuid.UUID(analysis_id),
        type=final_type,
        parsed_data=parsed_data_to_save,
    )
