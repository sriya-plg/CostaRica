import json
import logging
from pathlib import Path
from typing import Any

from app.backend.client import report_attachment_details, report_shipment_invoice
from app.core.timezone import local_iso
from app.graph.attachments import get_attachments
from app.graph.messages import get_message_details
from app.persistence.processed_emails import (
    get_processed_email,
    update_processed_email_results,
    update_processed_email_status,
)
from app.pipeline.subject_parser import extract_shipment_number
from app.pipeline.xml_processor import process_xml_attachments
from app.storage.attachments import make_email_download_dir, save_attachment

logger = logging.getLogger(__name__)


def _attachment_meta(attachment: dict[str, Any], saved_path: str) -> dict[str, Any]:
    return {
        "attachment_id": attachment["id"],
        "filename": attachment.get("name"),
        "content_type": attachment.get("contentType"),
        "size": attachment.get("size"),
        "saved_path": saved_path,
    }


def process_new_message(message_id: str) -> None:
    row = get_processed_email(message_id)
    if row is None:
        logger.error("message_id=%s not found in processed_emails", message_id)
        return

    received_at = row["received_at"]

    # Step 1: Fetch message details and parse subject
    subject: str | None = None
    subject_shipment: str | None = None
    try:
        msg_details = get_message_details(message_id)
        subject = msg_details.get("subject")
        subject_shipment = extract_shipment_number(subject)
        logger.info(
            "message_id=%s subject=%r -> parsed subject_shipment=%s",
            message_id,
            subject,
            subject_shipment,
        )
    except Exception as exc:
        logger.warning(
            "Could not fetch message details for message_id=%s from Graph: %s",
            message_id,
            exc,
        )

    # Fetch attachments
    attachments = get_attachments(message_id)
    if not attachments:
        update_processed_email_status(message_id, "no_attachments")
        logger.info("message_id=%s has no file attachments", message_id)
        return

    # Download attachments into timestamped directory
    dest_dir = make_email_download_dir(received_at)
    downloaded = 0
    for attachment in attachments:
        saved_path = save_attachment(attachment, dest_dir)
        report_attachment_details(message_id, _attachment_meta(attachment, str(saved_path)))
        downloaded += 1

    logger.info(
        "message_id=%s downloaded %s attachment(s) to %s",
        message_id,
        downloaded,
        dest_dir,
    )

    # Step 2: Process XML attachments (Invoice & AHC XML, extract NumeroConsecutivo & OtroTexto REF:S...)
    xml_results = process_xml_attachments(dest_dir)
    invoice_number = xml_results.get("invoice_number")
    xml_shipment_ref = xml_results.get("shipment_reference")

    # Determine final Shipment Number:
    # Rule: Check subject first; if it exists and starts with 'S', use it.
    # Otherwise fallback to XML <OtroTexto> REF:S...
    shipment_number: str | None = None
    shipment_source: str = "not_found"

    if subject_shipment and subject_shipment.upper().startswith("S"):
        shipment_number = subject_shipment
        shipment_source = "subject"
    elif xml_shipment_ref and xml_shipment_ref.upper().startswith("S"):
        shipment_number = xml_shipment_ref
        shipment_source = "xml_otro_texto"
    elif subject_shipment:
        # Fallback to subject shipment even if not starting with S if XML had none
        shipment_number = subject_shipment
        shipment_source = "subject_non_s_fallback"

    logger.info(
        "Final resolved shipment_number=%s (source=%s) for message_id=%s",
        shipment_number,
        shipment_source,
        message_id,
    )

    # Print extracted shipment & invoice numbers directly to terminal (ASCII safe for Windows console)
    print("\n" + "=" * 60, flush=True)
    print(" [EXTRACTED SHIPMENT & INVOICE DATA]", flush=True)
    print("=" * 60, flush=True)
    print(f"  - Message ID       : {message_id}", flush=True)
    print(f"  - Email Subject    : {subject}", flush=True)
    print(f"  - Shipment Number  : {shipment_number} (Source: {shipment_source})", flush=True)
    print(f"  - Invoice Number   : {invoice_number} (from <NumeroConsecutivo>)", flush=True)
    print(f"  - Invoice XML Path : {xml_results.get('invoice_xml')}", flush=True)
    print(f"  - AHC XML Path     : {xml_results.get('ahc_xml')}", flush=True)
    print(f"  - Download Folder  : {dest_dir}", flush=True)
    print("=" * 60 + "\n", flush=True)

    # Assemble structured JSON result
    result_payload = {
        "message_id": message_id,
        "subject": subject,
        "shipment_number": shipment_number,
        "shipment_source": shipment_source,
        "invoice_number": invoice_number,
        "invoice_xml": xml_results.get("invoice_xml"),
        "ahc_xml": xml_results.get("ahc_xml"),
        "download_directory": str(dest_dir),
        "xml_files_found": xml_results.get("xml_files_found", 0),
        "ignored_files": xml_results.get("ignored_files", []),
        "processed_at": local_iso(),
    }

    # Save result.json in the downloaded folder
    result_json_file = Path(dest_dir) / "result.json"
    result_json_file.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    logger.info("Saved extraction result to %s", result_json_file)

    # Update SQLite database
    update_processed_email_results(
        message_id=message_id,
        status="processed",
        subject=subject,
        shipment_number=shipment_number,
        invoice_number=invoice_number,
        result_data=result_payload,
    )

    # Dispatch to backend client
    report_shipment_invoice(result_payload)
