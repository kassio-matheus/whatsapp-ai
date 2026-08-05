import datetime
import os
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import asc, desc
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.r2 import R2Error, r2
from app.modules.ai.gateway import generate_for_user
from app.modules.ai.llm.common import friendly_provider_error
from app.modules.ai.models import ChatFile, ChatSession, Message
from app.modules.auth.models import User

SUMMARY_THRESHOLD = 30
MAX_ACTIVE_SESSIONS = 100
_ALLOWED_UPLOADS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "text/plain": {".txt"},
}


def _expires_at() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(
        tzinfo=None
    ) + datetime.timedelta(hours=settings.AI_SESSION_TTL_HOURS)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def cleanup_expired() -> int:
    with Session(engine) as session:
        cutoff = _now()
        expired = session.exec(
            select(ChatSession).where(
                ChatSession.expires_at < cutoff,
                ChatSession.is_active == True,
            )
        ).all()
        count = len(expired)
        for s in expired:
            s.is_active = False
            session.add(s)
        session.commit()
        return count


def create_session(
    *,
    user_id: uuid.UUID,
    title: str = "New Chat",
    system_prompt: str | None = None,
) -> ChatSession:
    with Session(engine) as session:
        cleanup_expired()
        active_count = len(
            session.exec(
                select(ChatSession).where(
                    ChatSession.user_id == user_id,
                    ChatSession.is_active == True,
                )
            ).all()
        )
        if active_count >= MAX_ACTIVE_SESSIONS:
            raise HTTPException(status_code=429, detail="Too many active sessions")
        db_session = ChatSession(
            user_id=user_id,
            title=title,
            system_prompt=system_prompt,
            expires_at=_expires_at(),
        )
        session.add(db_session)
        session.commit()
        session.refresh(db_session)
        return db_session


def get_session(*, session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession:
    with Session(engine) as session:
        db = session.get(ChatSession, session_id)
        if not db or db.user_id != user_id or not db.is_active:
            raise HTTPException(status_code=404, detail="Session not found")
        if db.expires_at < _now():
            db.is_active = False
            session.add(db)
            session.commit()
            raise HTTPException(status_code=410, detail="Session expired")
        return db


def get_context_summary(*, session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession:
    db = get_session(session_id=session_id, user_id=user_id)
    return db


def get_session_system_prompt(
    *, session_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    db = get_session(session_id=session_id, user_id=user_id)
    return db.system_prompt


def update_session_system_prompt(
    *, session_id: uuid.UUID, user_id: uuid.UUID, system_prompt: str | None
) -> ChatSession:
    get_session(session_id=session_id, user_id=user_id)
    with Session(engine) as session:
        db = session.get(ChatSession, session_id)
        if not db:
            raise HTTPException(status_code=404, detail="Session not found")
        db.system_prompt = system_prompt
        session.add(db)
        session.commit()
        session.refresh(db)
        return db


def delete_session_system_prompt(
    *, session_id: uuid.UUID, user_id: uuid.UUID
) -> ChatSession:
    return update_session_system_prompt(
        session_id=session_id,
        user_id=user_id,
        system_prompt=None,
    )


def delete_session(*, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with Session(engine) as session:
        db = session.get(ChatSession, session_id)
        if not db or db.user_id != user_id:
            raise HTTPException(status_code=404, detail="Session not found")
        file_rows = session.exec(
            select(ChatFile).where(ChatFile.session_id == db.id)
        ).all()
        db.is_active = False
        session.add(db)
        session.commit()

    if r2.configured:
        for row in file_rows:
            try:
                r2.delete_object(key=row.filepath)
            except R2Error:
                continue

    file_dir = os.path.join(settings.UPLOAD_DIR, str(session_id))
    if os.path.isdir(file_dir):
        shutil.rmtree(file_dir)


def list_sessions(
    *, user_id: uuid.UUID, limit: int = 20, offset: int = 0
) -> list[ChatSession]:
    with Session(engine) as session:
        cleanup_expired()
        stmt = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.user_id == user_id, ChatSession.is_active == True)
            .order_by(desc(ChatSession.created_at))
            .offset(offset)
            .limit(limit)
        )
        return list(session.exec(stmt).all())


def get_session_messages(*, session_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
    db = get_session(session_id=session_id, user_id=user_id)
    with Session(engine) as session:
        stmt = (
            select(Message)
            .where(Message.session_id == db.id)
            .order_by(asc(Message.created_at))
        )
        return list(session.exec(stmt).all())


def chat(
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    prompt: str,
    actor_user_id: str | None = None,
) -> str:
    get_session(session_id=session_id, user_id=user_id)

    with Session(engine) as session:
        chat_session = session.get(ChatSession, session_id)
        if (
            not chat_session
            or chat_session.user_id != user_id
            or not chat_session.is_active
        ):
            raise HTTPException(status_code=404, detail="Session not found")
        if chat_session.expires_at < _now():
            chat_session.is_active = False
            session.add(chat_session)
            session.commit()
            raise HTTPException(status_code=410, detail="Session expired")

        user_msg = Message(
            session_id=chat_session.id,
            role="user",
            content=prompt,
        )
        session.add(user_msg)
        session.flush()

        all_messages = session.exec(
            select(Message)
            .where(Message.session_id == chat_session.id)
            .order_by(asc(Message.created_at))
        ).all()

        context: list[dict[str, str]] = []

        if chat_session.context_summary:
            context.append(
                {
                    "role": "user",
                    "content": f"[Resumo da conversa anterior]: {chat_session.context_summary}",
                }
            )

        history = all_messages[:-1]
        recent = (
            history[-SUMMARY_THRESHOLD:]
            if len(history) >= SUMMARY_THRESHOLD
            else history
        )
        for m in recent:
            context.append({"role": m.role, "content": m.content})

        user = session.get(User, user_id)

        try:
            result = generate_for_user(
                session=session,
                user=user,
                prompt=prompt,
                context=context,
                system_prompt=chat_session.system_prompt,
                actor_user_id=actor_user_id or str(user_id),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=friendly_provider_error(exc),
            ) from exc
        response_text = (result.response or "").strip()
        if not response_text:
            raise HTTPException(
                status_code=502,
                detail="The AI assistant returned an empty reply",
            )
        assistant_msg = Message(
            session_id=chat_session.id,
            role="assistant",
            content=response_text,
        )
        session.add(assistant_msg)
        session.flush()

        chat_session.expires_at = _expires_at()
        session.add(chat_session)
        session.commit()

        return response_text


def upload_file(
    *, session_id: uuid.UUID, user_id: uuid.UUID, file: UploadFile
) -> ChatFile:
    db = get_session(session_id=session_id, user_id=user_id)

    filename = os.path.basename(file.filename or "")
    mime_type = file.content_type or ""
    extension = Path(filename).suffix.lower()
    if not filename or mime_type not in _ALLOWED_UPLOADS:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    if extension not in _ALLOWED_UPLOADS[mime_type]:
        raise HTTPException(status_code=415, detail="File extension does not match type")

    file_id = uuid.uuid4()

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

    if r2.configured:
        key = _file_key(
            user_id=user_id,
            session_id=db.id,
            file_id=file_id,
            extension=extension,
        )
        try:
            r2.put_object(
                key=key,
                data=bytes(chunk_buffer),
                content_type=mime_type,
            )
        except R2Error as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not store the file: {exc}",
            ) from exc
        stored_ref = key
    else:
        base_dir = Path(settings.UPLOAD_DIR).resolve()
        file_dir = base_dir / str(session_id)
        file_dir.mkdir(parents=True, exist_ok=True)
        saved_name = f"{file_id}{extension}"
        filepath = file_dir / saved_name
        filepath.write_bytes(bytes(chunk_buffer))
        stored_ref = str(filepath)

    with Session(engine) as session:
        chat_file = ChatFile(
            id=file_id,
            session_id=db.id,
            user_id=user_id,
            filename=filename,
            filepath=stored_ref,
            mime_type=mime_type,
            size_bytes=size,
        )
        session.add(chat_file)
        session.commit()
        session.refresh(chat_file)
        return chat_file


def _file_key(
    *, user_id: uuid.UUID, session_id: uuid.UUID, file_id: uuid.UUID, extension: str
) -> str:
    return f"ai/{user_id}/{session_id}/{file_id}{extension}"


def download_file(
    *, session_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID
) -> tuple[bytes, str, str]:
    db = get_session(session_id=session_id, user_id=user_id)
    with Session(engine) as session:
        chat_file = session.get(ChatFile, file_id)
        if not chat_file or chat_file.session_id != db.id or chat_file.user_id != user_id:
            raise HTTPException(status_code=404, detail="File not found")
        reference = chat_file.filepath

    if r2.configured:
        try:
            body, _ = r2.get_object(key=reference)
        except R2Error as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not read the file: {exc}",
            ) from exc
        return body, chat_file.mime_type, chat_file.filename

    path = Path(reference)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return path.read_bytes(), chat_file.mime_type, chat_file.filename


def get_session_files(*, session_id: uuid.UUID, user_id: uuid.UUID) -> list[ChatFile]:
    db = get_session(session_id=session_id, user_id=user_id)
    with Session(engine) as session:
        stmt = select(ChatFile).where(ChatFile.session_id == db.id)
        return list(session.exec(stmt).all())
