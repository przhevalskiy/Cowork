"""In-memory attachment service — text extraction and per-discussion context storage."""
import io
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Attachment:
    id: str
    filename: str
    content_type: str
    text: str
    size_bytes: int


# In-memory store: discussion_id → list of Attachments
_store: Dict[str, List[Attachment]] = {}


def _extract_text(filename: str, content_type: str, data: bytes) -> str:
    name_lower = filename.lower()

    if name_lower.endswith(('.txt', '.md', '.csv', '.json')):
        return data.decode('utf-8', errors='replace')

    if name_lower.endswith('.pdf') or 'pdf' in content_type:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or '' for page in reader.pages]
            return '\n'.join(pages).strip()
        except Exception as e:
            logger.warning(f"PDF extraction failed for {filename}: {e}")
            return ''

    if name_lower.endswith('.docx') or 'wordprocessingml' in content_type:
        try:
            import docx
            doc = docx.Document(io.BytesIO(data))
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            logger.warning(f"DOCX extraction failed for {filename}: {e}")
            return ''

    # Try plain text for anything else
    try:
        return data.decode('utf-8', errors='replace')
    except Exception:
        return ''


def add_attachment(discussion_id: str, filename: str, content_type: str, data: bytes) -> Attachment:
    text = _extract_text(filename, content_type, data)
    att = Attachment(
        id=str(uuid.uuid4()),
        filename=filename,
        content_type=content_type,
        text=text,
        size_bytes=len(data),
    )
    _store.setdefault(discussion_id, []).append(att)
    return att


def get_attachments(discussion_id: str) -> List[Attachment]:
    return _store.get(discussion_id, [])


def get_attachment(discussion_id: str, attachment_id: str) -> Optional[Attachment]:
    for a in _store.get(discussion_id, []):
        if a.id == attachment_id:
            return a
    return None


def delete_attachment(discussion_id: str, attachment_id: str) -> bool:
    attachments = _store.get(discussion_id, [])
    before = len(attachments)
    _store[discussion_id] = [a for a in attachments if a.id != attachment_id]
    return len(_store[discussion_id]) < before


def build_attachment_context(discussion_id: str) -> str:
    attachments = get_attachments(discussion_id)
    if not attachments:
        return ''
    parts = ['\n\nAttached reference documents (use these to inform your intake questions):']
    for att in attachments:
        if att.text.strip():
            # Truncate very large docs to ~8000 chars
            text = att.text[:8000] + ('...[truncated]' if len(att.text) > 8000 else '')
            parts.append(f'\n--- {att.filename} ---\n{text}')
    return '\n'.join(parts)
