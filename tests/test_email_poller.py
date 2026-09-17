import unittest
from unittest.mock import MagicMock, patch

from app.jobs.email_poller import EmailTracker, poll_new_emails, process_one_email, tracker


class TestEmailPollerUnread(unittest.TestCase):
    def setUp(self):
        tracker._in_flight.clear()

    def tearDown(self):
        tracker._in_flight.clear()

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

    @patch("app.jobs.email_poller.mark_message_as_read")
    @patch("app.jobs.email_poller.process_new_message")
    def test_failed_processing_leaves_unread(
        self, mock_process, mock_mark_read
    ):
        mock_process.side_effect = RuntimeError("Extraction failed")

        result = process_one_email({"id": "msg_fail", "subject": "Broken"})
        self.assertFalse(result)
        mock_mark_read.assert_not_called()
        self.assertFalse(tracker.is_in_flight("msg_fail"))


if __name__ == "__main__":
    unittest.main()
