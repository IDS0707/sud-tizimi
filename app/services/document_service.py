"""Document orchestration — the heart of the processing pipeline.

Implements the data-flow from TZ section 6:

    Upload → Detect → Parse → OCR (if needed) → Index

Two entry points:
  * ``store_upload``   — persist an incoming file + create the Document row.
  * ``process_document`` — parse, OCR scanned pages, and index the text.
"""
from __future__ import annotations

from typing import BinaryIO

from sqlalchemy.orm import Session

from app.database.models import Document, DocStatus, OcrResult, Page
from app.ocr import structure
from app.ocr.engine import ocr_engine
from app.parsers.registry import parse_file
from app.services import file_detector, index_service, layout_service
from app.services.storage import storage
from app.utils.logger import get_logger

log = get_logger("udip.documents")


def store_upload(
    db: Session,
    *,
    file_obj: BinaryIO,
    filename: str,
    size_bytes: int,
    head: bytes | None = None,
    user_id: int | None = None,
) -> Document:
    """Detect, store and register an uploaded file (status=uploaded)."""
    info = file_detector.detect(filename, head)
    key = storage.save(file_obj, filename=filename, subdir=info.category)

    doc = Document(
        user_id=user_id,
        filename=filename,
        stored_path=key,
        file_type=info.extension,
        mime_type=info.mime_type,
        category=info.category,
        size_bytes=size_bytes,
        status=DocStatus.UPLOADED,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    log.info("Stored document #%d (%s, %s)", doc.id, filename, info.extension)
    return doc


def process_document(db: Session, document_id: int, *, run_ocr: bool = True,
                     lang: str | None = None) -> Document:
    """Parse a document, OCR any scanned pages, and index the result."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"Document {document_id} not found")

    doc.status = DocStatus.PROCESSING
    db.commit()

    abs_path = str(storage.path(doc.stored_path))
    try:
        result = parse_file(abs_path, doc.file_type)
    except Exception as exc:
        doc.status = DocStatus.FAILED
        doc.doc_metadata = {"error": str(exc)}
        db.commit()
        log.exception("Parsing failed for document %d", document_id)
        raise

    # Persist metadata + page count.
    doc.page_count = result.page_count
    doc.doc_metadata = {**(doc.doc_metadata or {}), **result.metadata, "parser": result.parser}

    # Remove any previous pages (re-processing) then recreate.
    for old in list(doc.pages):
        db.delete(old)
    db.flush()

    ocr_pages = 0
    for parsed in result.pages:
        page = Page(
            document_id=doc.id,
            page_number=parsed.page_number,
            text=parsed.text or "",
            width=parsed.width,
            height=parsed.height,
            layout={"blocks": parsed.blocks} if parsed.blocks else None,
            image_path=parsed.image_path,
        )
        db.add(page)
        db.flush()  # assign page.id

        # OCR scanned/empty pages that have a rendered image.
        if run_ocr and parsed.needs_ocr and parsed.image_path:
            out = ocr_engine.recognize(parsed.image_path, lang=lang)
            if out.text:
                page.text = out.text
            db.add(OcrResult(
                document_id=doc.id,
                page_id=page.id,
                text=out.text,
                boxes=out.boxes,
                confidence=out.confidence,
                engine=out.engine,
                lang=out.lang,
            ))
            # Layout analysis + table detection (V3):
            #   PP-Structure if installed, else heuristic from OCR boxes.
            layout = None
            if structure.is_available():
                layout = structure.analyze(parsed.image_path)
            if layout is None and out.boxes:
                layout = layout_service.analyze_page_from_ocr(out.boxes, parsed.page_number)
            if layout:
                page.layout = {"blocks": layout["blocks"]}
            ocr_pages += 1

        # Index the page text (parser text or OCR text).
        source = "ocr" if (parsed.needs_ocr and run_ocr) else "parser"
        index_service.index_page(db, page, source=source)

    # Decide final status.
    if ocr_pages and result.page_count:
        doc.status = DocStatus.OCR_DONE
    else:
        doc.status = DocStatus.PARSED
    db.commit()
    db.refresh(doc)
    log.info(
        "Processed document %d: %d pages, %d OCR-ed, status=%s",
        document_id, result.page_count, ocr_pages, doc.status,
    )
    return doc
