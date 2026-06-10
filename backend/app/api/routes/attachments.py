"""Attachment upload/delete routes for per-discussion file context."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional

from app.services.attachment_service import add_attachment, get_attachments, delete_attachment, get_attachment
from app.services.discussion_service import get_discussion_service
from app.auth import get_current_user, UserContext

router = APIRouter(prefix="/api/discussions", tags=["attachments"])
logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}


class AttachmentSummaryOut(BaseModel):
    id: str
    discussion_id: str
    filename: str
    file_content_type: str
    file_size: int
    chunk_count: int
    created_at: str
    is_image: Optional[bool] = False


class AttachmentChunkOut(BaseModel):
    id: str
    content: str
    chunk_index: int
    content_type: str


class AttachmentDetailOut(AttachmentSummaryOut):
    full_text: str
    chunks: List[AttachmentChunkOut]


@router.post("/{discussion_id}/attachments", response_model=AttachmentSummaryOut)
async def upload_attachment(
    discussion_id: str,
    file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
):
    disc_service = get_discussion_service()
    if not disc_service.get_discussion(discussion_id, current_user.user_id):
        raise HTTPException(status_code=404, detail="Discussion not found")

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    content_type = file.content_type or "application/octet-stream"
    att = add_attachment(
        discussion_id=discussion_id,
        filename=file.filename or "upload",
        content_type=content_type,
        data=data,
    )
    return AttachmentSummaryOut(
        id=att.id,
        discussion_id=discussion_id,
        filename=att.filename,
        file_content_type=att.content_type,
        file_size=att.size_bytes,
        chunk_count=len(att.text.split('\n\n')) if att.text else 0,
        created_at=datetime.utcnow().isoformat(),
        is_image=content_type in IMAGE_TYPES,
    )


@router.get("/{discussion_id}/attachments", response_model=List[AttachmentSummaryOut])
async def list_attachments(
    discussion_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    disc_service = get_discussion_service()
    if not disc_service.get_discussion(discussion_id, current_user.user_id):
        raise HTTPException(status_code=404, detail="Discussion not found")

    return [
        AttachmentSummaryOut(
            id=a.id,
            discussion_id=discussion_id,
            filename=a.filename,
            file_content_type=a.content_type,
            file_size=a.size_bytes,
            chunk_count=len(a.text.split('\n\n')) if a.text else 0,
            created_at=datetime.utcnow().isoformat(),
            is_image=a.content_type in IMAGE_TYPES,
        )
        for a in get_attachments(discussion_id)
    ]


@router.get("/{discussion_id}/attachments/{attachment_id}", response_model=AttachmentDetailOut)
async def get_attachment_detail(
    discussion_id: str,
    attachment_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    disc_service = get_discussion_service()
    if not disc_service.get_discussion(discussion_id, current_user.user_id):
        raise HTTPException(status_code=404, detail="Discussion not found")

    att = get_attachment(discussion_id, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    paragraphs = [p for p in att.text.split('\n\n') if p.strip()]
    chunks = [
        AttachmentChunkOut(id=f"{att.id}-{i}", content=p, chunk_index=i, content_type="text")
        for i, p in enumerate(paragraphs)
    ]

    return AttachmentDetailOut(
        id=att.id,
        discussion_id=discussion_id,
        filename=att.filename,
        file_content_type=att.content_type,
        file_size=att.size_bytes,
        chunk_count=len(chunks),
        created_at=datetime.utcnow().isoformat(),
        is_image=att.content_type in IMAGE_TYPES,
        full_text=att.text,
        chunks=chunks,
    )


@router.delete("/{discussion_id}/attachments/{attachment_id}", status_code=204)
async def remove_attachment(
    discussion_id: str,
    attachment_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    disc_service = get_discussion_service()
    if not disc_service.get_discussion(discussion_id, current_user.user_id):
        raise HTTPException(status_code=404, detail="Discussion not found")

    if not delete_attachment(discussion_id, attachment_id):
        raise HTTPException(status_code=404, detail="Attachment not found")
