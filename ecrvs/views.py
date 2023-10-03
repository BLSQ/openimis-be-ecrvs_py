import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view

from ecrvs.models import HeraNotification
from ecrvs.services import process_hera_notification

logger = logging.getLogger(__name__)


@api_view(["POST"])
def hera_webhook(request):
    logger.info(f"Hera: new notification received")
    payload = request.data
    status = HeraNotification.determine_status(payload=payload)
    notification = HeraNotification.objects.create(
        status=status,
        operation=payload["operation"],
        context=payload["context"],
        topic=payload["topicName"],
        json_ext=payload,
    )
    if status != HeraNotification.STATUS_INVALID:
        success, message = process_hera_notification(notification)
        if success:
            return JsonResponse({"status": "ok"})

        return JsonResponse({"status": "error", "error_message": message, "data": payload})

    return JsonResponse({
        "status": "error",
        "error_message": "invalid or unknown values for context, operation or topic",
        "data": payload
    })
