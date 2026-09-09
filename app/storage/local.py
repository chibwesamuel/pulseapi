from pathlib import Path
from typing import BinaryIO

from app.core.config import settings


class LocalStorage:
    """
    Local filesystem storage backend.
    """

    def __init__(
        self,
        root: str | Path | None = None,
    ):
        self.root = Path(
            root or settings.STORAGE_LOCAL_PATH
        ).resolve()

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _resolve_key(
        self,
        key: str,
    ) -> Path:
        path = (
            self.root / key
        ).resolve()

        if not path.is_relative_to(
            self.root
        ):
            raise ValueError(
                "Storage key resolves outside "
                "the storage root"
            )

        return path

    def save(
        self,
        key: str,
        file: BinaryIO,
        max_size: int | None = None,
    ) -> int:
        path = self._resolve_key(key)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        bytes_written = 0

        try:
            with path.open("wb") as destination:
                while chunk := file.read(
                    1024 * 1024
                ):
                    bytes_written += len(chunk)

                    if (
                        max_size is not None
                        and bytes_written > max_size
                    ):
                        raise ValueError(
                            "File exceeds maximum allowed size"
                        )

                    destination.write(chunk)

        except Exception:
            if path.exists():
                path.unlink()

            raise

        return bytes_written

    def open(
        self,
        key: str,
    ) -> BinaryIO:
        path = self._resolve_key(key)

        if not path.is_file():
            raise FileNotFoundError(
                f"Stored file not found: {key}"
            )

        return path.open("rb")

    def exists(
        self,
        key: str,
    ) -> bool:
        return self._resolve_key(
            key
        ).is_file()

    def delete(
        self,
        key: str,
    ) -> None:
        path = self._resolve_key(key)

        if path.exists():
            path.unlink()
