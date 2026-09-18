import json
import unittest
from unittest.mock import MagicMock, patch

from app.pipeline.message_processor import process_new_message


class TestMessageProcessorIntegration(unittest.TestCase):
    @patch("app.backend.client.httpx.post")
    @patch("app.backend.client.httpx.get")
    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_fallback_to_xml_when_subject_not_starting_with_s(
        self, mock_save_att, mock_get_att, mock_get_msg, mock_http_get, mock_http_post
    ):
        message_id = "test_msg_non_s_subject"

        # Mock Core Data API calls
        mock_post_email = MagicMock()
        mock_post_email.status_code = 200
        mock_post_email.json.return_value = {"emailLogId": 8}

        mock_get_att_list = MagicMock()
        mock_get_att_list.status_code = 200
        mock_get_att_list.json.return_value = {
            "attachments": [
                {"attachmentId": 801, "fileName": "FE-50276.xml"},
                {"attachmentId": 802, "fileName": "FE-50276.pdf"},
            ]
        }

        mock_post_activity = MagicMock()
        mock_post_activity.status_code = 200
        mock_post_activity.json.return_value = {"activityId": 5001}

        mock_http_post.side_effect = [mock_post_email, mock_post_activity, mock_post_activity]
        mock_http_get.return_value = mock_get_att_list

        # Subject does NOT start with S
        mock_get_msg.return_value = {
            "id": message_id,
            "subject": "Shipment No: 50276 - Documents",
            "from": {"emailAddress": {"address": "customer@example.com"}},
            "bodyPreview": "Here are the files",
            "receivedDateTime": "2026-09-17T10:30:33.464Z",
        }
        mock_get_att.return_value = [
            {"id": "att1", "name": "FE-50276.xml", "contentType": "text/xml", "size": 100},
            {"id": "att2", "name": "FE-50276.pdf", "contentType": "application/pdf", "size": 500},
        ]

        sample_factura = """<?xml version="1.0" encoding="utf-8"?>
<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica">
    <Clave>50618052600310265506100100001010000050276194729135</Clave>
    <NumeroConsecutivo>00100001010000050276</NumeroConsecutivo>
    <Otros>
        <OtroTexto codigo="Shipment Reference">REF:SCSR00306822,INV:CR10135</OtroTexto>
    </Otros>
</FacturaElectronica>"""

        def mock_save_side_effect(att, dest_dir):
            file_path = dest_dir / att["name"]
            if att["name"] == "FE-50276.xml":
                file_path.write_text(sample_factura, encoding="utf-8")
            else:
                file_path.write_bytes(b"%PDF dummy")
            return file_path

        mock_save_att.side_effect = mock_save_side_effect

        result_data = process_new_message(message_id)

        self.assertEqual(result_data["shipment_source"], "xml_otro_texto")
        self.assertEqual(result_data["shipment_number"], "SCSR00306822")
        self.assertEqual(result_data["invoice_number"], "00100001010000050276")
        self.assertEqual(result_data["email_log_id"], 8)
        self.assertEqual(len(result_data["activities_created"]), 2)

    @patch("app.backend.client.httpx.post")
    @patch("app.backend.client.httpx.get")
    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_direct_subject_when_starting_with_s(
        self, mock_save_att, mock_get_att, mock_get_msg, mock_http_get, mock_http_post
    ):
        message_id = "test_msg_s_subject"

        # Mock Core Data API calls
        mock_post_email = MagicMock()
        mock_post_email.status_code = 200
        mock_post_email.json.return_value = {"emailLogId": 9}

        mock_get_att_list = MagicMock()
        mock_get_att_list.status_code = 200
        mock_get_att_list.json.return_value = {
            "attachments": [
                {"attachmentId": 901, "fileName": "FE-50277.xml"},
            ]
        }

        mock_post_activity = MagicMock()
        mock_post_activity.status_code = 200
        mock_post_activity.json.return_value = {"activityId": 6001}

        mock_http_post.side_effect = [mock_post_email, mock_post_activity]
        mock_http_get.return_value = mock_get_att_list

        # Subject starts with S
        mock_get_msg.return_value = {
            "id": message_id,
            "subject": "Shipment N°: SCSR99999999 - Costa Rica",
        }
        mock_get_att.return_value = [
            {"id": "att1", "name": "FE-50277.xml", "contentType": "text/xml", "size": 100},
        ]

        sample_factura = """<?xml version="1.0" encoding="utf-8"?>
<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica">
    <Clave>50618052600310265506100100001010000050277194729135</Clave>
    <NumeroConsecutivo>00100001010000050277</NumeroConsecutivo>
</FacturaElectronica>"""

        def mock_save_side_effect(att, dest_dir):
            file_path = dest_dir / att["name"]
            file_path.write_text(sample_factura, encoding="utf-8")
            return file_path

        mock_save_att.side_effect = mock_save_side_effect

        result_data = process_new_message(message_id)

        self.assertEqual(result_data["shipment_number"], "SCSR99999999")
        self.assertEqual(result_data["shipment_source"], "subject")
        self.assertEqual(result_data["invoice_number"], "00100001010000050277")
        self.assertEqual(result_data["email_log_id"], 9)
        self.assertEqual(len(result_data["activities_created"]), 1)


if __name__ == "__main__":
    unittest.main()
