import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view

from ecrvs.models import HeraNotification
from ecrvs.services import process_hera_notification
from ecrvs.exception import HeraNotificationException

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
        try:
            process_hera_notification(notification)
            notification.set_processed()
            return JsonResponse({"status": "ok", "code": 200})
        except HeraNotificationException as e:
            notification.set_status(HeraNotification.STATUS_PROCESSED_ERROR)
            logger.exception("Known error while processing Hera notification on the webhook")
            return JsonResponse({"status": "error", "message": str(e), "data": payload, "code": 400})
        except Exception as e:
            notification.set_status(HeraNotification.STATUS_PROCESSED_ERROR)
            logger.exception("Unknown error while processing Hera notification on the webhook")
            return JsonResponse({"status": "error", "message": str(e), "data": payload, "code": 500})

    logger.error(f"Hera: received invalid notification - unknown value for context, operation or topic")
    return JsonResponse({
        "status": "error",
        "message": "invalid or unknown values for context, operation or topic",
        "data": payload,
        "code": 400,
    })
