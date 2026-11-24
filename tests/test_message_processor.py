import json
import unittest
from unittest.mock import MagicMock, patch

from app.pipeline.message_processor import process_new_message


class TestMessageProcessorIntegration(unittest.TestCase):
    @patch("app.pipeline.message_processor.upload_pdf_to_azure")
    @patch("app.backend.client.httpx.post")
    @patch("app.backend.client.httpx.get")
    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_fallback_to_xml_when_subject_not_starting_with_s(
        self, mock_save_att, mock_get_att, mock_get_msg, mock_http_get, mock_http_post, mock_upload_pdf
    ):
        mock_upload_pdf.return_value = (
            "https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/FE-50276.pdf"
        )
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

        mock_post_ml = MagicMock()
        mock_post_ml.status_code = 200
        mock_post_ml.json.return_value = {"success": True}

        mock_http_post.side_effect = [
            mock_post_email,
            mock_post_activity,
            mock_post_ml,
            mock_post_activity,
            mock_post_ml,
        ]
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
        self.assertEqual(result_data["reference_number"], "REF:SCSR00306822,INV:CR10135")
        self.assertEqual(result_data["email_log_id"], 8)
        self.assertEqual(len(result_data["activities_created"]), 2)
        mock_upload_pdf.assert_called_once()
        self.assertIn("FE-50276.pdf", result_data["uploaded_blobs"])
        self.assertEqual(
            result_data["uploaded_blobs"]["FE-50276.pdf"],
            "https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/FE-50276.pdf",
        )
        # Verify AddCoreDataEmailLog payload received only the Azure Blob URL for the PDF (no XML)
        first_post_payload = mock_http_post.call_args_list[0].kwargs["json"]
        filenames_sent = [att["fileName"] for att in first_post_payload["attachments"]]
        self.assertEqual(
            filenames_sent,
            ["https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/FE-50276.pdf"],
        )
        ml_payload = mock_http_post.call_args_list[2].kwargs["json"]
        self.assertEqual(
            ml_payload["mlRequest"],
            {
                "invoiceKey": "00100001010000050276",
                "shipmentNo": "SCSR00306822",
                "referenceNo": "REF:SCSR00306822,INV:CR10135",
            },
        )

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

        mock_post_ml = MagicMock()
        mock_post_ml.status_code = 200
        mock_post_ml.json.return_value = {"success": True}

        mock_http_post.side_effect = [mock_post_email, mock_post_activity, mock_post_ml]
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
        self.assertIsNone(result_data["reference_number"])
        self.assertEqual(result_data["email_log_id"], 9)
        self.assertEqual(len(result_data["activities_created"]), 1)
        ml_payload = mock_http_post.call_args_list[2].kwargs["json"]
        self.assertEqual(
            ml_payload["mlRequest"],
            {
                "invoiceKey": "00100001010000050277",
                "shipmentNo": "SCSR99999999",
                "referenceNo": "",
            },
        )

    @patch("app.pipeline.message_processor.upload_pdf_to_azure")
    @patch("app.backend.client.httpx.post")
    @patch("app.backend.client.httpx.get")
    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_fallback_to_pdf_when_subject_and_xml_have_no_s_shipment(
        self, mock_save_att, mock_get_att, mock_get_msg, mock_http_get, mock_http_post, mock_upload_pdf
    ):
        mock_upload_pdf.return_value = (
            "https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/FE-50293.pdf"
        )
        message_id = "test_msg_pdf_fallback"

        mock_post_email = MagicMock()
        mock_post_email.status_code = 200
        mock_post_email.json.return_value = {"emailLogId": 10}

        mock_get_att_list = MagicMock()
        mock_get_att_list.status_code = 200
        mock_get_att_list.json.return_value = {
            "attachments": [
                {"attachmentId": 1001, "fileName": "FE-50293.xml"},
                {"attachmentId": 1002, "fileName": "FE-50293.pdf"},
            ]
        }

        mock_post_activity = MagicMock()
        mock_post_activity.status_code = 200
        mock_post_activity.json.return_value = {"activityId": 7001}

        mock_post_ml = MagicMock()
        mock_post_ml.status_code = 200
        mock_post_ml.json.return_value = {"success": True}

        mock_http_post.side_effect = [
            mock_post_email,
            mock_post_activity,
            mock_post_ml,
            mock_post_activity,
            mock_post_ml,
        ]
        mock_http_get.return_value = mock_get_att_list

        mock_get_msg.return_value = {
            "id": message_id,
            "subject": "Shipment No: 50293 - Documents",
        }
        mock_get_att.return_value = [
            {"id": "att1", "name": "FE-50293.xml", "contentType": "text/xml", "size": 100},
            {"id": "att2", "name": "FE-50293.pdf", "contentType": "application/pdf", "size": 500},
        ]

        sample_factura = """<?xml version="1.0" encoding="utf-8"?>
<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica">
    <Clave>50618052600310265506100100001010000050293194729135</Clave>
    <NumeroConsecutivo>00100001010000050293</NumeroConsecutivo>
    <Otros>
        <OtroTexto codigo="Shipment Reference">FCL,1X40HC,//,ETD,08,de,mayo,2026</OtroTexto>
    </Otros>
</FacturaElectronica>"""

        def mock_save_side_effect(att, dest_dir):
            file_path = dest_dir / att["name"]
            if att["name"] == "FE-50293.xml":
                file_path.write_text(sample_factura, encoding="utf-8")
            else:
                file_path.write_text("%PDF-1.4\nBILL OF LADING / AIRWAYBIL\nS00307578\n", encoding="latin1")
            return file_path

        mock_save_att.side_effect = mock_save_side_effect

        result_data = process_new_message(message_id)

        self.assertEqual(result_data["shipment_number"], "S00307578")
        self.assertEqual(result_data["shipment_source"], "pdf")
        self.assertEqual(result_data["invoice_number"], "00100001010000050293")
        self.assertIsNone(result_data["reference_number"])
        ml_payload = mock_http_post.call_args_list[2].kwargs["json"]
        self.assertEqual(
            ml_payload["mlRequest"],
            {
                "invoiceKey": "00100001010000050293",
                "shipmentNo": "S00307578",
                "referenceNo": "",
            },
        )

    @patch("app.pipeline.message_processor.upload_pdf_to_azure")
    @patch("app.backend.client.httpx.post")
    @patch("app.backend.client.httpx.get")
    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_shipment_blank_when_none_of_subject_xml_pdf_has_s_number(
        self, mock_save_att, mock_get_att, mock_get_msg, mock_http_get, mock_http_post, mock_upload_pdf
    ):
        mock_upload_pdf.return_value = (
            "https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/FE-50293.pdf"
        )
        message_id = "test_msg_no_s_anywhere"

        mock_post_email = MagicMock()
        mock_post_email.status_code = 200
        mock_post_email.json.return_value = {"emailLogId": 11}

        mock_get_att_list = MagicMock()
        mock_get_att_list.status_code = 200
        mock_get_att_list.json.return_value = {
            "attachments": [
                {"attachmentId": 1101, "fileName": "FE-50293.xml"},
                {"attachmentId": 1102, "fileName": "FE-50293.pdf"},
            ]
        }

        mock_post_activity = MagicMock()
        mock_post_activity.status_code = 200
        mock_post_activity.json.return_value = {"activityId": 8001}

        mock_post_ml = MagicMock()
        mock_post_ml.status_code = 200
        mock_post_ml.json.return_value = {"success": True}

        mock_http_post.side_effect = [
            mock_post_email,
            mock_post_activity,
            mock_post_ml,
            mock_post_activity,
            mock_post_ml,
        ]
        mock_http_get.return_value = mock_get_att_list

        mock_get_msg.return_value = {
            "id": message_id,
            "subject": "Shipment No: 50293",
        }
        mock_get_att.return_value = [
            {"id": "att1", "name": "FE-50293.xml", "contentType": "text/xml", "size": 100},
            {"id": "att2", "name": "FE-50293.pdf", "contentType": "application/pdf", "size": 500},
        ]

        sample_factura = """<?xml version="1.0" encoding="utf-8"?>
<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica">
    <Clave>50618052600310265506100100001010000050293194729135</Clave>
    <NumeroConsecutivo>00100001010000050293</NumeroConsecutivo>
    <Otros>
        <OtroTexto codigo="Shipment Reference">FCL,1X40HC,//,ETD,08,de,mayo,2026</OtroTexto>
    </Otros>
</FacturaElectronica>"""

        def mock_save_side_effect(att, dest_dir):
            file_path = dest_dir / att["name"]
            if att["name"] == "FE-50293.xml":
                file_path.write_text(sample_factura, encoding="utf-8")
            else:
                file_path.write_bytes(b"%PDF-1.4\nAir Waybill # 3047867\n")
            return file_path

        mock_save_att.side_effect = mock_save_side_effect

        result_data = process_new_message(message_id)

        self.assertIsNone(result_data["shipment_number"])
        self.assertEqual(result_data["shipment_source"], "not_found")
        self.assertEqual(result_data["invoice_number"], "00100001010000050293")
        self.assertIsNone(result_data["reference_number"])
        ml_payload = mock_http_post.call_args_list[2].kwargs["json"]
        self.assertEqual(
            ml_payload["mlRequest"],
            {
                "invoiceKey": "00100001010000050293",
                "shipmentNo": "",
                "referenceNo": "",
            },
        )

    @patch("app.pipeline.message_processor.upload_pdf_to_azure")
    @patch("app.backend.client.httpx.post")
    @patch("app.backend.client.httpx.get")
    @patch("app.pipeline.message_processor.get_message_details")
    @patch("app.pipeline.message_processor.get_attachments")
    @patch("app.pipeline.message_processor.save_attachment")
    def test_only_pdf_uploaded_to_blob_and_sent_to_email_log(
        self, mock_save_att, mock_get_att, mock_get_msg, mock_http_get, mock_http_post, mock_upload_pdf
    ):
        pdf_url = "https://plgaiml1.blob.core.windows.net/plgaiml1/cwdocs/FE-50277.pdf"
        mock_upload_pdf.return_value = pdf_url
        message_id = "test_msg_pdf_only_payload"

        mock_post_email = MagicMock()
        mock_post_email.status_code = 200
        mock_post_email.json.return_value = {"emailLogId": 12}

        mock_get_att_list = MagicMock()
        mock_get_att_list.status_code = 200
        mock_get_att_list.json.return_value = {
            "attachments": [
                {"attachmentId": 1201, "fileName": pdf_url},
            ]
        }

        mock_post_activity = MagicMock()
        mock_post_activity.status_code = 200
        mock_post_activity.json.return_value = {"activityId": 9001}

        mock_post_ml = MagicMock()
        mock_post_ml.status_code = 200
        mock_post_ml.json.return_value = {"success": True}

        mock_http_post.side_effect = [mock_post_email, mock_post_activity, mock_post_ml]
        mock_http_get.return_value = mock_get_att_list

        mock_get_msg.return_value = {
            "id": message_id,
            "subject": "FW: Invoice Shipment N°: PGAA00307692",
            "from": {"emailAddress": {"address": "rbanua@pegasuslogistics.com"}},
            "bodyPreview": "FYI",
            "receivedDateTime": "2026-11-23T16:27:58Z",
        }
        mock_get_att.return_value = [
            {"id": "att1", "name": "FE-50277.pdf", "contentType": "application/pdf", "size": 500},
            {"id": "att2", "name": "FE-50277.xml", "contentType": "text/xml", "size": 200},
            {"id": "att3", "name": "AHC-50277.xml", "contentType": "text/xml", "size": 150},
            {"id": "att4", "name": "image001.png", "contentType": "image/png", "size": 50},
            {"id": "att5", "name": "image002.png", "contentType": "image/png", "size": 50},
        ]

        sample_factura = """<?xml version="1.0" encoding="utf-8"?>
<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica">
    <Clave>50618052600310265506100100001010000050277194729135</Clave>
    <NumeroConsecutivo>00100001010000050277</NumeroConsecutivo>
    <Otros>
        <OtroTexto codigo="Shipment Reference">REF:SCSR00307692,INV:CR10135</OtroTexto>
    </Otros>
</FacturaElectronica>"""
        sample_ahc = """<?xml version="1.0" encoding="utf-8"?>
<MensajeHacienda xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/mensajeHacienda">
    <Clave>50618052600310265506100100001010000050277194729135</Clave>
</MensajeHacienda>"""

        def mock_save_side_effect(att, dest_dir):
            file_path = dest_dir / att["name"]
            if att["name"] == "FE-50277.xml":
                file_path.write_text(sample_factura, encoding="utf-8")
            elif att["name"] == "AHC-50277.xml":
                file_path.write_text(sample_ahc, encoding="utf-8")
            elif att["name"].endswith(".pdf"):
                file_path.write_bytes(b"%PDF-1.4 dummy")
            else:
                file_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            return file_path

        mock_save_att.side_effect = mock_save_side_effect

        result_data = process_new_message(message_id)

        mock_upload_pdf.assert_called_once()
        self.assertEqual(mock_upload_pdf.call_args.args[0].name, "FE-50277.pdf")
        self.assertEqual(result_data["uploaded_blobs"], {"FE-50277.pdf": pdf_url})

        first_post_payload = mock_http_post.call_args_list[0].kwargs["json"]
        self.assertEqual(
            first_post_payload["attachments"],
            [{"attachmentId": 0, "fileName": pdf_url}],
        )
        self.assertEqual(result_data["invoice_number"], "00100001010000050277")
        self.assertEqual(result_data["shipment_number"], "SCSR00307692")


if __name__ == "__main__":
    unittest.main()
