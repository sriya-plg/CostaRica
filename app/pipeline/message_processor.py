import json
import logging
from pathlib import Path
from typing import Any

from app.backend.client import (
    core_data_client,
    report_attachment_details,
    report_shipment_invoice,
)
from app.core.config import settings
from app.core.timezone import local_iso
from app.graph.attachments import get_attachments
from app.graph.messages import get_message_details
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


def process_new_message(message_id: str, received_at: str | None = None) -> dict[str, Any]:
    """Process an email: log to Core Data, retrieve attachment list, download attachments, parse XMLs, add activity, and dispatch to backend."""
    timestamp = received_at or local_iso()

    # Step 1: Fetch message details and parse subject
    subject: str | None = None
    subject_shipment: str | None = None
    sender_email: str = ""
    body_preview: str = ""
    received_datetime: str = timestamp
    msg_details: dict[str, Any] = {}

    try:
        msg_details = get_message_details(message_id)
        subject = msg_details.get("subject")
        subject_shipment = extract_shipment_number(subject)
        sender_info = msg_details.get("from")
        if isinstance(sender_info, dict):
            sender_email = sender_info.get("emailAddress", {}).get("address", "")
        body_preview = msg_details.get("bodyPreview") or ""
        received_datetime = msg_details.get("receivedDateTime") or timestamp

        logger.info(
            "message_id=%s sender=%s subject=%r -> parsed subject_shipment=%s",
            message_id,
            sender_email,
            subject,
            subject_shipment,
        )
    except Exception as exc:
        logger.warning(
            "Could not fetch message details for message_id=%s from Graph: %s",
            message_id,
            exc,
        )

    # Fetch attachments from Graph
    attachments = get_attachments(message_id)
    if not attachments:
        logger.info("message_id=%s has no file attachments", message_id)
        return {}

    attachment_filenames = [att.get("name") for att in attachments if att.get("name")]

    # --- Core Data API 1: Add Email Log ---
    email_log_id = core_data_client.add_email_log(
        email=sender_email,
        email_subject=subject or "",
        email_body=body_preview,
        email_received_on=received_datetime,
        attachment_filenames=attachment_filenames,
    )
    logger.info("message_id=%s -> Core Data emailLogId=%s", message_id, email_log_id)

    # --- Core Data API 2: Get Attachment List ---
    core_data_attachments: list[dict[str, Any]] = []
    if email_log_id is not None:
        core_data_attachments = core_data_client.get_attachment_list(email_log_id)
        logger.info(
            "emailLogId=%s returned %d attachment(s) from Core Data",
            email_log_id,
            len(core_data_attachments),
        )

    # Download attachments into timestamped directory
    dest_dir = make_email_download_dir(timestamp)
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
        shipment_number = subject_shipment
        shipment_source = "subject_non_s_fallback"

    logger.info(
        "Final resolved shipment_number=%s (source=%s) for message_id=%s",
        shipment_number,
        shipment_source,
        message_id,
    )

    # --- Core Data API 3: Add Activity ---
    activities_created: list[dict[str, Any]] = []
    if email_log_id is not None and core_data_attachments:
        for cd_att in core_data_attachments:
            att_id = cd_att.get("attachmentId")
            if att_id is not None:
                act_resp = core_data_client.add_activity(
                    email_log_id=email_log_id,
                    attachment_id=int(att_id),
                    bill_to=settings.CORE_DATA_BILL_TO,
                )
                activities_created.append({
                    "attachmentId": att_id,
                    "fileName": cd_att.get("fileName"),
                    "activityResponse": act_resp,
                })

    # Print formatted extraction summary card to terminal
    print("\n" + "=" * 65, flush=True)
    print("  ORDER DATA EXTRACTED (Cardtronics Costa Rica)", flush=True)
    print("=" * 65, flush=True)
    print(f"  Email Subject       : {subject}", flush=True)
    print(f"  Core Data EmailLogId: {email_log_id}", flush=True)
    print(f"  Shipment Number     : {shipment_number} (source: {shipment_source})", flush=True)
    print(f"  Invoice Number      : {invoice_number} (from <NumeroConsecutivo>)", flush=True)
    print(f"  Invoice XML         : {xml_results.get('invoice_xml')}", flush=True)
    print(f"  AHC XML             : {xml_results.get('ahc_xml')}", flush=True)
    print(f"  Downloads Folder    : {dest_dir}", flush=True)
    print(f"  Activities Created  : {len(activities_created)}", flush=True)
    print("=" * 65 + "\n", flush=True)

    # Assemble structured JSON result
    result_payload = {
        "message_id": message_id,
        "email_log_id": email_log_id,
        "core_data_attachments": core_data_attachments,
        "activities_created": activities_created,
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

    # Dispatch to backend client
    report_shipment_invoice(result_payload)
    return result_payload
