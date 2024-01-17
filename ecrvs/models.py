import datetime
import os
import logging
from threading import Lock

import requests
from django.conf import settings
from django.db import models
from datetime import datetime as py_datetime

import core.models
from core.models import ExtendableModel, ObjectMutation
from ecrvs.exception import HeraNotificationException, HeraSubscriptionException, HeraSetupException
from location.models import Location, HealthFacility

logger = logging.getLogger(__name__)


class HeraMapping(models.Model):
    id = models.AutoField(db_column="ID", primary_key=True)
    hera_code = models.CharField(db_column="HeraCode", unique=True, max_length=255)
    created_at = models.DateTimeField(db_column='CreatedAt', default=py_datetime.now)
    last_access = models.DateTimeField(db_column='LastAccess', default=py_datetime.now)
    is_instance_deleted = models.BooleanField(db_column='IsDeleted', default=False)

    class Meta:
        abstract = True


class HeraLocationIDsMapping(HeraMapping):
    openimis_location = models.ForeignKey(Location, models.DO_NOTHING,
                                          db_column='OpenIMISID')
    location_type = models.CharField(db_column='LocationType', max_length=1)

    class Meta:
        managed = True
        db_table = "tblHeraLocationIDsMapping"

    def delete_location(self):
        self.openimis_location.delete_history()
        self.is_instance_deleted = True
        self.save()


class HeraHFIDsMapping(HeraMapping):
    openimis_hf = models.ForeignKey(HealthFacility, models.DO_NOTHING,
                                    db_column='OpenIMISID')

    class Meta:
        managed = True
        db_table = "tblHeraHFIDsMapping"

    def delete_hf(self):
        self.openimis_hf.delete_history()
        self.is_instance_deleted = True
        self.save()


class HeraNotification(ExtendableModel):
    id = models.AutoField(db_column="ID", primary_key=True)
    topic = models.CharField(db_column="Topic", max_length=255)
    operation = models.CharField(db_column="Operation", max_length=255)
    datetime_received = models.DateTimeField(db_column="ReceivedAt", default=py_datetime.now)
    context = models.CharField(db_column="Context", max_length=255)
    status = models.CharField(db_column="Status", max_length=255)
    datetime_processed = models.DateTimeField(db_column="ProcessedAt", blank=True, null=True)

    class Meta:
        managed = True
        db_table = "tblHeraNotification"

    OPERATION_CREATE = "CREATE"
    OPERATION_UPDATE = "UPDATE"
    OPERATION_DELETE = "DELETE"
    AVAILABLE_OPERATIONS = [
        OPERATION_CREATE,
        OPERATION_UPDATE,
        OPERATION_DELETE
    ]

    @property
    def operations(self):
        return self.AVAILABLE_OPERATIONS

    TOPIC_LIFE_EVENT = "LifeEventTopic"
    TOPIC_LOCATION_EVENT = "LocationEventTopic"
    AVAILABLE_TOPICS = [
        TOPIC_LIFE_EVENT,
        TOPIC_LOCATION_EVENT
    ]

    @property
    def topics(self):
        return self.AVAILABLE_TOPICS

    CONTEXT_BIRTH_CREATED = "BIRTH_REGISTRATION_CREATED"
    CONTEXT_HF_CREATED = "HEALTH_FACILITY_CREATED"
    CONTEXT_HF_UPDATED = "HEALTH_FACILITY_UPDATED"
    CONTEXT_HF_DELETED = "HEALTH_FACILITY_DELETED"
    CONTEXT_PROVINCE_CREATED = "PROVINCE_CREATED"
    CONTEXT_PROVINCE_UPDATED = "PROVINCE_UPDATED"
    CONTEXT_PROVINCE_DELETED = "PROVINCE_DELETED"
    CONTEXT_DISTRICT_CREATED = "DISTRICT_CREATED"
    CONTEXT_DISTRICT_UPDATED = "DISTRICT_UPDATED"
    CONTEXT_DISTRICT_DELETED = "DISTRICT_DELETED"
    CONTEXT_PLACE_CREATED = "PLACE_CREATED"
    CONTEXT_PLACE_UPDATED = "PLACE_UPDATED"
    CONTEXT_PLACE_DELETED = "PLACE_DELETED"
    AVAILABLE_CONTEXTS = [
        CONTEXT_BIRTH_CREATED,
        CONTEXT_HF_CREATED,
        CONTEXT_HF_UPDATED,
        CONTEXT_HF_DELETED,
        CONTEXT_PROVINCE_CREATED,
        CONTEXT_PROVINCE_UPDATED,
        CONTEXT_PROVINCE_DELETED,
        CONTEXT_DISTRICT_CREATED,
        CONTEXT_DISTRICT_UPDATED,
        CONTEXT_DISTRICT_DELETED,
        CONTEXT_PLACE_CREATED,
        CONTEXT_PLACE_UPDATED,
        CONTEXT_PLACE_DELETED,
    ]

    @property
    def contexts(self):
        return self.AVAILABLE_CONTEXTS

    STATUS_RECEIVED = "RECEIVED"
    STATUS_PROCESSED_SUCCESS = "SUCCESS"
    STATUS_PROCESSED_ERROR = "ERROR"
    STATUS_INVALID = "INVALID"
    AVAILABLE_STATUSES = [
        STATUS_RECEIVED,
        STATUS_PROCESSED_SUCCESS,
        STATUS_PROCESSED_ERROR,
        STATUS_INVALID,
    ]

    @property
    def statuses(self):
        return self.AVAILABLE_STATUSES

    @classmethod
    def determine_status(cls, payload):
        status = cls.STATUS_RECEIVED
        if (payload["topicName"] not in cls.AVAILABLE_TOPICS
                or payload["operation"] not in cls.AVAILABLE_OPERATIONS
                or payload["context"] not in cls.AVAILABLE_CONTEXTS):
            status = cls.STATUS_INVALID
        return status

    def set_status(self, new_status):
        if new_status not in self.AVAILABLE_STATUSES:
            raise ValueError(f"Invalid status ({new_status})")
        self.status = new_status
        self.save()

    def set_processed(self):
        self.status = self.STATUS_PROCESSED_SUCCESS
        self.datetime_processed = py_datetime.now()
        self.save()


class HeraSubscription(ExtendableModel):
    uuid = models.UUIDField(db_column="UUID", primary_key=True, editable=False)
    topic = models.CharField(db_column="Topic", max_length=255)
    created_at = models.DateTimeField(db_column="CreatedAt", default=py_datetime.now)
    created_by = models.IntegerField(db_column='CreatedBy')
    active = models.BooleanField(db_column="IsActive", default=True)
    deleted_at = models.DateTimeField(db_column="DeletedAt", null=True, blank=True)
    deleted_by = models.IntegerField(db_column='DeletedBy', null=True, blank=True)

    class Meta:
        managed = True
        db_table = "tblHeraSubscription"

    @property
    def id(self):
        return self.uuid

    def cancel(self, user_id: int):
        self.active = False
        self.deleted_by = user_id
        self.deleted_at = py_datetime.now()
        self.save()


class SingletonMeta(type):
    """
    This is a thread-safe implementation of Singleton.
    https://refactoring.guru/design-patterns/singleton/python/example
    """

    _instances = {}

    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class HeraInstance(metaclass=SingletonMeta):
    hera_login_secret = ""
    webhook_address = ""
    post_login_url = ""
    subscriptions_url = ""
    get_persons_url = ""
    hera_token = ""
    fetch_insuree_fields = []
    token_expiry_timestamp = None

    def __init__(self) -> None:
        base_hera_login_url = os.environ.get('HERA_LOGIN_URL', False)
        if not base_hera_login_url:
            raise HeraSetupException("The HERA_LOGIN_URL ENV variable is not set")
        base_hera_data_url = os.environ.get('HERA_DATA_URL', False)
        if not base_hera_data_url:
            raise HeraSetupException("The HERA_DATA_URL ENV variable is not set")
        hera_login_secret = os.environ.get('HERA_LOGIN_SECRET', False)
        if not hera_login_secret:
            raise HeraSetupException("The HERA_LOGIN_SECRET ENV variable is not set")
        webhook_address = os.environ.get('HERA_WEBHOOK_ADDRESS', False)
        if not webhook_address:
            raise HeraSetupException("The HERA_WEBHOOK_ADDRESS ENV variable is not set")

        self.post_login_url = f"{base_hera_login_url}/realms/Hera/protocol/openid-connect/token"
        self.subscriptions_url = f"{base_hera_data_url}/v1/subscriptions"
        self.get_persons_url = f"{base_hera_data_url}/v1/persons"
        self.hera_login_secret = hera_login_secret
        self.webhook_address = webhook_address
        self.fetch_insuree_fields = settings.HERA_INSUREE_FIELDS_TO_FETCH

    def _get_token(self) -> None:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data_urlencode = {
            "client_id": "hera-m2m",
            "client_secret": self.hera_login_secret,
            "grant_type": "client_credentials",
        }
        logger.info("Hera: fetching token")

        response = requests.post(self.post_login_url, headers=headers, data=data_urlencode)
        if not response.ok:
            raise HeraNotificationException(f"Hera: error with token fetching - {response.text}")

        data = response.json()
        if "access_token" not in data:
            raise HeraNotificationException(f"Hera: no token received - {data['error']} - {data['error_description']}")

        self.hera_token = data["access_token"]
        self.token_expiry_timestamp = datetime.datetime.now() + datetime.timedelta(seconds=data["expires_in"])
        logger.info("Hera: token successfully fetched")

    def _prepare_data_headers(self) -> dict:
        if not self.hera_token or self.token_expiry_timestamp < datetime.datetime.now():
            self._get_token()

        headers = {
            "Authorization": f"Bearer {self.hera_token}"
        }
        return headers

    def _build_insuree_fields_to_fetch_query(self) -> str:
        query = ""
        for field in self.fetch_insuree_fields:
            query += f"attributeNames={field}&"
        query = query[:-1]
        return query

    def subscribe(self, topic: str) -> dict:
        if topic not in HeraNotification.AVAILABLE_TOPICS:
            raise ValueError("Invalid topic - can't subscribe")
        logger.info(f"Hera: trying to subscribe to {topic}")
        headers = self._prepare_data_headers()
        url = f"{self.subscriptions_url}?topic={topic}&address={self.webhook_address}&policy=3600%2C-1"
        response = requests.post(url, headers=headers)

        if not response.ok:
            raise HeraSubscriptionException(f"Hera: couldn't subscribe to {topic} - {response.text}")

        data = response.json()
        logger.info(f"Hera: successfully subscribed to {topic}")
        return data

    def fetch_insuree_data_from_nin(self, nin) -> dict:
        # check NIN format ?
        logger.info(f"Hera: trying to fetch insuree data for {nin}")
        headers = self._prepare_data_headers()
        fields_to_fetch = self._build_insuree_fields_to_fetch_query()
        url = f"{self.get_persons_url}/{nin}?{fields_to_fetch}"
        response = requests.get(url, headers=headers)

        if not response.ok:
            raise HeraNotificationException(f"Hera: couldn't fetch insuree data (nin {nin}) - response: {response.text}")

        data = response.json()
        logger.info(f"Hera: successfully fetched insuree data for {nin}")
        return data

    def unsubscribe(self, subscription: HeraSubscription) -> bool:
        logger.info(f"Hera: unsubscribing from {subscription.topic} - {subscription.uuid}")
        headers = self._prepare_data_headers()
        url = f"{self.subscriptions_url}/{subscription.uuid}"
        response = requests.delete(url, headers=headers)

        if not response.ok:
            raise HeraSubscriptionException(f"Hera: couldn't unsubscribe from {subscription.uuid} - {response.text}")

        logger.info(f"Hera: successfully unsubscribed from {subscription.uuid}")
        return True


class HeraSubscriptionMutation(core.models.UUIDModel, ObjectMutation):
    hera_subscription = models.ForeignKey(HeraSubscription, models.DO_NOTHING, related_name="mutations")
    mutation = models.ForeignKey(core.models.MutationLog, models.DO_NOTHING, related_name="hera_subscriptions")

    class Meta:
        managed = True
        db_table = "ecrvs_HeraSubscriptionMutation"
