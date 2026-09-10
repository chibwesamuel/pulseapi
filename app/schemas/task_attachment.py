from uuid import UUID
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.schemas.pagination import PaginationMeta


class TaskAttachmentResponse(BaseModel):
    """
    Schema returned for a task attachment.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    task_id: UUID
    uploaded_by: UUID

    file_name: str
    file_path: str
    file_type: str | None
    file_size: int | None

    created_at: datetime


class PaginatedTaskAttachmentsResponse(BaseModel):
    """
    Paginated task attachment response.
    """

    attachments: list[TaskAttachmentResponse]
    total: int
    meta: PaginationMeta
