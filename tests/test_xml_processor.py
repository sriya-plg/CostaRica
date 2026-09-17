from pathlib import Path
import tempfile
import unittest

from app.pipeline.xml_processor import (
    get_xml_root_localname,
    extract_numero_consecutivo,
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
            self.assertIsNotNone(result["invoice_xml"])
            self.assertIn("FE-50277.xml", result["invoice_xml"])
            self.assertIsNotNone(result["ahc_xml"])
            self.assertIn("AHC-50277.xml", result["ahc_xml"])
            self.assertEqual(result["xml_files_found"], 2)
            self.assertIn("FE-50277.pdf", result["ignored_files"])


if __name__ == "__main__":
    unittest.main()
