import logging
from pathlib import Path
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureBlobStorage:
    """Client for uploading documents to Azure Blob Storage."""

    def __init__(
        self,
        connection_string: str | None = None,
        container_name: str | None = None,
    ) -> None:
        self.connection_string = connection_string
        raw_container = container_name or settings.azure_container_name
        self.container_name = raw_container.split("/")[-1].strip() if raw_container else "cwdocs"
        self._client: BlobServiceClient | None = None

    def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            conn_str = (
                self.connection_string
                if self.connection_string is not None
                else settings.AZURE_CONNECTION_STRING
            )
            if not conn_str:
                raise ValueError(
                    "Azure Storage Connection String is not configured in settings (AZURE_CONNECTION_STRING)"
                )
            self._client = BlobServiceClient.from_connection_string(conn_str)
        return self._client

    def upload_pdf(self, file_path: Path | str, folder_name: str | None = None) -> str:
        """Upload a downloaded PDF file to Azure Blob storage in the configured container.

        Args:
            file_path: Local Path to the PDF file on disk.
            folder_name: Optional folder name (unused; stored without date/folder prefix).

        Returns:
            The full Azure Blob URL formatted as 'https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/<filename>'.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file to upload does not exist: {path}")

        blob_name = path.name

        logger.info(
            "Uploading PDF to Azure Blob: local=%s target=plgaiml1/cwdocs/%s",
            path,
            blob_name,
        )

        try:
            client = self._get_client()

            # Primary upload to container 'plgaiml1' under blob 'cwdocs/<filename>'
            blob_client_plg = client.get_blob_client(
                container="plgaiml1",
                blob=f"cwdocs/{blob_name}",
            )
            content_settings = ContentSettings(content_type="application/pdf")
            with open(path, "rb") as data:
                blob_client_plg.upload_blob(data, overwrite=True, content_settings=content_settings)

            # Also mirror upload to container 'cwdocs' with blob '<filename>'
            try:
                blob_client_cw = client.get_blob_client(container="cwdocs", blob=blob_name)
                with open(path, "rb") as data:
                    blob_client_cw.upload_blob(data, overwrite=True, content_settings=content_settings)
            except Exception as e:
                logger.debug("Mirror upload to cwdocs container skipped: %s", e)

            blob_url = blob_client_plg.url
            logger.info(
                "Successfully uploaded PDF to Azure Blob: url=%s",
                blob_url,
            )
            return blob_url
        except Exception as exc:
            logger.error(
                "Failed to upload PDF %s to Azure Blob: %s",
                path,
                exc,
            )
            raise


azure_blob_storage = AzureBlobStorage()


def upload_pdf_to_azure(file_path: Path | str, folder_name: str | None = None) -> str:
    """Helper function to upload PDF to Azure Blob storage."""
    return azure_blob_storage.upload_pdf(file_path, folder_name)