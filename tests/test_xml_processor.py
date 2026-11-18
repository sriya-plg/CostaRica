from pathlib import Path
import tempfile
import unittest

from app.pipeline.xml_processor import (
    get_xml_root_localname,
    extract_numero_consecutivo,
    extract_reference_number_from_xml,
    extract_shipment_from_pdf,
    extract_shipment_reference_from_xml,
    process_xml_attachments,
)


class TestXmlProcessor(unittest.TestCase):
    def test_real_sample_factura_xml(self):
        sample_file = Path("downloads/2026-09-11_03-07-23/FE-50618052600310265506100100001010000050276194729135.xml")
        if not sample_file.exists():
            self.skipTest("Sample file not present in workspace")

        root_name = get_xml_root_localname(sample_file)
        self.assertEqual(root_name, "FacturaElectronica")

        numero = extract_numero_consecutivo(sample_file)
        self.assertEqual(numero, "00100001010000050276")

        shipment_ref = extract_shipment_reference_from_xml(sample_file)
        self.assertEqual(shipment_ref, "SCSR00306822")

        reference_no = extract_reference_number_from_xml(sample_file)
        self.assertEqual(reference_no, "REF:SCSR00306822,INV:CR10135")

    def test_process_directory_with_factura_ahc_and_pdf(self):
        sample_factura = """<?xml version="1.0" encoding="utf-8"?>
<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica">
    <Clave>50618052600310265506100100001010000050277194729135</Clave>
    <NumeroConsecutivo>00100001010000050277</NumeroConsecutivo>
    <Otros>
        <OtroTexto codigo="Shipment Reference">REF:SCSR00306822,INV:CR10135</OtroTexto>
    </Otros>
</FacturaElectronica>"""

        sample_ahc = """<?xml version="1.0" encoding="utf-8"?>
<MensajeHacienda xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/mensajeHacienda">
    <Clave>50618052600310265506100100001010000050277194729135</Clave>
    <EstadoMensaje>Aceptado</EstadoMensaje>
</MensajeHacienda>"""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "FE-50277.xml").write_text(sample_factura, encoding="utf-8")
            (tmp_path / "AHC-50277.xml").write_text(sample_ahc, encoding="utf-8")
            (tmp_path / "FE-50277.pdf").write_bytes(b"%PDF-1.4 dummy pdf content")

            result = process_xml_attachments(tmp_path)

            self.assertEqual(result["invoice_number"], "00100001010000050277")
            self.assertEqual(result["shipment_reference"], "SCSR00306822")
            self.assertEqual(result["reference_number"], "REF:SCSR00306822,INV:CR10135")
            self.assertIsNotNone(result["invoice_xml"])
            self.assertIn("FE-50277.xml", result["invoice_xml"])
            self.assertIsNotNone(result["ahc_xml"])
            self.assertIn("AHC-50277.xml", result["ahc_xml"])
            self.assertEqual(result["xml_files_found"], 2)
            self.assertIn("FE-50277.pdf", result["ignored_files"])

    def test_reference_number_blank_without_ref_keyword(self):
        sample_factura = """<?xml version="1.0" encoding="utf-8"?>
<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica">
    <Clave>50618052600310265506100100001010000050293194729135</Clave>
    <NumeroConsecutivo>00100001010000050293</NumeroConsecutivo>
    <Otros>
        <OtroTexto>Sellado por: www.comprobanteselectronicoscr.com</OtroTexto>
        <OtroTexto codigo="Shipment Reference">FCL,1X40HC,//,ETD,08,de,mayo,2026</OtroTexto>
    </Otros>
</FacturaElectronica>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir) / "FE-50293.xml"
            xml_path.write_text(sample_factura, encoding="utf-8")
            self.assertIsNone(extract_reference_number_from_xml(xml_path))

    def test_extract_shipment_from_real_sample_pdfs(self):
        pdf_with_s = Path(
            "downloads/2026-11-16_04-43-52/FE-50618052600310265506100100001010000050293194729135 (1).pdf"
        )
        if pdf_with_s.exists():
            self.assertEqual(extract_shipment_from_pdf(pdf_with_s), "S00307578")

        pdf_without_s = Path("downloads/2026-11-16_04-13-56/PGAA2 ((CI PPWRK))-1-47.pdf")
        if pdf_without_s.exists():
            self.assertIsNone(extract_shipment_from_pdf(pdf_without_s))

    def test_extract_shipment_reference_pdf_layouts(self):
        cases = [
            (
                "FE-15163_terumo.pdf",
                "\n".join([
                    "INVOICE KEY 00100001040000015163",
                    "SHIPMENT",
                    "N/A",
                    "SHIPMENT DETAILS",
                    "ORDER NUMBERS / OWNER'S REFERENCE",
                    "WEIGHT (KGS)",
                    "4514",
                    "BILL OF LADING / AIRWAYBIL",
                    "SCSR00303751",
                ]),
                "SCSR00303751",
            ),
            (
                "FE-50276_flextronics.pdf",
                "\n".join([
                    "INVOICE KEY 00100001010000050276",
                    "SHIPMENT",
                    "N/A",
                    "ORDER NUMBERS / OWNER'S REFERENCE",
                    "REF:SCSR00306822,INV:CR10135",
                    "BILL OF LADING / AIRWAYBIL",
                    "PGAA00306822",
                ]),
                "SCSR00306822",
            ),
            (
                "FE-50277_microtech.pdf",
                "\n".join([
                    "INVOICE KEY 00100001010000050277",
                    "SHIPMENT",
                    "N/A",
                    "ORDER NUMBERS / OWNER'S REFERENCE",
                    "REF:SCSR00307692,CNTR:KOSU4512765,Seal:KOSL356186,ZF:CR001033420",
                    "BILL OF LADING / AIRWAYBIL",
                    "PGAA00307692",
                ]),
                "SCSR00307692",
            ),
            (
                "FE-50289_cs_automotive.pdf",
                "\n".join([
                    "INVOICE KEY 00100001010000050289",
                    "SHIPMENT",
                    "N/A",
                    "ORDER NUMBERS / OWNER'S REFERENCE",
                    "INVOICE,NO.:,LY20260109-001",
                    "BILL OF LADING / AIRWAYBIL",
                    "PSLSHASJO06179",
                ]),
                None,
            ),
            (
                "FE-50293_nitinol.pdf",
                "\n".join([
                    "INVOICE KEY 00100001010000050293",
                    "SHIPMENT",
                    "N/A",
                    "ORDER NUMBERS / OWNER'S REFERENCE",
                    "FCL,1X40HC,//,ETD,08,de,mayo,2026",
                    "BILL OF LADING / AIRWAYBIL",
                    "S00307578",
                ]),
                "S00307578",
            ),
            (
                "charges_no_false_positive.pdf",
                "\n".join([
                    "SHIPMENT DETAILS",
                    "S99999999",
                    "Origin Charges Per Shipment",
                    "S88888888",
                    "Destination Charges Per Shipment",
                    "S77777777",
                    "Air Waybill #",
                    "S66666666",
                ]),
                None,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for filename, content, expected in cases:
                with self.subTest(filename=filename):
                    pdf_path = tmp_path / filename
                    pdf_path.write_text(content, encoding="latin1")
                    self.assertEqual(extract_shipment_from_pdf(pdf_path), expected)


if __name__ == "__main__":
    unittest.main()
