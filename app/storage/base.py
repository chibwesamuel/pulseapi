from typing import BinaryIO, Protocol


class Storage(Protocol):
    """
    Interface for application file storage.

    Storage implementations operate on storage keys rather
    than absolute filesystem paths.
    """

    def save(
        self,
        key: str,
        file: BinaryIO,
        max_size: int | None = None,
    ) -> int:
        """
        Store a file under the given storage key.

        Returns the number of bytes written.
        """
        ...

    def open(
        self,
        key: str,
    ) -> BinaryIO:
        """
        Open a stored file for reading.
        """
        ...

    def exists(
        self,
        key: str,
    ) -> bool:
        """
        Check whether a stored file exists.
        """
        ...

    def delete(
        self,
        key: str,
    ) -> None:
        """
        Delete a stored file.
        """
        ...
