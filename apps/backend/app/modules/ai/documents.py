"""Documents and company information that feed the AI assistant.

This module owns the persistent "knowledge" the assistant can rely on:

* the free-form company description (:class:`AICompanyProfile`);
* documents uploaded by the company (:class:`AICompanyDocument`);
* files attached to a chat session (:class:`ChatFile`).

Uploaded files are stored (Cloudflare R2 when configured, otherwise the local
upload directory) and their text is extracted through
:func:`app.modules.ai.file_reader.extract_document_text`, the place where the
document-reading AI plugs in. Extracted text and the company profile are later
rendered into system-prompt blocks (``company_knowledge_block`` /
``session_knowledge_block``) by the callers that generate replies.
"""

from __future__ import annotations

import datetime
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.r2 import R2Error, r2
from app.modules.ai.file_reader import extract_document_text
from app.modules.ai.models import (
    AICompanyDocument,
    AICompanyProfile,
    AIDocumentStatus,
    ChatFile,
)
from app.modules.ai.token_saver import compact_text

#: MIME types accepted as AI knowledge documents.
ALLOWED_UPLOADS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "text/plain": {".txt"},
}

#: Upper bound (characters) for every injected knowledge block. The combined
#: system prompt is still capped by the token saver before it reaches the LLM.
_KNOWLEDGE_BLOCK_CHARS = 8000
#: Per-document cap (characters) so one huge file can't crowd out the rest.
_DOCUMENT_BODY_CHARS = 4000


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _read_and_validate(
    file: UploadFile,
) -> tuple[str, str, str, bytes, int]:
    """Check the type, stream the upload respecting the size limit,
    and return ``(filename, mime_type, extension, data, size_bytes)``."""
    filename = os.path.basename(file.filename or "")
    mime_type = file.content_type or ""
    if not filename or mime_type not in ALLOWED_UPLOADS:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_UPLOADS[mime_type]:
        raise HTTPException(
            status_code=415, detail="File extension does not match type")

    size = 0
    chunk_buffer = bytearray()
    try:
        while chunk := file.file.read(64 * 1024):
            size += len(chunk)
            if size > settings.MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File is too large")
            chunk_buffer.extend(chunk)
    finally:
        file.file.close()
    return filename, mime_type, extension, bytes(chunk_buffer), size


def _persist_file(
    *,
    folder: str,
    resource_id: uuid.UUID,
    file_id: uuid.UUID,
    data: bytes,
    extension: str,
    mime_type: str,
) -> str:
    """Store the blob and return the reference persisted in the DB.

    ``folder`` is a stable path segment (``ai/company`` or ``ai/session``) so
    R2 keys and local directories stay separated by resource type.
    """
    if r2.configured:
        key = f"{folder}/{resource_id}/{file_id}{extension}"
        try:
            r2.put_object(key=key, data=data, content_type=mime_type)
        except R2Error as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not store the file: {exc}",
            ) from exc
        return key

    base_dir = Path(settings.UPLOAD_DIR).resolve()
    file_dir = base_dir / folder / str(resource_id)
    file_dir.mkdir(parents=True, exist_ok=True)
    filepath = file_dir / f"{file_id}{extension}"
    filepath.write_bytes(data)
    return str(filepath)


def _delete_stored_file(reference: str) -> None:
    """Best-effort removal of a stored blob; never raises."""
    if r2.configured:
        try:
            r2.delete_object(key=reference)
        except R2Error:
            pass
        return
    path = Path(reference)
    if path.is_file():
        path.unlink(missing_ok=True)


def _status_for(text: str) -> str:
    return AIDocumentStatus.EXTRACTED.value if text else AIDocumentStatus.PENDING.value


def _read_stored_file(reference: str, mime_type: str, filename: str) -> tuple[bytes, str, str]:
    if r2.configured:
        try:
            body, _ = r2.get_object(key=reference)
        except R2Error as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not read the file: {exc}",
            ) from exc
        return body, mime_type, filename
    path = Path(reference)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return path.read_bytes(), mime_type, filename


# ---------------------------------------------------------------------------
# Company profile
# ---------------------------------------------------------------------------


def get_company_profile(
    *, session: Session, company_id: uuid.UUID
) -> AICompanyProfile | None:
    return session.get(AICompanyProfile, company_id)


def update_company_profile(
    *, session: Session, company_id: uuid.UUID, company_info: str | None
) -> AICompanyProfile:
    profile = session.get(AICompanyProfile, company_id)
    if profile is None:
        profile = AICompanyProfile(company_id=company_id)
        session.add(profile)
    profile.company_info = compact_text(company_info) or None
    profile.updated_at = _now()
    session.commit()
    session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Company documents
# ---------------------------------------------------------------------------


def upload_company_document(
    *, company_id: uuid.UUID, uploader_id: uuid.UUID, file: UploadFile
) -> AICompanyDocument:
    filename, mime_type, extension, data, size = _read_and_validate(file)
    file_id = uuid.uuid4()
    reference = _persist_file(
        folder="ai/company",
        resource_id=company_id,
        file_id=file_id,
        data=data,
        extension=extension,
        mime_type=mime_type,
    )
    text = extract_document_text(filename=filename, mime_type=mime_type, data=data)
    with Session(engine) as session:
        document = AICompanyDocument(
            id=file_id,
            company_id=company_id,
            uploader_id=uploader_id,
            filename=filename,
            filepath=reference,
            mime_type=mime_type,
            size_bytes=size,
            extraction_status=_status_for(text),
            extracted_text=text or None,
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        return document


def list_company_documents(*, company_id: uuid.UUID) -> list[AICompanyDocument]:
    with Session(engine) as session:
        stmt = (
            select(AICompanyDocument)
            .where(AICompanyDocument.company_id == company_id)
            .order_by(AICompanyDocument.created_at)
        )
        return list(session.exec(stmt).all())


def get_company_document(
    *, company_id: uuid.UUID, document_id: uuid.UUID
) -> AICompanyDocument:
    with Session(engine) as session:
        document = session.get(AICompanyDocument, document_id)
    if document is None or document.company_id != company_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def delete_company_document(
    *, company_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    with Session(engine) as session:
        document = session.get(AICompanyDocument, document_id)
        if document is None or document.company_id != company_id:
            raise HTTPException(status_code=404, detail="Document not found")
        reference = document.filepath
        session.delete(document)
        session.commit()
    _delete_stored_file(reference)


def download_company_document(
    *, company_id: uuid.UUID, document_id: uuid.UUID
) -> tuple[bytes, str, str]:
    document = get_company_document(company_id=company_id, document_id=document_id)
    return _read_stored_file(document.filepath, document.mime_type, document.filename)


# ---------------------------------------------------------------------------
# Session files
# ---------------------------------------------------------------------------


def upload_session_file(
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    file: UploadFile,
) -> ChatFile:
    filename, mime_type, extension, data, size = _read_and_validate(file)
    file_id = uuid.uuid4()
    reference = _persist_file(
        folder="ai/session",
        resource_id=session_id,
        file_id=file_id,
        data=data,
        extension=extension,
        mime_type=mime_type,
    )
    text = extract_document_text(filename=filename, mime_type=mime_type, data=data)
    with Session(engine) as session:
        chat_file = ChatFile(
            id=file_id,
            session_id=session_id,
            user_id=user_id,
            filename=filename,
            filepath=reference,
            mime_type=mime_type,
            size_bytes=size,
            extraction_status=_status_for(text),
            extracted_text=text or None,
        )
        session.add(chat_file)
        session.commit()
        session.refresh(chat_file)
        return chat_file


def list_session_files(*, session_id: uuid.UUID) -> list[ChatFile]:
    with Session(engine) as session:
        stmt = (
            select(ChatFile)
            .where(ChatFile.session_id == session_id)
            .order_by(ChatFile.created_at)
        )
        return list(session.exec(stmt).all())


def delete_session_file(*, session_id: uuid.UUID, file_id: uuid.UUID) -> None:
    with Session(engine) as session:
        chat_file = session.get(ChatFile, file_id)
        if chat_file is None or chat_file.session_id != session_id:
            raise HTTPException(status_code=404, detail="File not found")
        reference = chat_file.filepath
        session.delete(chat_file)
        session.commit()
    _delete_stored_file(reference)


# ---------------------------------------------------------------------------
# System-prompt knowledge blocks
# ---------------------------------------------------------------------------


def company_knowledge_block(*, session: Session, company_id: uuid.UUID) -> str:
    """Render the company's knowledge (profile + documents) as a prompt block.

    Returns ``""`` when the company has no injected knowledge.
    """
    parts: list[str] = []

    profile = session.get(AICompanyProfile, company_id)
    if profile is not None and profile.company_info:
        parts.append("[Informações da empresa]\n" + compact_text(profile.company_info))

    documents = session.exec(
        select(AICompanyDocument).where(
            AICompanyDocument.company_id == company_id,
            AICompanyDocument.extraction_status == AIDocumentStatus.EXTRACTED.value,
        )
    ).all()
    for document in documents:
        body = compact_text(document.extracted_text)
        if not body:
            continue
        body = body[:_DOCUMENT_BODY_CHARS].rstrip()
        parts.append(f"[Documento: {document.filename}]\n{body}")

    return _cap_block("\n\n".join(parts))


def session_knowledge_block(*, session: Session, session_id: uuid.UUID) -> str:
    """Render the text extracted from the session's attached files."""
    files = session.exec(
        select(ChatFile).where(
            ChatFile.session_id == session_id,
            ChatFile.extraction_status == AIDocumentStatus.EXTRACTED.value,
        )
    ).all()
    parts = [
        f"[Anexo: {chat_file.filename}]\n"
        f"{(chat_file.extracted_text or '')[: _DOCUMENT_BODY_CHARS]}"
        for chat_file in files
        if chat_file.extracted_text
    ]
    return _cap_block("\n\n".join(parts))


def _cap_block(block: str) -> str:
    if len(block) <= _KNOWLEDGE_BLOCK_CHARS:
        return block
    return block[:_KNOWLEDGE_BLOCK_CHARS - 3].rstrip() + "..."