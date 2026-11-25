import unittest
from unittest.mock import MagicMock, patch

from app.jobs.email_poller import EmailTracker, poll_new_emails, process_one_email, tracker


class TestEmailPollerUnread(unittest.TestCase):
    def setUp(self):
        tracker._in_flight.clear()
        tracker._failures.clear()

    def tearDown(self):
        tracker._in_flight.clear()
        tracker._failures.clear()

    @patch("app.jobs.email_poller.mark_message_as_read")
    @patch("app.jobs.email_poller.process_new_message")
    @patch("app.jobs.email_poller.list_unread_emails")
    def test_poll_processes_unread_and_marks_as_read(
        self, mock_list, mock_process, mock_mark_read
    ):
        mock_list.return_value = [
            {"id": "msg_unread_1", "subject": "Shipment 1", "isRead": False},
            {"id": "msg_unread_2", "subject": "Shipment 2", "isRead": False},
        ]

        count = poll_new_emails()
        self.assertEqual(count, 2)
        self.assertEqual(mock_process.call_count, 2)
        self.assertEqual(mock_mark_read.call_count, 2)
        mock_mark_read.assert_any_call("msg_unread_1")
        mock_mark_read.assert_any_call("msg_unread_2")

    @patch("app.jobs.email_poller.mark_message_as_read")
    @patch("app.jobs.email_poller.process_new_message")
    def test_in_flight_message_is_skipped(
        self, mock_process, mock_mark_read
    ):
        tracker.start("msg_in_flight")

        result = process_one_email({"id": "msg_in_flight", "subject": "In flight"})
        self.assertFalse(result)
        mock_process.assert_not_called()
        mock_mark_read.assert_not_called()

    @patch("app.jobs.email_poller.send_alert_email")
    @patch("app.jobs.email_poller.mark_message_as_read")
    @patch("app.jobs.email_poller.process_new_message")
    def test_failed_processing_leaves_unread(
        self, mock_process, mock_mark_read, mock_send_alert
    ):
        mock_process.side_effect = RuntimeError("Extraction failed")

        result = process_one_email({"id": "msg_fail", "subject": "Broken"})
        self.assertFalse(result)
        mock_mark_read.assert_not_called()
        mock_send_alert.assert_called_once()
        self.assertFalse(tracker.is_in_flight("msg_fail"))

    @patch("app.jobs.email_poller.send_alert_email")
    @patch("app.jobs.email_poller.mark_message_as_read")
    @patch("app.jobs.email_poller.process_new_message")
    def test_retries_twice_then_marks_read_and_alerts_only_on_first_failure(
        self, mock_process, mock_mark_read, mock_send_alert
    ):
        mock_process.side_effect = ValueError("No PDF attachment")
        msg = {
            "id": "msg_retry_limit",
            "subject": "Missing PDF",
            "receivedDateTime": "2026-11-25T10:00:00Z",
            "from": {"emailAddress": {"address": "sender@example.com"}},
        }

        # Attempt 1 (initial failure): sends alert, stays unread
        self.assertFalse(process_one_email(msg))
        mock_send_alert.assert_called_once_with(
            message_id="msg_retry_limit",
            subject="Missing PDF",
            reason="No PDF attachment",
            sender="sender@example.com",
            received_at="2026-11-25T10:00:00Z",
        )
        mock_mark_read.assert_not_called()

        # Attempt 2 (retry 1): no alert, stays unread
        self.assertFalse(process_one_email(msg))
        self.assertEqual(mock_send_alert.call_count, 1)
        mock_mark_read.assert_not_called()

        # Attempt 3 (retry 2): no alert, marked as read after 2nd retry fails
        self.assertFalse(process_one_email(msg))
        self.assertEqual(mock_send_alert.call_count, 1)
        mock_mark_read.assert_called_once_with("msg_retry_limit")

    @patch("app.jobs.email_poller.send_alert_email")
    @patch("app.jobs.email_poller.mark_message_as_read")
    @patch("app.jobs.email_poller.process_new_message")
    def test_alert_sent_on_first_failure_then_retry_succeeds(
        self, mock_process, mock_mark_read, mock_send_alert
    ):
        mock_process.side_effect = [RuntimeError("Azure timeout"), {"ok": True}]
        msg = {"id": "msg_recover", "subject": "Recoverable"}

        # Attempt 1 fails -> alert sent, left unread
        self.assertFalse(process_one_email(msg))
        mock_send_alert.assert_called_once()
        mock_mark_read.assert_not_called()

        # Attempt 2 succeeds -> marked as read, failure state cleared
        self.assertTrue(process_one_email(msg))
        self.assertEqual(mock_send_alert.call_count, 1)
        mock_mark_read.assert_called_once_with("msg_recover")
        self.assertNotIn("msg_recover", tracker._failures)


if __name__ == "__main__":
    unittest.main()
