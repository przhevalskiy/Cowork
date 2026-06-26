from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.models import Template, TemplateCreate, TemplateUpdate
from app.auth import get_current_user_id
from app.services.template_service import get_template_service

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=List[Template])
async def list_templates(user_id: str = Depends(get_current_user_id)):
    """List all templates for the authenticated user."""
    return get_template_service().list_templates(user_id)


@router.post("", response_model=Template)
async def create_template(
    data: TemplateCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new template."""
    return get_template_service().create_template(user_id, **data.model_dump())


@router.get("/{template_id}", response_model=Template)
async def get_template(
    template_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a template by ID."""
    template = get_template_service().get_template(template_id, user_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/{template_id}", response_model=Template)
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Update a template. Only fields explicitly sent are changed."""
    updates = data.model_dump(exclude_unset=True)
    template = get_template_service().update_template(template_id, user_id, **updates)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a template."""
    if not get_template_service().delete_template(template_id, user_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "id": template_id}
