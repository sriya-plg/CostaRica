import unittest
from unittest.mock import MagicMock, patch

from app.graph.messages import get_message_details, list_unread_emails, mark_message_as_read


class TestGraphMessages(unittest.TestCase):
    @patch("app.graph.messages.graph_client.request")
    def test_list_unread_emails_pagination(self, mock_request):
        mock_request.side_effect = [
            {
                "value": [{"id": "msg_1", "isRead": False}],
                "@odata.nextLink": "/users/test/messages?$skip=50",
            },
            {
                "value": [{"id": "msg_2", "isRead": False}],
            },
        ]

        messages = list_unread_emails(lookback_hours=24)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["id"], "msg_1")
        self.assertEqual(messages[1]["id"], "msg_2")
        self.assertEqual(mock_request.call_count, 2)

    @patch("app.graph.messages.graph_client.request")
    def test_mark_message_as_read(self, mock_request):
        mark_message_as_read("msg_123")
        mock_request.assert_called_once()
        method, path = mock_request.call_args[0]
        self.assertEqual(method, "PATCH")
        self.assertIn("/messages/msg_123", path)
        self.assertEqual(mock_request.call_args[1]["json"], {"isRead": True})


if __name__ == "__main__":
    unittest.main()
