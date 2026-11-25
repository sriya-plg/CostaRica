import logging
import re
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT_FACTURA_ELECTRONICA = "FacturaElectronica"
ROOT_MENSAJE_HACIENDA = "MensajeHacienda"

# Matches REF:SCSR00306822 or REF: S...
_REF_PATTERN = re.compile(r"(?i)\bREF\s*:\s*(S[A-Za-z0-9_\-]+)")
_REF_KEYWORD_PATTERN = re.compile(r"(?i)\bREF\b")

_PDF_LABEL_PATTERN = re.compile(
    r"(?i)^(?:"
    r"SHIPMENT(?:\s*[:#]\s*.*)?|"
    r"ORDER\s+NUMBERS\s*/\s*OWNER'?S\s+REFERENCE(?:\s*[:#]\s*.*)?|"
    r"BILL\s+OF\s+LADING\s*/\s*AIRWAYBIL+(?:\s*[:#]\s*.*)?|"
    r"INVOICE(?:\s+KEY)?(?:\s*[:#]?\s+\S+)?"
    r")$"
)
_PDF_STOP_LINE_PATTERN = re.compile(
    r"(?i)^(?:SHIPMENT\s+DETAILS|CONSIGNOR|CONSIGNEE|WEIGHT\b|VOLUME\b|"
    r"CHARGEABLE\b|CONTAINERS|CHARGES|DESCRIPTION|DUE\s+DATE|TERMS|Page\s+\d)"
)
_PDF_S_NUMBER_PATTERN = re.compile(r"(?i)\b(S[A-Za-z]{0,4}\d{4,}[A-Za-z0-9_\-]*)\b")


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


def extract_reference_number_from_xml(xml_path: Path) -> str | None:
    """
    Extract complete <OtroTexto> text for referenceNo if it contains the REF keyword.
    Prefers <OtroTexto codigo="..."> elements, falling back to any <OtroTexto> element.
    Returns None if no <OtroTexto> contains the REF keyword.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        otro_texto_elems = [
            elem for elem in root.iter() if elem.tag.split("}")[-1] == "OtroTexto"
        ]
        with_codigo = [
            elem for elem in otro_texto_elems
            if any(k.lower() == "codigo" for k in elem.attrib)
        ]
        candidates = with_codigo or otro_texto_elems
        for elem in candidates:
            text = (elem.text or "").strip()
            if text and _REF_KEYWORD_PATTERN.search(text):
                logger.info("Found referenceNo=%r in <OtroTexto> in %s", text, xml_path)
                return text
        return None
    except Exception as exc:
        logger.error("Error reading referenceNo from %s: %s", xml_path, exc)
        return None


def _extract_lines_with_pdf_library(pdf_path: Path) -> list[str]:
    """Extract text lines using pymupdf, pypdf, or PyPDF2 if available."""
    try:
        import fitz  # type: ignore

        with fitz.open(pdf_path) as doc:
            lines: list[str] = []
            for page in doc:
                for line in page.get_text("text").splitlines():
                    stripped = line.strip()
                    if stripped:
                        lines.append(stripped)
            return lines
    except Exception:
        pass

    for mod_name in ("pypdf", "PyPDF2"):
        try:
            mod = __import__(mod_name)
            reader = mod.PdfReader(str(pdf_path))
            lines = []
            for page in reader.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped:
                        lines.append(stripped)
            return lines
        except Exception:
            pass

    return []


def extract_text_lines_from_pdf(pdf_path: Path) -> list[str]:
    """Extract non-empty text lines from a PDF using installed libraries and stream parsing."""
    lines = _extract_lines_with_pdf_library(pdf_path)

    try:
        raw = Path(pdf_path).read_bytes()
    except Exception as exc:
        logger.error("Failed to read PDF file %s: %s", pdf_path, exc)
        return lines

    streams: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        stream_bytes = match.group(1)
        try:
            streams.append(zlib.decompress(stream_bytes).decode("latin1", errors="ignore"))
        except Exception:
            streams.append(stream_bytes.decode("latin1", errors="ignore"))

    stream_lines: list[str] = []
    for st in streams:
        if "begincmap" in st:
            continue
        for tok in re.findall(r"\(([^()]*)\)\s*Tj", st):
            stripped = tok.strip()
            if stripped:
                stream_lines.append(stripped)
        for arr in re.findall(r"\[(.*?)\]\s*TJ", st, re.S):
            parts = re.findall(r"\(([^()]*)\)", arr)
            joined = "".join(parts).strip()
            if joined:
                stream_lines.append(joined)

    if stream_lines:
        lines.extend(stream_lines)
    elif not lines and not streams:
        for raw_line in raw.decode("latin1", errors="ignore").splitlines():
            stripped = raw_line.strip()
            if stripped:
                lines.append(stripped)

    return lines


def extract_shipment_from_pdf(pdf_path: Path) -> str | None:
    """
    Extract an 'S'-prefixed shipment number from PLG Costa Rica reference PDF fields
    (SHIPMENT, ORDER NUMBERS / OWNER'S REFERENCE, BILL OF LADING / AIRWAYBIL, INVOICE).
    """
    try:
        lines = extract_text_lines_from_pdf(pdf_path)
        for idx, line in enumerate(lines):
            if _PDF_LABEL_PATTERN.match(line):
                same_line_match = _REF_PATTERN.search(line) or _PDF_S_NUMBER_PATTERN.search(line)
                if same_line_match:
                    val = same_line_match.group(1).strip()
                    logger.info("Extracted PDF shipment=%s (same line) from %s", val, pdf_path)
                    return val
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    if _PDF_LABEL_PATTERN.match(next_line) or _PDF_STOP_LINE_PATTERN.match(next_line):
                        continue
                    next_match = _REF_PATTERN.search(next_line) or _PDF_S_NUMBER_PATTERN.search(next_line)
                    if next_match:
                        val = next_match.group(1).strip()
                        logger.info("Extracted PDF shipment=%s (following line) from %s", val, pdf_path)
                        return val
        return None
    except Exception as exc:
        logger.error("Error extracting shipment from PDF %s: %s", pdf_path, exc)
        return None


def extract_shipment_from_pdfs(dest_dir: Path) -> str | None:
    """Scan all *.pdf files in dest_dir and return the first extracted 'S'-prefixed shipment number."""
    dest_path = Path(dest_dir)
    if not dest_path.exists() or not dest_path.is_dir():
        return None

    for file_path in sorted(dest_path.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() == ".pdf":
            extracted = extract_shipment_from_pdf(file_path)
            if extracted:
                return extracted
    return None


def process_xml_attachments(dest_dir: Path) -> dict[str, Any]:
    """
    Scans the downloaded directory strictly for *.xml files.
    - PDF and non-XML files are ignored here (PDFs are only scanned as shipment fallback).
    - FacturaElectronica root -> Classified as Invoice XML:
        - Extracts <NumeroConsecutivo> (Invoice Number)
        - Extracts <OtroTexto> REF:S... (Shipment Reference fallback)
        - Extracts complete <OtroTexto> text as reference_number if REF keyword is present
    - MensajeHacienda root -> Classified as Hacienda/AHC XML, skips invoice number extraction.
    """
    dest_path = Path(dest_dir)
    if not dest_path.exists() or not dest_path.is_dir():
        logger.error("Download directory does not exist: %s", dest_dir)
        return {
            "invoice_number": None,
            "shipment_reference": None,
            "reference_number": None,
            "invoice_xml": None,
            "ahc_xml": None,
            "xml_files_found": 0,
            "ignored_files": [],
        }

    invoice_number: str | None = None
    shipment_reference: str | None = None
    reference_number: str | None = None
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

            extracted_ref_no = extract_reference_number_from_xml(file_path)
            if extracted_ref_no:
                reference_number = extracted_ref_no
                logger.info("Extracted XML Reference Number=%r from %s", reference_number, file_path.name)
        elif root_name == ROOT_MENSAJE_HACIENDA:
            ahc_xml_path = str(file_path)
            logger.info("Classified as AHC/Hacienda XML (%s); skipped invoice extraction", file_path.name)
        else:
            logger.warning("Unrecognized XML root element <%s> in %s", root_name, file_path.name)

    return {
        "invoice_number": invoice_number,
        "shipment_reference": shipment_reference,
        "reference_number": reference_number,
        "invoice_xml": invoice_xml_path,
        "ahc_xml": ahc_xml_path,
        "xml_files_found": len(xml_files),
        "ignored_files": ignored_files,
    }
