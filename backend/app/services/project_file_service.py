"""Persistent project "Files & sources" — Supabase table + Storage bucket.

Unlike the in-memory per-discussion attachment_service, these files persist and
are shared across every task (discussion) filed under a project. Binary content
lives in the `project-files` Storage bucket; extracted text is cached in the
`project_files` table for fast injection into chat context.
"""
import logging
import uuid
from typing import List, Optional

from app.database.supabase_client import get_supabase_client
from app.models import ProjectFile
from app.services.attachment_service import _extract_text

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "project-files"
_MAX_FILE_CHARS = 8000


def _row_to_file(row: dict) -> ProjectFile:
    return ProjectFile(
        id=row["id"],
        project_id=row["project_id"],
        filename=row.get("filename", "file"),
        content_type=row.get("content_type"),
        size_bytes=row.get("size_bytes"),
        storage_path=row.get("storage_path", ""),
        created_at=row.get("created_at"),
    )


def add_project_file(
    project_id: str, user_id: str, filename: str, content_type: str, data: bytes
) -> ProjectFile:
    client = get_supabase_client()
    file_id = str(uuid.uuid4())
    storage_path = f"{user_id}/{project_id}/{file_id}-{filename}"

    client.storage.from_(STORAGE_BUCKET).upload(
        storage_path,
        data,
        {"content-type": content_type or "application/octet-stream", "upsert": "true"},
    )

    text = _extract_text(filename, content_type or "", data)
    row = {
        "id": file_id,
        "project_id": project_id,
        "user_id": user_id,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(data),
        "storage_path": storage_path,
        "extracted_text": text,
    }
    resp = client.table("project_files").insert(row).execute()
    return _row_to_file(resp.data[0])


def list_project_files(project_id: str, user_id: str) -> List[ProjectFile]:
    resp = (
        get_supabase_client()
        .table("project_files")
        .select("id, project_id, filename, content_type, size_bytes, storage_path, created_at")
        .eq("project_id", project_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_row_to_file(r) for r in (resp.data or [])]


def delete_project_file(project_id: str, file_id: str, user_id: str) -> bool:
    client = get_supabase_client()
    resp = (
        client.table("project_files")
        .select("storage_path")
        .eq("id", file_id)
        .eq("project_id", project_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not resp or not resp.data:
        return False

    storage_path = resp.data.get("storage_path")
    if storage_path:
        try:
            client.storage.from_(STORAGE_BUCKET).remove([storage_path])
        except Exception as e:
            logger.warning(f"Failed to remove storage object {storage_path}: {e}")

    client.table("project_files").delete().eq("id", file_id).eq(
        "user_id", user_id
    ).execute()
    return True


def build_project_file_context(project_id: str) -> str:
    """Concatenate the project's file text for injection into the chat system prompt."""
    resp = (
        get_supabase_client()
        .table("project_files")
        .select("filename, extracted_text")
        .eq("project_id", project_id)
        .execute()
    )
    rows = resp.data or []
    parts: List[str] = []
    for r in rows:
        text = (r.get("extracted_text") or "").strip()
        if not text:
            continue
        truncated = text[:_MAX_FILE_CHARS] + ("...[truncated]" if len(text) > _MAX_FILE_CHARS else "")
        parts.append(f"\n--- {r.get('filename', 'file')} ---\n{truncated}")
    if not parts:
        return ""
    return "\n\nProject reference files (shared across this project's tasks):" + "".join(parts)
