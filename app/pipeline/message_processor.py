import logging

logger = logging.getLogger(__name__)


def process_new_message(message_id: str) -> None:
    # TODO: next stage — attachment download, XML parsing, tag extraction, backend calls
    logger.info("Stub process_new_message for message_id=%s", message_id)
