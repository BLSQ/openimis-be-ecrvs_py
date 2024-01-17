from django.urls import path

from ecrvs import views

HERA_WEBHOOK_PATH = "webhooks/hera"

urlpatterns = [
    path(HERA_WEBHOOK_PATH, views.hera_webhook),
    path(HERA_WEBHOOK_PATH + "/", views.hera_webhook),  # hotfix for Hera adding a / for some reason
]
