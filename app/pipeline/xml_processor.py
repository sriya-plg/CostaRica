import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT_FACTURA_ELECTRONICA = "FacturaElectronica"
ROOT_MENSAJE_HACIENDA = "MensajeHacienda"

# Matches REF:SCSR00306822 or REF: S...
_REF_PATTERN = re.compile(r"(?i)\bREF\s*:\s*(S[A-Za-z0-9_\-]+)")


def get_xml_root_localname(xml_path: Path) -> str | None:
    """Parse XML and return the local name of the root element, ignoring any XML namespaces."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        return root.tag.split("}")[-1]
    except Exception as exc:
        logger.error("Failed to parse XML file %s: %s", xml_path, exc)
        return None


def extract_numero_consecutivo(xml_path: Path) -> str | None:
    """Extract <NumeroConsecutivo> value from FacturaElectronica XML, handling namespaces."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for elem in root.iter():
            tag_name = elem.tag.split("}")[-1]
            if tag_name == "NumeroConsecutivo":
                if elem.text:
                    return elem.text.strip()
        logger.warning("Tag <NumeroConsecutivo> not found in %s", xml_path)
        return None
    except Exception as exc:
        logger.error("Error reading <NumeroConsecutivo> from %s: %s", xml_path, exc)
        return None


def extract_shipment_reference_from_xml(xml_path: Path) -> str | None:
    """
    Extract shipment reference starting with 'S' from <OtroTexto> in FacturaElectronica.
    Example: <OtroTexto codigo="Shipment Reference">REF:SCSR00306822,INV:CR10135</OtroTexto>
    Returns 'SCSR00306822'.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for elem in root.iter():
            tag_name = elem.tag.split("}")[-1]
            if tag_name == "OtroTexto":
                text = elem.text or ""
                match = _REF_PATTERN.search(text)
                if match:
                    ref_val = match.group(1).strip()
                    logger.info("Found Shipment Reference=%s in <OtroTexto> in %s", ref_val, xml_path)
                    return ref_val
        return None
    except Exception as exc:
        logger.error("Error reading shipment reference from %s: %s", xml_path, exc)
        return None


def process_xml_attachments(dest_dir: Path) -> dict[str, Any]:
    """
    Scans the downloaded directory strictly for *.xml files.
    - PDF and non-XML files are ignored and never opened/parsed.
    - FacturaElectronica root -> Classified as Invoice XML:
        - Extracts <NumeroConsecutivo> (Invoice Number)
        - Extracts <OtroTexto> REF:S... (Shipment Reference fallback)
    - MensajeHacienda root -> Classified as Hacienda/AHC XML, skips invoice number extraction.
    """
    dest_path = Path(dest_dir)
    if not dest_path.exists() or not dest_path.is_dir():
        logger.error("Download directory does not exist: %s", dest_dir)
        return {
            "invoice_number": None,
            "shipment_reference": None,
            "invoice_xml": None,
            "ahc_xml": None,
            "xml_files_found": 0,
            "ignored_files": [],
        }

    invoice_number: str | None = None
    shipment_reference: str | None = None
    invoice_xml_path: str | None = None
    ahc_xml_path: str | None = None
    xml_files: list[str] = []
    ignored_files: list[str] = []

    for file_path in dest_path.iterdir():
        if not file_path.is_file():
            continue

        # Strictly filter by .xml extension
        if file_path.suffix.lower() != ".xml":
            ignored_files.append(file_path.name)
            logger.info("Ignoring non-XML file: %s (PDF/other not parsed per rule)", file_path.name)
            continue

        xml_files.append(file_path.name)
        root_name = get_xml_root_localname(file_path)
        logger.info("Identified XML file %s with root element <%s>", file_path.name, root_name)

        if root_name == ROOT_FACTURA_ELECTRONICA:
            invoice_xml_path = str(file_path)
            extracted_num = extract_numero_consecutivo(file_path)
            if extracted_num:
                invoice_number = extracted_num
                logger.info("Extracted Invoice Number (NumeroConsecutivo)=%s from %s", invoice_number, file_path.name)
            
            extracted_ref = extract_shipment_reference_from_xml(file_path)
            if extracted_ref:
                shipment_reference = extracted_ref
                logger.info("Extracted XML Shipment Reference=%s from %s", shipment_reference, file_path.name)
        elif root_name == ROOT_MENSAJE_HACIENDA:
            ahc_xml_path = str(file_path)
            logger.info("Classified as AHC/Hacienda XML (%s); skipped invoice extraction", file_path.name)
        else:
            logger.warning("Unrecognized XML root element <%s> in %s", root_name, file_path.name)

    return {
        "invoice_number": invoice_number,
        "shipment_reference": shipment_reference,
        "invoice_xml": invoice_xml_path,
        "ahc_xml": ahc_xml_path,
        "xml_files_found": len(xml_files),
        "ignored_files": ignored_files,
    }
