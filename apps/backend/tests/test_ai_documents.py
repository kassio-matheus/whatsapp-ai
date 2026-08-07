"""Tests for the AI knowledge documents (company + session) pipeline."""

import io
import uuid

import pytest
from fastapi import UploadFile
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from starlette.datastructures import Headers

from app.modules.ai import documents
from app.modules.ai.file_reader import extract_document_text
from app.modules.ai.models import AIDocumentStatus
from app.modules.companies.models import Company


@pytest.fixture()
def session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(documents, "engine", engine)
    with Session(engine) as db:
        company = Company(name="Acme", owner_id=uuid.uuid4())
        db.add(company)
        db.commit()
        db.refresh(company)
        yield db, company


def _upload(name: str, content: str, mime: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content.encode("utf-8")),
        filename=name,
        headers=Headers({"content-type": mime}),
    )


def test_extract_document_text_reads_plain_text():
    text = extract_document_text(
        filename="produtos.txt", mime_type="text/plain", data=b"nosso cardapio"
    )
    assert "cardapio" in text


def test_extract_document_text_leaves_other_formats_pending():
    assert (
        extract_document_text(
            filename="catalogo.pdf", mime_type="application/pdf", data=b"%PDF"
        )
        == ""
    )


def test_company_profile_update_and_knowledge_block(session):
    db, company = session
    documents.update_company_profile(
        session=db, company_id=company.id, company_info="Somos uma pizzaria."
    )
    block = documents.company_knowledge_block(session=db, company_id=company.id)
    assert "pizzaria" in block


def test_company_profile_clear(session):
    db, company = session
    documents.update_company_profile(
        session=db, company_id=company.id, company_info="  "
    )
    assert (
        documents.company_knowledge_block(session=db, company_id=company.id) == ""
    )


def test_upload_company_document_extracts_text(session, tmp_path, monkeypatch):
    db, company = session
    monkeypatch.setattr(documents, "settings", type("S", (), {"UPLOAD_DIR": str(tmp_path), "MAX_UPLOAD_BYTES": 1_000_000})())

    row = documents.upload_company_document(
        company_id=company.id,
        uploader_id=uuid.uuid4(),
        file=_upload("cardapio.txt", "Pizzas a partir de R$ 39", "text/plain"),
    )
    assert row.extraction_status == AIDocumentStatus.EXTRACTED.value
    assert "R$ 39" in row.extracted_text

    block = documents.company_knowledge_block(session=db, company_id=company.id)
    assert "cardapio.txt" in block
    assert "R$ 39" in block


def test_pending_documents_are_skipped_in_knowledge(session, tmp_path, monkeypatch):
    db, company = session
    monkeypatch.setattr(documents, "settings", type("S", (), {"UPLOAD_DIR": str(tmp_path), "MAX_UPLOAD_BYTES": 1_000_000})())

    documents.upload_company_document(
        company_id=company.id,
        uploader_id=uuid.uuid4(),
        file=_upload("catalogo.pdf", "%PDF fake", "application/pdf"),
    )
    assert documents.company_knowledge_block(session=db, company_id=company.id) == ""


def test_unsupported_file_type_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "settings", type("S", (), {"UPLOAD_DIR": str(tmp_path), "MAX_UPLOAD_BYTES": 1_000_000})())

    with pytest.raises(Exception) as exc:
        documents.upload_company_document(
            company_id=uuid.uuid4(),
            uploader_id=uuid.uuid4(),
            file=_upload("malware.exe", "MZ", "application/octet-stream"),
        )
    assert exc.value.status_code == 415


def test_session_knowledge_block_uses_attached_files(session, tmp_path, monkeypatch):
    db, company = session
    monkeypatch.setattr(documents, "settings", type("S", (), {"UPLOAD_DIR": str(tmp_path), "MAX_UPLOAD_BYTES": 1_000_000})())

    session_id = uuid.uuid4()
    chat_file = documents.upload_session_file(
        session_id=session_id,
        user_id=company.owner_id,
        file=_upload("politicas.txt", "Reembolso em 30 dias", "text/plain"),
    )
    assert chat_file.extraction_status == AIDocumentStatus.EXTRACTED.value

    block = documents.session_knowledge_block(session=db, session_id=session_id)
    assert "politicas.txt" in block
    assert "Reembolso" in block


def test_company_documents_crud(session, tmp_path, monkeypatch):
    _, company = session
    monkeypatch.setattr(documents, "settings", type("S", (), {"UPLOAD_DIR": str(tmp_path), "MAX_UPLOAD_BYTES": 1_000_000})())

    row = documents.upload_company_document(
        company_id=company.id,
        uploader_id=uuid.uuid4(),
        file=_upload("regras.txt", "Horario 8h-18h", "text/plain"),
    )
    listed = documents.list_company_documents(company_id=company.id)
    assert [d.id for d in listed] == [row.id]

    body, _, name = documents.download_company_document(
        company_id=company.id, document_id=row.id
    )
    assert body == b"Horario 8h-18h"
    assert name == "regras.txt"

    documents.delete_company_document(company_id=company.id, document_id=row.id)
    assert documents.list_company_documents(company_id=company.id) == []
