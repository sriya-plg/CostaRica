import unittest
from app.pipeline.subject_parser import extract_shipment_number


class TestSubjectParser(unittest.TestCase):
    def test_extract_shipment_number_formats(self):
        test_cases = [
            ("Shipment N°: PGAA00307692", "PGAA00307692"),
            ("Shipment Nº: PGAA00307692", "PGAA00307692"),
            ("Shipment N° PGAA00307692", "PGAA00307692"),
            ("Shipment No: 50276", "50276"),
            ("Shipment No. 50276", "50276"),
            ("Shipment #: 50277", "50277"),
            ("Shipment #50277", "50277"),
            ("Shipment 50293", "50293"),
            ("Shipment: PGAA00307692", "PGAA00307692"),
            ("FW: Shipment N°: PGAA00307692 - Costa Rica Invoices", "PGAA00307692"),
            ("Re: Shipment No: 50276 [EXTERNAL]", "50276"),
            ("SHIPMENT NUMBER: 998877", "998877"),
        ]

        for subject, expected in test_cases:
            with self.subTest(subject=subject):
                self.assertEqual(extract_shipment_number(subject), expected)

    def test_extract_shipment_number_none_or_invalid(self):
        self.assertIsNone(extract_shipment_number(None))
        self.assertIsNone(extract_shipment_number(""))
        self.assertIsNone(extract_shipment_number("Hello team, please find attached files"))
        self.assertIsNone(extract_shipment_number("Invoice 12345 attached"))


if __name__ == "__main__":
    unittest.main()
