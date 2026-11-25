from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.storage.azure_blob import AzureBlobStorage


class TestAzureBlobStorage(unittest.TestCase):
    def setUp(self):
        self.storage = AzureBlobStorage(
            connection_string="DefaultEndpointsProtocol=https;AccountName=testacc;AccountKey=testkey;EndpointSuffix=core.windows.net",
            container_name="cwdocs",
        )

    def test_container_name_parsing(self):
        storage_with_slash = AzureBlobStorage(
            connection_string="dummy",
            container_name="plgaiml1/cwdocs",
        )
        self.assertEqual(storage_with_slash.container_name, "cwdocs")

    @patch("azure.storage.blob.BlobServiceClient.from_connection_string")
    def test_upload_pdf_success(self, mock_from_conn):
        mock_client = MagicMock()
        mock_blob_client = MagicMock()
        mock_blob_client.url = "https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/test.pdf"
        mock_client.get_blob_client.return_value = mock_blob_client
        mock_from_conn.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = Path(tmpdir) / "test.pdf"
            pdf_file.write_bytes(b"%PDF-1.4 sample content")

            blob_url = self.storage.upload_pdf(pdf_file)

            self.assertEqual(
                blob_url,
                "https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/test.pdf",
            )
            mock_client.get_blob_client.assert_any_call(
                container="plgaiml1",
                blob="cwdocs/test.pdf",
            )
            self.assertTrue(mock_blob_client.upload_blob.called)

    def test_upload_pdf_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.upload_pdf(Path("non_existent_folder/fake.pdf"), "2026-09-28")

    def test_missing_connection_string_raises(self):
        storage_no_conn = AzureBlobStorage(connection_string="", container_name="cwdocs")
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = Path(tmpdir) / "test.pdf"
            pdf_file.write_bytes(b"%PDF dummy")
            with self.assertRaises(ValueError):
                storage_no_conn.upload_pdf(pdf_file, "2026-09-28")


if __name__ == "__main__":
    unittest.main()
