from uuid import UUID

from sqlalchemy.orm import Session

from app.models.task_attachment import TaskAttachment


def create_attachment(
    db: Session,
    task_id: UUID,
    user_id: UUID,
    file_name: str,
    file_path: str,
    file_type: str | None = None,
    file_size: int | None = None,
) -> TaskAttachment:
    """
    Create a task attachment.

    The transaction is controlled by the service layer.
    """

    attachment = TaskAttachment(
        task_id=task_id,
        uploaded_by=user_id,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
    )

    db.add(attachment)
    db.flush()

    return attachment


def get_attachment(
    db: Session,
    attachment_id: UUID,
) -> TaskAttachment | None:
    """
    Retrieve a single attachment.
    """

    return (
        db.query(TaskAttachment)
        .filter(
            TaskAttachment.id == attachment_id,
        )
        .first()
    )


def list_attachments(
    db: Session,
    task_id: UUID,
    skip: int = 0,
    limit: int = 10,
) -> tuple[int, list[TaskAttachment]]:
    """
    List attachments belonging to a task.
    """

    query = (
        db.query(TaskAttachment)
        .filter(
            TaskAttachment.task_id == task_id,
        )
    )

    total = query.count()

    attachments = (
        query
        .order_by(
            TaskAttachment.created_at.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return total, attachments


def delete_attachment(
    db: Session,
    attachment: TaskAttachment,
) -> TaskAttachment:
    """
    Delete an attachment.

    The transaction is controlled by the service layer.
    """

    db.delete(attachment)
    db.flush()

    return attachment
