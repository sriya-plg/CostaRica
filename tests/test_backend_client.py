import unittest
from unittest.mock import MagicMock, patch

from app.backend.client import CoreDataClient


class TestCoreDataClient(unittest.TestCase):
    def setUp(self):
        self.client = CoreDataClient(base_url="https://plgtst.pegasuslogistics.com/api/orderentry")

    @patch("httpx.post")
    def test_add_email_log_success_dict(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"emailLogId": 8}
        mock_post.return_value = mock_response

        log_id = self.client.add_email_log(
            email="test@pegasus.com",
            email_subject="Shipment CR123",
            email_body="Attached files",
            email_received_on="2026-09-17T10:30:33.464Z",
            attachment_filenames=["FE-123.xml", "doc.pdf"],
        )

        self.assertEqual(log_id, 8)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["email"], "test@pegasus.com")
        self.assertEqual(len(call_kwargs["json"]["attachments"]), 2)
        self.assertEqual(call_kwargs["json"]["attachments"][0]["fileName"], "FE-123.xml")
        self.assertEqual(call_kwargs["json"]["attachments"][0]["attachmentId"], 0)

    @patch("httpx.post")
    def test_add_email_log_numeric_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = 42
        mock_post.return_value = mock_response

        log_id = self.client.add_email_log(
            email="test@pegasus.com",
            email_subject="Test",
            email_body="",
            email_received_on="2026-09-17T10:30:33.464Z",
            attachment_filenames=["file.xml"],
        )
        self.assertEqual(log_id, 42)

    @patch("httpx.get")
    def test_get_attachment_list_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "attachments": [
                {"attachmentId": 123, "fileName": "shipment-details.pdf"},
                {"attachmentId": 124, "fileName": "pickup-confirmation.pdf"},
            ]
        }
        mock_get.return_value = mock_response

        result = self.client.get_attachment_list(8)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["attachmentId"], 123)
        self.assertEqual(result[0]["fileName"], "shipment-details.pdf")

    @patch("httpx.post")
    def test_add_activity_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "activityId": 1001}
        mock_post.return_value = mock_response

        result = self.client.add_activity(email_log_id=8, attachment_id=123, bill_to=0)

        self.assertIsNotNone(result)
        self.assertTrue(result.get("success"))
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload, {"emailLogId": 8, "attachmentId": 123, "billTo": 0})

    @patch("httpx.post")
    def test_update_activity_ml_process_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "message": "ML status updated"}
        mock_post.return_value = mock_response

        result = self.client.update_activity_ml_process(
            activity_id=100234,
            email_log_id=550012,
            attachment_id=900871,
            bill_to=0,
            ml_status=3,
            ml_request={
                "invoiceKey": "INV-2026-004512",
                "shipmentNo": "SHP-778341",
                "referenceNo": "REF-90876",
            },
            ml_log="ML extraction completed successfully.",
            ml_error=None,
            ml_process_started_on="2026-09-28T09:14:02Z",
            ml_process_completed_on="2026-09-28T09:14:37Z",
            ml_completion_time_in_secs=35,
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.get("success"))
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["activityId"], 100234)
        self.assertEqual(payload["emailLogId"], 550012)
        self.assertEqual(payload["attachmentId"], 900871)
        self.assertEqual(payload["billTo"], 0)
        self.assertEqual(payload["mlStatus"], 3)
        self.assertEqual(payload["mlRequest"]["invoiceKey"], "INV-2026-004512")
        self.assertEqual(payload["mlCompletionTimeInSecs"], 35)


if __name__ == "__main__":
    unittest.main()
