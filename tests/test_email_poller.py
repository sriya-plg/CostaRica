import unittest
from unittest.mock import MagicMock, patch

from app.jobs.email_poller import EmailTracker, poll_new_emails, process_one_email, tracker
from app.persistence.processed_emails import (
    _get_db,
    get_processed_email,
    init_db,
    insert_processed_email,
)


class TestEmailPollerUnread(unittest.TestCase):
    def setUp(self):
        init_db()
        with _get_db() as conn:
            conn.execute("DELETE FROM processed_emails WHERE message_id LIKE 'msg_%'")
            conn.commit()

    def tearDown(self):
        with _get_db() as conn:
            conn.execute("DELETE FROM processed_emails WHERE message_id LIKE 'msg_%'")
            conn.commit()

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

        row1 = get_processed_email("msg_unread_1")
        row2 = get_processed_email("msg_unread_2")
        self.assertIsNotNone(row1)
        self.assertIsNotNone(row2)

    @patch("app.jobs.email_poller.mark_message_as_read")
    @patch("app.jobs.email_poller.process_new_message")
    def test_already_processed_in_db_marks_as_read_and_skips(
        self, mock_process, mock_mark_read
    ):
        insert_processed_email("msg_already_done", status="processed")

        result = process_one_email({"id": "msg_already_done", "subject": "Done"})
        self.assertFalse(result)
        mock_process.assert_not_called()
        mock_mark_read.assert_called_once_with("msg_already_done")

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
