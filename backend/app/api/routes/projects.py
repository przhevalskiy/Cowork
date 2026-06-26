from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List

from app.models import Project, ProjectCreate, ProjectUpdate, ProjectFile, Discussion
from app.auth import get_current_user_id, get_current_user, UserContext
from app.services.project_service import get_project_service
from app.services.discussion_service import get_discussion_service
from app.services import project_file_service

router = APIRouter(prefix="/api/projects", tags=["projects"])

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.get("", response_model=List[Project])
async def list_projects(user_id: str = Depends(get_current_user_id)):
    """List all projects for the authenticated user."""
    return get_project_service().list_projects(user_id)


@router.post("", response_model=Project)
async def create_project(
    data: ProjectCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new project."""
    try:
        return get_project_service().create_project(user_id, **data.model_dump())
    except Exception as e:
        # The single-level-nesting DB trigger surfaces here as a constraint error.
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a project by ID."""
    project = get_project_service().get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Update a project. Only fields explicitly sent are changed."""
    updates = data.model_dump(exclude_unset=True)
    try:
        project = get_project_service().update_project(project_id, user_id, **updates)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a project. Filed conversations are unfiled (project_id set NULL)."""
    deleted = get_project_service().delete_project(project_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted", "id": project_id}


@router.get("/{project_id}/discussions", response_model=List[Discussion])
async def list_project_discussions(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """List the conversations filed under a project."""
    if not get_project_service().get_project(project_id, user_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return get_discussion_service().list_discussions(user_id, project_id=project_id)


# ── Files & sources ──────────────────────────────────────────────

@router.get("/{project_id}/files", response_model=List[ProjectFile])
async def list_project_files(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """List a project's shared files."""
    if not get_project_service().get_project(project_id, user_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return project_file_service.list_project_files(project_id, user_id)


@router.post("/{project_id}/files", response_model=ProjectFile)
async def upload_project_file(
    project_id: str,
    file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
):
    """Upload a file shared across all tasks in the project."""
    if not get_project_service().get_project(project_id, current_user.user_id):
        raise HTTPException(status_code=404, detail="Project not found")

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    try:
        return project_file_service.add_project_file(
            project_id=project_id,
            user_id=current_user.user_id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.delete("/{project_id}/files/{file_id}", status_code=204)
async def delete_project_file(
    project_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a project file."""
    if not project_file_service.delete_project_file(project_id, file_id, user_id):
        raise HTTPException(status_code=404, detail="File not found")
