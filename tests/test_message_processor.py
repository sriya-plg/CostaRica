import json
import unittest
from unittest.mock import patch

from app.persistence.processed_emails import get_processed_email, init_db, insert_processed_email
from app.pipeline.message_processor import process_new_message


class TestMessageProcessorIntegration(unittest.TestCase):
    def setUp(self):
        init_db()

    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_fallback_to_xml_when_subject_not_starting_with_s(
        self, mock_save_att, mock_get_att, mock_get_msg
    ):
        message_id = "test_msg_non_s_subject"
        insert_processed_email(message_id, status="received")

        # Subject does NOT start with S
        mock_get_msg.return_value = {
            "id": message_id,
            "subject": "Shipment No: 50276 - Documents",
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

        process_new_message(message_id)

        row = get_processed_email(message_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "processed")
        # Should fallback to XML OtroTexto value SCSR00306822
        self.assertEqual(row["shipment_number"], "SCSR00306822")
        self.assertEqual(row["invoice_number"], "00100001010000050276")

        result_data = json.loads(row["result_json"])
        self.assertEqual(result_data["shipment_source"], "xml_otro_texto")
        self.assertEqual(result_data["shipment_number"], "SCSR00306822")

    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_direct_subject_when_starting_with_s(
        self, mock_save_att, mock_get_att, mock_get_msg
    ):
        message_id = "test_msg_s_subject"
        insert_processed_email(message_id, status="received")

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

        process_new_message(message_id)

        row = get_processed_email(message_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["shipment_number"], "SCSR99999999")

        result_data = json.loads(row["result_json"])
        self.assertEqual(result_data["shipment_source"], "subject")


if __name__ == "__main__":
    unittest.main()
