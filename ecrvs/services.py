import logging

from django.db.models import Q
from django.utils.translation import gettext as _

from autoenroll.services import autoenroll_family
from core.models import InteractiveUser
from ecrvs.models import HeraLocationIDsMapping, HeraNotification, HeraInstance, HeraHFIDsMapping, HeraSubscription
from ecrvs.exception import HeraNotificationException
from insuree.models import Family, Insuree, Profession, Gender
from location.models import Location, HealthFacility, HealthFacilityLegalForm, UserDistrict

logger = logging.getLogger(__name__)

CONTEXT_DISTRICT_START = "PROVINCE"
CONTEXT_WARD_START = "DISTRICT"
CONTEXT_VILLAGE_START = "PLACE"
CONTEXT_HF_START = "HEALTH_FACILITY"

LOCATION_TYPE_REGION = "R"
LOCATION_TYPE_DISTRICT = "D"
LOCATION_TYPE_WARD = "W"
LOCATION_TYPE_VILLAGE = "V"

HF_TYPE_COMMUNITY_CLINIC = "Community Clinic"
HF_TYPE_COMMUNITY_CLINIC_2 = "Commmunity Clinic"  # Yes, some entries have this spelling
HF_TYPE_HOSPITAL = "Hospital"
HF_TYPE_MAJ_CENTER = "Major Health Centre"
HF_TYPE_MIN_CENTER = "Minor Health Centre"
HF_TYPE_VILLAGE_OPD = "Village OPD"
HF_TYPE_HEALTH_POST = "Health Post"
AVAILABLE_HF_TYPES = [
    HF_TYPE_COMMUNITY_CLINIC,
    HF_TYPE_COMMUNITY_CLINIC_2,
    HF_TYPE_HOSPITAL,
    HF_TYPE_MAJ_CENTER,
    HF_TYPE_MIN_CENTER,
    HF_TYPE_VILLAGE_OPD,
    HF_TYPE_HEALTH_POST,
]

HF_LEVELS_MAPPING = {
    HF_TYPE_HEALTH_POST: HealthFacility.LEVEL_DISPENSARY,
    HF_TYPE_COMMUNITY_CLINIC: HealthFacility.LEVEL_DISPENSARY,
    HF_TYPE_COMMUNITY_CLINIC_2: HealthFacility.LEVEL_DISPENSARY,
    HF_TYPE_VILLAGE_OPD: HealthFacility.LEVEL_DISPENSARY,
    HF_TYPE_MIN_CENTER: HealthFacility.LEVEL_HEALTH_CENTER,
    HF_TYPE_MAJ_CENTER: HealthFacility.LEVEL_HEALTH_CENTER,
    HF_TYPE_HOSPITAL: HealthFacility.LEVEL_HOSPITAL,
}

DEFAULT_AUDIT_USER_ID = -1

HERA_GENDER_MALE = "SEX::MALE"
HERA_GENDER_FEMALE = "SEX::FEMALE"
UNKNOWN_GENDER = "UNKNOWN"

GENDER_MAPPING = {
    HERA_GENDER_MALE: Gender.objects.get(code='M'),
    HERA_GENDER_FEMALE: Gender.objects.get(code='F'),
    UNKNOWN_GENDER: Gender.objects.get(code='O'),
}


def get_hera_location_mapping_by_hera_code(hera_code: str, location_type: str = None):
    filters = Q(hera_code=hera_code) & Q(is_instance_deleted=False)
    if location_type:
        filters &= Q(location_type=location_type)

    mapping = HeraLocationIDsMapping.objects.filter(filters).first()
    if mapping:
        from core import datetime
        mapping.last_access = datetime.datetime.now()
        mapping.save()

    return mapping


def get_hera_hf_mapping_by_hera_code(hera_code: str):
    filters = Q(hera_code=hera_code) & Q(is_instance_deleted=False)
    mapping = HeraHFIDsMapping.objects.filter(filters).first()
    if mapping:
        from core import datetime
        mapping.last_access = datetime.datetime.now()
        mapping.save()

    return mapping


def fetch_insuree_occupation_from_payload(hera_occupation: str):
    return Profession.objects.filter(profession=hera_occupation).first()


def convert_str_date_to_python_date(date_str: str):
    from core import datetime
    python_datetime = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return python_datetime.date()


def process_existing_insuree(insuree: Insuree, new_data: dict, nin: str):
    # Here, we should theoretically check if the received NIN:
    # - has the right format
    # - has the right length
    # But the data in Hera is poor (bad format, sometimes no NIN...),
    # so we shouldn't do that for the moment (January 2024)
    logger.info(f"Hera: there already is an insuree with the received nin ({nin}) - insuree ID {insuree.id}")
    logger.info(f"Hera: updating insuree")

    from core import datetime
    insuree.save_history()
    insuree.other_names = new_data["firstName"]
    insuree.last_name = new_data["lastName"]
    insuree.phone = new_data["mobileNumber"]
    insuree.dob = convert_str_date_to_python_date(new_data["dob"])
    insuree.json_ext = new_data
    insuree.profession = fetch_insuree_occupation_from_payload(new_data["occupation"])
    insuree.gender = GENDER_MAPPING.get(new_data["gender"], GENDER_MAPPING[UNKNOWN_GENDER])
    insuree.audit_user_id = DEFAULT_AUDIT_USER_ID
    insuree.validity_from = datetime.datetime.now()
    insuree.save()

    logger.info(f"Hera: insuree {insuree.id} successfully updated")


def process_new_insuree(insuree_data: dict, nin: str):
    # Here, we should theoretically check if the received NIN:
    # - has the right format
    # - has the right length
    # But the data in Hera is poor (bad format, sometimes no NIN...),
    # so we shouldn't do that for the moment (January 2024)
    logger.info("Hera: processing new insuree query")

    # get village from payload
    village_hera_code = insuree_data["residentialVillage"] if insuree_data["residentialVillage"] else insuree_data["registrationVillage"]
    village_mapping = get_hera_location_mapping_by_hera_code(village_hera_code, LOCATION_TYPE_VILLAGE)
    if not village_mapping:
        # instead of triggering an error, we could place the family in an "unknown village", based on the LGA?
        # Let's discuss this
        raise HeraNotificationException(f"Hera: can't find village with Hera code {village_hera_code}")

    logger.info(f"Hera: creating new family")
    new_family = Family.objects.create(
        audit_user_id=DEFAULT_AUDIT_USER_ID,
        head_insuree_id=1,  # dummy
        location=village_mapping.openimis_location,
    )

    logger.info(f"Hera: creating the new insuree")
    # add email field to the insuree, once it's available on Hera
    new_insuree = Insuree.objects.create(
        chf_id=nin,
        other_names=insuree_data["firstName"],
        last_name=insuree_data["lastName"],
        phone=insuree_data["mobileNumber"],
        dob=convert_str_date_to_python_date(insuree_data["dob"]),
        json_ext=insuree_data,
        profession=fetch_insuree_occupation_from_payload(insuree_data["occupation"]),
        gender=GENDER_MAPPING.get(insuree_data["gender"], GENDER_MAPPING[UNKNOWN_GENDER]),
        audit_user_id=DEFAULT_AUDIT_USER_ID,
        head=True,
        card_issued=True,
    )

    # Now placing the correct insuree into the family
    new_family.head_insuree = new_insuree
    new_family.save()

    logger.info(f"Hera: autoenrolling the new insuree (if applicable)")
    autoenroll_family(new_insuree, new_family)

    logger.info(f"Hera: insuree successfully created")


def process_life_event_notification(notification: HeraNotification):
    logger.info(f"Hera: LifeEvent notification")
    nin = notification.json_ext["nin"]
    context = notification.context

    hera_instance = HeraInstance()
    insuree_data = hera_instance.fetch_insuree_data_from_nin(nin)

    if context == HeraNotification.CONTEXT_BIRTH_CREATED:
        logger.info(f"Hera: starting to process LifeEvent notification")

        existing_insuree = Insuree.objects.filter(validity_to__isnull=True, chf_id=nin).first()
        if existing_insuree:
            process_existing_insuree(existing_insuree, insuree_data, nin)
        else:
            process_new_insuree(insuree_data, nin)

        logger.info(f"Hera: LifeEvent notification successfully processed")
    else:
        raise HeraNotificationException(f"Hera: unknown context: {context} (notification id ={notification.id})")


def get_object_name_from_hera_payload(payload: dict):
    for language in payload["location"]["locationValueList"]:
        if language["langCode"] == "ENGLISH":
            return language.get("newValue", "")


def get_location_type_from_payload(payload: dict):
    context = payload["context"]
    if context.startswith(CONTEXT_DISTRICT_START):
        return LOCATION_TYPE_DISTRICT
    elif context.startswith(CONTEXT_WARD_START):
        return LOCATION_TYPE_WARD
    elif context.startswith(CONTEXT_VILLAGE_START):
        return LOCATION_TYPE_VILLAGE
    return None


def create_location(data: dict, location_type: str, hera_code: str):
    logger.info(f"Hera: creating new location")

    # should we handle the case of deleted location that we try to recreate with the same code?
    # this crashes because the hera_code has unique=True -> IntegrityError when recreating

    # check if parent exists
    if location_type == LOCATION_TYPE_DISTRICT:
        parent_location = Location.objects.filter(validity_to__isnull=True, type=LOCATION_TYPE_REGION, name="The Gambia").first()
        if not parent_location:
            raise HeraNotificationException(f"can't find the Gambia region")

    else:
        parent_code = data["location"]["location"]["locationCode"]
        parent_mapping = get_hera_location_mapping_by_hera_code(parent_code)
        if not parent_mapping:
            raise HeraNotificationException(f"no known parent location (parent Hera code={parent_code}, "
                                            f"Hera code={hera_code})")
        parent_location = parent_mapping.openimis_location

    location = Location.objects.create(
        name=get_object_name_from_hera_payload(data),
        audit_user_id=DEFAULT_AUDIT_USER_ID,
        parent=parent_location,
        type=location_type,
    )

    logger.info(f"Hera: creating new mapping")
    mapping = HeraLocationIDsMapping.objects.create(
        hera_code=hera_code,
        openimis_location=location,
        location_type=location_type
    )

    location.code = f"HERA{mapping.id}"
    location.save()
    logger.info(f"Hera: location mapping created successfully")

    if location_type == LOCATION_TYPE_DISTRICT:
        logger.info(f"Hera: adding new district to the Admin")
        admin = InteractiveUser.objects.filter(validity_to__isnull=True, id=1).first()
        UserDistrict.objects.create(
            user=admin,
            location=location,
            audit_user_id=DEFAULT_AUDIT_USER_ID,
        )

    logger.info(f"Hera: location successfully created")


def update_location(location: Location, data: dict, location_type: str, hera_code: str):
    logger.info(f"Hera: updating location")

    if location_type == LOCATION_TYPE_DISTRICT:
        parent_location = Location.objects.filter(validity_to__isnull=True, type=LOCATION_TYPE_REGION, name="The Gambia").first()
        if not parent_location:
            raise HeraNotificationException(f"can't find the Gambia region")

    else:
        # check if parent exists
        parent_code = data["location"]["location"]["locationCode"]
        parent_mapping = get_hera_location_mapping_by_hera_code(parent_code)
        if not parent_mapping:
            raise HeraNotificationException(f"no known parent location (Hera code={hera_code}, "
                                            f"Hera parent code={parent_code})")
        parent_location = parent_mapping.openimis_location

        # check if parents are on the same level
        previous_parent_type = location.parent.type
        new_parent_type = parent_mapping.openimis_location.type
        if previous_parent_type != new_parent_type:
            raise HeraNotificationException(f"illegal move to other level in the pyramid - "
                                            f"initial parent={previous_parent_type} new parent={new_parent_type} "
                                            f"(Hera code={hera_code})")

    # check if same level
    previous_type = location.type
    if previous_type != location_type:
        raise HeraNotificationException(f"location type changed - previous={previous_type} new={location_type} "
                                        f"(Hera code={location.code})")

    # if all of this is ok, update
    from core import datetime
    location.save_history()
    location.name = get_object_name_from_hera_payload(data)
    location.validity_from = datetime.datetime.now()
    location.audit_user_id = DEFAULT_AUDIT_USER_ID
    location.parent = parent_location
    location.save()
    logger.info(f"Hera: location successfully updated")


def delete_location(mapping: HeraLocationIDsMapping):
    logger.info(f"Hera: deleting location")
    # Maybe there should be something in Location in order to cleanly delete a location
    # for instance, decide what to do with children locations, with families, Hfs...
    # This simply deleted the current location and leaves all the rest as it is.
    mapping.delete_location()
    logger.info(f"Hera: location successfully deleted")


def convert_location_context_to_type(context: str):
    if context.startswith(CONTEXT_DISTRICT_START):
        return LOCATION_TYPE_DISTRICT
    elif context.startswith(CONTEXT_WARD_START):
        return LOCATION_TYPE_WARD
    elif context.startswith(CONTEXT_VILLAGE_START):
        return LOCATION_TYPE_VILLAGE
    else:
        raise HeraNotificationException(f"Hera: unknown context - {context}")


def process_location_initial_load(data: dict, context: str, operation: str):
    logger.info(f"Hera: received location notification")
    location_type = convert_location_context_to_type(context)
    hera_code = data["location"]["locationCode"]
    location_mapping = get_hera_location_mapping_by_hera_code(hera_code, location_type=location_type)

    if operation == HeraNotification.OPERATION_CREATE or operation == HeraNotification.OPERATION_UPDATE:
        if not location_mapping:
            logger.info(f"Hera: creating initial load location with operation={operation}")
            create_location(data, location_type, hera_code)
        else:
            update_location(location_mapping.openimis_location, data, location_type, hera_code)
    elif operation == HeraNotification.OPERATION_DELETE:
        if location_mapping:
            delete_location(location_mapping)
            raise HeraNotificationException(f"can't delete location - it doesn't exist (Hera code={hera_code})")
    else:
        raise HeraNotificationException(f"unknown operation ({operation})")


def process_hf_initial_load(data: dict, operation: str):
    logger.info(f"Hera: received hf notification")
    hera_hf_code = data["location"]["locationCode"]
    hf_mapping = get_hera_hf_mapping_by_hera_code(hera_hf_code)

    if operation == HeraNotification.OPERATION_CREATE or operation == HeraNotification.OPERATION_UPDATE:

        # Checking if the HF type exists
        hf_type = data["location"]["type"]
        if hf_type not in AVAILABLE_HF_TYPES:
            raise HeraNotificationException(f"unknown type - {hf_type} (Hera code={hera_hf_code})")

        # Checking if the district exists
        hera_district_code = data["location"]["location"]["location"]["location"]["locationCode"]
        district_mapping = get_hera_location_mapping_by_hera_code(hera_district_code,
                                                                  location_type=LOCATION_TYPE_DISTRICT)
        if not district_mapping:
            raise HeraNotificationException(f"unknown district (district Hera code={hera_district_code}, "
                                            f"Hera hf code={hera_hf_code})")

        if not hf_mapping:
            logger.info(f"Hera: creating initial load hf with operation={operation}")
            create_hf(data, district_mapping.openimis_location, hera_hf_code, hf_type)
        else:
            update_hf(data, hf_mapping.openimis_hf, district_mapping.openimis_location, hf_type)
    elif operation == HeraNotification.OPERATION_DELETE:
        if hf_mapping:
            delete_hf(hf_mapping)
            raise HeraNotificationException(f"can't delete hf - it doesn't exist (Hera code={hera_hf_code})")
    else:
        raise HeraNotificationException(f"unknown operation ({operation})")


def process_location_event(data: dict, location_type: str, operation: str):
    hera_code = data["location"]["locationCode"]
    location_mapping = get_hera_location_mapping_by_hera_code(hera_code, location_type=location_type)

    if not location_mapping:
        if operation == HeraNotification.OPERATION_CREATE:
            create_location(data, location_type, hera_code)
        else:
            raise HeraNotificationException(f"unknown location (Hera code={hera_code}, operation={operation})")

    else:
        if operation == HeraNotification.OPERATION_UPDATE:
            update_location(location_mapping.openimis_location, data, location_type, hera_code)
        elif operation == HeraNotification.OPERATION_DELETE:
            delete_location(location_mapping)
        elif operation == HeraNotification.OPERATION_CREATE:
            raise HeraNotificationException(f"location already exists with a mapping, "
                                            f"can't create it again (Hera code={hera_code})")
        else:
            raise HeraNotificationException(f"unknown case, shouldn't happen (Hera code={hera_code})")


def create_hf(data: dict, district: Location, hera_code: str, hf_type: str):
    logger.info(f"Hera: creating health facility")
    hf_name = get_object_name_from_hera_payload(data)

    # first, check if there aren't already Hfs with the same name in the same district
    existing_hfs = HealthFacility.objects.filter(validity_to__isnull=True,
                                                 name=hf_name,
                                                 location=district).all()
    if existing_hfs:
        raise HeraNotificationException(f"a health facility with the same name already exists in that district "
                                        f"(Hera code={hera_code}, OI ID={existing_hfs})")

    hf = HealthFacility.objects.create(
        name=hf_name,
        audit_user_id=DEFAULT_AUDIT_USER_ID,
        code="HERA-TMP",
        level=HF_LEVELS_MAPPING[hf_type],
        legal_form=HealthFacilityLegalForm.objects.filter(code="G").first(),
        location=district,
        care_type=HealthFacility.CARE_TYPE_BOTH,
    )

    logger.info(f"Hera: creating health facility mapping")
    mapping = HeraHFIDsMapping.objects.create(
        hera_code=hera_code,
        openimis_hf=hf,
    )

    hf.code = f"HERA{mapping.id}"
    hf.save()

    logger.info(f"Hera: health facility successfully created")


def update_hf(data: dict, hf: HealthFacility, new_district: Location, hf_type: str):
    logger.info(f"Hera: trying to update health facility")

    from core import datetime
    hf.save_history()
    hf.location = new_district
    hf.name = get_object_name_from_hera_payload(data)
    hf.audit_user_id = DEFAULT_AUDIT_USER_ID
    hf.level = HF_LEVELS_MAPPING[hf_type]
    hf.legal_form = HealthFacilityLegalForm.objects.filter(code="G").first()
    hf.validity_from = datetime.datetime.now()
    hf.save()

    logger.info(f"Hera: health facility successfully updated")


def delete_hf(mapping: HeraHFIDsMapping):
    logger.info(f"Hera: deleting health facility")
    # Just like delete_location, there should be something in HealthFacility that decides what happens when a HF is deleted
    # for instance, decide what to do with claim admins, claims...
    mapping.delete_hf()
    logger.info(f"Hera: health facility successfully deleted")


def process_hf_event(data: dict, operation: str):
    logger.info(f"Hera: processing HF")
    # in Hera, HFs are placed at the openIMIS Village level, but in openIMIS, they are at the openIMIS District level
    hera_hf_code = data["location"]["locationCode"]
    hf_mapping = get_hera_hf_mapping_by_hera_code(hera_hf_code)

    if operation == HeraNotification.OPERATION_CREATE or operation == HeraNotification.OPERATION_UPDATE:
        # Checking if the HF type exists
        hf_type = data["location"]["type"]
        if hf_type not in AVAILABLE_HF_TYPES:
            raise HeraNotificationException(f"unknown type - {hf_type} (Hera code={hera_hf_code})")

        # Checking if the district exists
        hera_district_code = data["location"]["location"]["location"]["location"]["locationCode"]
        district_mapping = get_hera_location_mapping_by_hera_code(hera_district_code, location_type=LOCATION_TYPE_DISTRICT)
        if not district_mapping:
            raise HeraNotificationException(f"unknown district (district Hera code={hera_district_code}, "
                                            f"Hera hf code={hera_hf_code})")
        if not hf_mapping:
            if operation == HeraNotification.OPERATION_CREATE:
                create_hf(data, district_mapping.openimis_location, hera_hf_code, hf_type)
            else:
                raise HeraNotificationException(f"unknown hf, no mapping - can't update (Hera hf code={hera_hf_code})")
        else:
            if operation == HeraNotification.OPERATION_UPDATE:
                update_hf(data, hf_mapping.openimis_hf, district_mapping.openimis_location, hf_type)
            else:
                raise HeraNotificationException(f"can't create hf, mapping already exists (Hera hf code={hera_hf_code}, "
                                                f"mapping id={hf_mapping.id})")
    elif operation == HeraNotification.OPERATION_DELETE:
        if not hf_mapping:
            raise HeraNotificationException("can't delete HF, there is no mapping")

        delete_hf(hf_mapping)
    else:
        raise HeraNotificationException(f"unknown case, shouldn't happen (Hera code={hera_hf_code})")


def process_location_event_notification(notification: HeraNotification):
    logger.info(f"Hera: LocationEvent notification")
    operation = notification.operation
    context = notification.context

    # commented out for handling the initial load
    # if context.startswith(CONTEXT_DISTRICT_START):
    #     process_location_event(notification.json_ext, LOCATION_TYPE_DISTRICT, operation)
    # elif context.startswith(CONTEXT_WARD_START):
    #     process_location_event(notification.json_ext, LOCATION_TYPE_WARD, operation)
    # elif context.startswith(CONTEXT_VILLAGE_START):
    #     process_location_event(notification.json_ext, LOCATION_TYPE_VILLAGE, operation)
    # elif context.startswith(CONTEXT_HF_START):
    #     process_hf_event(notification.json_ext, operation)

    if context.startswith(CONTEXT_DISTRICT_START) or context.startswith(CONTEXT_WARD_START) or context.startswith(CONTEXT_VILLAGE_START):
        process_location_initial_load(notification.json_ext, context, operation)
    elif context.startswith(CONTEXT_HF_START):
        process_hf_initial_load(notification.json_ext, operation)

    else:
        raise HeraNotificationException(f"Hera: unknown context: {context} (notification id ={notification.id})")


def process_hera_notification(notification: HeraNotification):
    topic = notification.topic

    if topic == HeraNotification.TOPIC_LIFE_EVENT:
        process_life_event_notification(notification)
    elif topic == HeraNotification.TOPIC_LOCATION_EVENT:
        process_location_event_notification(notification)
    else:
        raise HeraNotificationException(f"Hera: unknown topic: {topic} (notification id ={notification.id})")


def create_hera_subscription(topic: str, user_id: int):
    hera = HeraInstance()
    data = hera.subscribe(topic)
    subscription = HeraSubscription.objects.create(
        uuid=data["uuid"],
        topic=data["topic"],
        json_ext=data,
        created_by=user_id,
    )
    return subscription


def delete_hera_subscription(subscription: HeraSubscription, user_id: int):
    try:
        hera = HeraInstance()
        success = hera.unsubscribe(subscription)
        if success:
            subscription.cancel(user_id)
            logger.info(f"Hera: subscription {subscription.uuid} successfully cancelled by user {user_id}")
            return []

    except Exception as exc:
        return {
            'title': subscription.uuid,
            'list': [{
                'message': _("hera_subscription.mutation.failed_to_unsubscribe") % {'uuid': subscription.uuid},
                'detail': str(exc)
            }]
        }
