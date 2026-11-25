import unittest
from unittest.mock import MagicMock, patch

from app.graph.messages import (
    get_message_details,
    list_unread_emails,
    mark_message_as_read,
    send_alert_email,
)


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

    @patch("app.graph.messages.settings.ALERT_EMAIL", "ops@example.com, admin@example.com")
    @patch("app.graph.messages.graph_client.request")
    def test_send_alert_email_posts_to_graph(self, mock_request):
        sent = send_alert_email(
            message_id="msg_alert_1",
            subject="Invoice 123",
            reason="Message msg_alert_1 has no PDF attachment",
            sender="vendor@example.com",
            received_at="2026-11-25T10:00:00Z",
        )
        self.assertTrue(sent)
        mock_request.assert_called_once()
        method, path = mock_request.call_args[0]
        self.assertEqual(method, "POST")
        self.assertTrue(path.endswith("/sendMail"))
        payload = mock_request.call_args[1]["json"]
        recipients = [r["emailAddress"]["address"] for r in payload["message"]["toRecipients"]]
        self.assertEqual(recipients, ["ops@example.com", "admin@example.com"])
        self.assertIn("Message msg_alert_1 has no PDF attachment", payload["message"]["body"]["content"])

    @patch("app.graph.messages.settings.ALERT_EMAIL", "")
    @patch("app.graph.messages.graph_client.request")
    def test_send_alert_email_skips_when_unconfigured(self, mock_request):
        sent = send_alert_email(
            message_id="msg_alert_2",
            subject="Invoice 456",
            reason="Azure failed",
        )
        self.assertFalse(sent)
        mock_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
