from app.core.config import settings
from app.storage.local import LocalStorage
from app.storage.base import Storage


def get_storage() -> Storage:
    """
    Return the configured storage backend.
    """

    if settings.STORAGE_BACKEND == "local":
        return LocalStorage()

    raise ValueError(
        f"Unsupported storage backend: "
        f"{settings.STORAGE_BACKEND}"
    )