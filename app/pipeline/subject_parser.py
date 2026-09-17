import logging
import re

logger = logging.getLogger(__name__)

# Matches "Shipment N°: PGAA00307692", "Shipment No: 50276", "Shipment #: 50277", "Shipment: 50293", "SHIPMENT NUMBER: 998877", etc.
_SHIPMENT_PATTERN = re.compile(
    r"(?i)\bshipment\s*(?:number\b|num\b|no\b|n[°ºo\.]+|#)?\s*[:\s-]*\s*([A-Za-z0-9_\-]+)",
    re.UNICODE,
)


def extract_shipment_number(subject: str | None) -> str | None:
    """
    Extracts the shipment number strictly from the email subject.

    Examples:
        'Shipment N°: PGAA00307692' -> 'PGAA00307692'
        'Shipment No: 50276'         -> '50276'
        'Shipment #: 50277'          -> '50277'
        'Shipment 50293'             -> '50293'
        'Shipment: PGAA00307692'     -> 'PGAA00307692'
        'SHIPMENT NUMBER: 998877'    -> '998877'

    Returns None if no shipment number could be found.
    """
    if not subject:
        logger.warning("Empty or None subject provided for shipment extraction")
        return None

    cleaned_subject = subject.strip()
    match = _SHIPMENT_PATTERN.search(cleaned_subject)
    if match:
        shipment_no = match.group(1).strip()
        logger.info("Extracted shipment_number=%s from subject=%r", shipment_no, cleaned_subject)
        return shipment_no

    logger.warning("Could not extract shipment number from subject=%r", cleaned_subject)
    return None
