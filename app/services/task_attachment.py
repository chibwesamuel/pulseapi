from math import ceil
from pathlib import Path
from uuid import UUID, uuid4
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.repositories.task_attachment import (
    create_attachment,
    get_attachment,
    list_attachments,
    delete_attachment,
)
from app.storage.factory import get_storage
from fastapi.responses import StreamingResponse


def _validate_file_signature(
    file,
    file_type: str,
) -> None:
    """
    Validate that the uploaded file content matches
    the declared MIME type where a reliable signature
    or container structure is available.
    """

    header = file.read(16)

    if file_type == "application/pdf":
        if not header.startswith(b"%PDF-"):
            raise ValueError(
                "File content does not match attachment type"
            )

    elif file_type == "image/png":
        if header != (
            b"\x89PNG\r\n\x1a\n"
            + header[8:]
        ):
            raise ValueError(
                "File content does not match attachment type"
            )

    elif file_type == "image/jpeg":
        if not header.startswith(b"\xff\xd8\xff"):
            raise ValueError(
                "File content does not match attachment type"
            )

    elif file_type == "image/gif":
        if header[:6] not in (
            b"GIF87a",
            b"GIF89a",
        ):
            raise ValueError(
                "File content does not match attachment type"
            )

    elif file_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        file.seek(0)

        try:
            with ZipFile(file) as archive:
                names = set(archive.namelist())

                if "[Content_Types].xml" not in names:
                    raise ValueError(
                        "File content does not match attachment type"
                    )

                if file_type.endswith("wordprocessingml.document"):
                    required = "word/document.xml"
                else:
                    required = "xl/workbook.xml"

                if required not in names:
                    raise ValueError(
                        "File content does not match attachment type"
                    )

        except BadZipFile:
            raise ValueError(
                "File content does not match attachment type"
            )

    file.seek(0)

def create_new_attachment(
    db: Session,
    task: Task,
    user_id: UUID,
    organization_id: UUID,
    file_name: str,
    file,
    file_type: str | None = None,
):
    """
    Store a file and create its task attachment metadata.

    The task has already been validated by the
    get_current_task dependency.

    The user must also be a member of the
    project containing the task.
    """

    membership = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == task.project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )

    if not membership:
        raise ValueError(
            "User is not a project member"
        )

    original_name = Path(
        file_name or ""
    ).name

    if not original_name:
        raise ValueError(
            "A valid file name is required"
        )

    allowed_types = {
        content_type.strip()
        for content_type in settings.ALLOWED_ATTACHMENT_TYPES.split(",")
        if content_type.strip()
    }

    if file_type not in allowed_types:
        raise ValueError(
            "Unsupported attachment type"
        )

    extension = Path(
        original_name
    ).suffix.lower()

    extension_map = {}

    for item in settings.ALLOWED_ATTACHMENT_EXTENSIONS.split(","):
        mime_type, extensions = item.split(":", 1)

        extension_map[mime_type.strip()] = {
            value.strip().lower()
            for value in extensions.split("|")
            if value.strip()
        }

    allowed_extensions = extension_map.get(
        file_type,
        set(),
    )

    if extension not in allowed_extensions:
        raise ValueError(
            "File extension does not match attachment type"
        )

    _validate_file_signature(
        file,
        file_type,
    )

    storage_key = (
        f"organizations/"
        f"{organization_id}/"
        f"tasks/"
        f"{task.id}/"
        f"attachments/"
        f"{uuid4()}"
        f"{extension}"
    )

    storage = get_storage()

    try:
        file_size = storage.save(
            storage_key,
            file,
            max_size=settings.MAX_ATTACHMENT_SIZE,
        )

        attachment = create_attachment(
            db,
            task_id=task.id,
            user_id=user_id,
            file_name=original_name,
            file_path=storage_key,
            file_type=file_type,
            file_size=file_size,
        )

        db.commit()
        db.refresh(attachment)

        return attachment

    except Exception:
        db.rollback()

        try:
            if storage.exists(storage_key):
                storage.delete(storage_key)
        except Exception:
            pass

        raise


def get_task_attachments(
    db: Session,
    task_id: UUID,
    skip: int = 0,
    limit: int = 10,
):
    """
    List attachments for a task.
    """

    total, attachments = list_attachments(
        db,
        task_id,
        skip,
        limit,
    )

    page = (skip // limit) + 1

    total_pages = (
        ceil(total / limit)
        if total
        else 1
    )

    return {
        "total": total,
        "meta": {
            "page": page,
            "page_size": limit,
            "total_items": total,
            "total_pages": total_pages,
        },
        "attachments": attachments,
    }


def get_single_attachment(
    db: Session,
    attachment_id: UUID,
):
    """
    Retrieve one attachment.
    """

    return get_attachment(
        db,
        attachment_id,
    )

def remove_attachment(
    db: Session,
    attachment_id: UUID,
    user_id: UUID,
):
    """
    Delete an attachment and its stored file.

    Users may only delete attachments they uploaded.
    """

    attachment = get_attachment(
        db,
        attachment_id,
    )

    if not attachment:
        raise ValueError(
            "Attachment not found"
        )

    if attachment.uploaded_by != user_id:
        raise ValueError(
            "You can only delete your own attachments"
        )

    storage = get_storage()

    storage_key = attachment.file_path

    try:
        if storage.exists(storage_key):
            storage.delete(storage_key)

        delete_attachment(
            db,
            attachment,
        )

        db.commit()

        return attachment

    except Exception:
        db.rollback()
        raise

def get_attachment_file(
    db: Session,
    attachment_id: UUID,
    task_id: UUID,
):
    """
    Retrieve an attachment and open its stored file.

    The attachment must belong to the requested task.
    """

    attachment = get_attachment(
        db,
        attachment_id,
    )

    if not attachment:
        raise ValueError(
            "Attachment not found"
        )

    if attachment.task_id != task_id:
        raise ValueError(
            "Attachment not found"
        )

    storage = get_storage()

    try:
        file = storage.open(
            attachment.file_path
        )

    except FileNotFoundError:
        raise ValueError(
            "Stored attachment not found"
        )

    return attachment, file