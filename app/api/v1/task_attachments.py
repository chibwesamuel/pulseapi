from uuid import UUID

import re
import unicodedata
from urllib.parse import quote
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from sqlalchemy.orm import Session

from app.database.session import get_db

from app.dependencies.organization import (
    get_current_task,
)

from app.dependencies.permissions import (
    require_permission,
)

from app.models.task import Task
from app.models.user import User

from app.schemas.task_attachment import (
    TaskAttachmentResponse,
    PaginatedTaskAttachmentsResponse,
)

from app.services.task_attachment import (
    create_new_attachment,
    get_task_attachments,
    get_single_attachment,
    remove_attachment,
    get_attachment_file,
)
from fastapi.responses import StreamingResponse


def build_content_disposition(filename: str) -> str:
    """
    Build a safe Content-Disposition header for a downloaded file.

    The ASCII filename provides compatibility with older clients,
    while filename* preserves the original UTF-8 filename.
    """

    # Remove path separators.
    safe_filename = (
        filename
        .replace("\\", "_")
        .replace("/", "_")
    )

    # Reject everything from the first HTTP control character onward.
    control_character = next(
        (
            index
            for index, character in enumerate(safe_filename)
            if ord(character) < 32
            or ord(character) == 127
        ),
        None,
    )

    if control_character is not None:
        safe_filename = safe_filename[:control_character]

    if not safe_filename:
        safe_filename = "download"

    # Create an ASCII fallback for clients that do not support
    # RFC 5987 / RFC 6266 filename*.
    ascii_filename = unicodedata.normalize(
        "NFKD",
        safe_filename,
    ).encode(
        "ascii",
        "ignore",
    ).decode(
        "ascii",
    )

    ascii_filename = re.sub(
        r"[^A-Za-z0-9._ -]",
        "_",
        ascii_filename,
    ).strip()

    if not ascii_filename:
        ascii_filename = "download"

    encoded_filename = quote(
        safe_filename,
        safe="",
    )

    return (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{encoded_filename}"
    )

router = APIRouter(
    prefix=(
        "/organizations/"
        "{organization_id}/projects/"
        "{project_id}/tasks/"
        "{task_id}/attachments"
    ),
    tags=["Task Attachments"],
)


@router.post(
    "",
    response_model=TaskAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_attachment(
    organization_id: UUID,
    project_id: UUID,
    task_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    task: Task = Depends(get_current_task),
    current_user: User = Depends(
        require_permission(
            "projects.members.manage"
        )
    ),
):
    """
    Upload a file and attach it to the current task.
    """

    try:
        return create_new_attachment(
            db=db,
            task=task,
            user_id=current_user.id,
            organization_id=organization_id,
            file_name=file.filename or "",
            file=file.file,
            file_type=file.content_type,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@router.get(
    "",
    response_model=PaginatedTaskAttachmentsResponse,
)
def list_task_attachments(
    organization_id: UUID,
    project_id: UUID,
    task_id: UUID,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    task: Task = Depends(get_current_task),
    current_user: User = Depends(
        require_permission(
            "projects.view"
        )
    ),
):
    """
    List attachments belonging to the current task.
    """

    return get_task_attachments(
        db,
        task.id,
        skip,
        limit,
    )


@router.get(
    "/{attachment_id}",
    response_model=TaskAttachmentResponse,
)
def get_attachment(
    organization_id: UUID,
    project_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    task: Task = Depends(get_current_task),
    current_user: User = Depends(
        require_permission(
            "projects.view"
        )
    ),
):
    """
    Retrieve a task attachment.

    The current task dependency ensures that the
    requested task belongs to the requested project
    and organization.
    """

    attachment = get_single_attachment(
        db,
        attachment_id,
    )

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    if attachment.task_id != task.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    return attachment


@router.delete(
    "/{attachment_id}",
)
def delete_attachment(
    organization_id: UUID,
    project_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    task: Task = Depends(get_current_task),
    current_user: User = Depends(
        require_permission(
            "projects.members.manage"
        )
    ),
):
    """
    Delete a task attachment.

    The attachment must belong to the current task.
    """

    attachment = get_single_attachment(
        db,
        attachment_id,
    )

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    if attachment.task_id != task.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    try:
        remove_attachment(
            db,
            attachment_id,
            current_user.id,
        )

        return {
            "message": "Task attachment removed successfully"
        }

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

@router.get(
    "/{attachment_id}/download",
)
def download_task_attachment(
    organization_id: UUID,
    project_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    task: Task = Depends(get_current_task),
    current_user: User = Depends(
        require_permission(
            "projects.view"
        )
    ),
):
    """
    Download a file attached to the current task.
    """

    try:
        attachment, file = get_attachment_file(
            db=db,
            attachment_id=attachment_id,
            task_id=task.id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    return StreamingResponse(
        file,
        media_type=(
            attachment.file_type
            or "application/octet-stream"
        ),
        headers={
            "Content-Disposition": build_content_disposition(
                attachment.file_name
            )
        },
    )
