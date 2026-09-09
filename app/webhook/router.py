import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import PlainTextResponse

from app.webhook.notifications import handle_notification

logger = logging.getLogger(__name__)

router = APIRouter()


def _validation_response(validation_token: str) -> PlainTextResponse:
    return PlainTextResponse(content=validation_token, status_code=200)


@router.get("/webhook")
async def validate_webhook(validationToken: str) -> PlainTextResponse:
    return _validation_response(validationToken)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    # Graph validates subscriptions via POST with validationToken in the query string.
    validation_token = request.query_params.get("validationToken")
    if validation_token is not None:
        return _validation_response(validation_token)

    body = await request.json()
    notifications = body.get("value", [])
    if not isinstance(notifications, list):
        logger.warning("Webhook POST body missing value array")
        return Response(status_code=202)

    for notification in notifications:
        background_tasks.add_task(handle_notification, notification)

    return Response(status_code=202)
