import logging

from django.db.models import Q

from autoenroll.services import autoenroll_family
from core.models import InteractiveUser
from ecrvs.models import HeraLocationIDsMapping, HeraNotification, HeraInstance, HeraHFIDsMapping
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

SUCCESS_MESSAGE = "success"

HF_TYPE_COMMUNITY_CLINIC = "Community Clinic"
HF_TYPE_COMMUNITY_CLINIC_2 = "Commmunity Clinic"
HF_TYPE_HOSPITAL = "Hospital"
HF_TYPE_MAJ_CENTER = "Major Health Centre"
HF_TYPE_MIN_CENTER = "Minor Health Centre"
HF_TYPE_VILLAGE_OPD = "Village OPD"
AVAILABLE_HF_TYPES = [
    HF_TYPE_COMMUNITY_CLINIC,
    HF_TYPE_COMMUNITY_CLINIC_2,
    HF_TYPE_HOSPITAL,
    HF_TYPE_MAJ_CENTER,
    HF_TYPE_MIN_CENTER,
    HF_TYPE_VILLAGE_OPD
]

HF_LEVELS_MAPPING = {
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


def trigger_error(error_message: str):
    logger.error(f"Hera: {error_message}")
    return False, error_message


def fetch_insuree_occupation_from_payload(hera_occupation: str):
    return Profession.objects.filter(profession=hera_occupation).first()


def process_new_insuree(insuree_data: dict, nin: str):

    # Here, we should theoretically check if the received NIN:
    # - has the right format
    # - has the right length
    # But the data in Hera is poor (bad format, no NIN...), so we shouldn't do that
    logger.info(f"Hera: trying to create family")
    raise ValueError

    existing_insuree = Insuree.objects.filter(validity_to__isnull=True, chf_id=nin).first()
    if existing_insuree:
        error_message = f"there's already an insuree with this nin (nin={nin})"
        return trigger_error(error_message)

    # get village from payload
    village_hera_code = insuree_data["residentialVillage"] if insuree_data["residentialVillage"] else insuree_data["registrationVillage"]
    village_mapping = get_hera_location_mapping_by_hera_code(village_hera_code, LOCATION_TYPE_VILLAGE)
    if not village_mapping:
        error_message = f"unknown village (Hera code={village_hera_code})"
        return trigger_error(error_message)
    # instead of triggering an error, we could place the family in an "unknown village", based on the LGA - to be discussed

    new_family = Family.objects.create(
        audit_user_id=DEFAULT_AUDIT_USER_ID,
        head_insuree_id=1,  # dummy
        location=village_mapping.openimis_location,
    )

    logger.info(f"Hera: trying to create insuree")
    # add email field to the insuree, once it's available on Hera
    new_insuree = Insuree.objects.create(
        chf_id=nin,
        other_names=insuree_data["firstName"],
        last_name=insuree_data["lastName"],
        phone=insuree_data["mobileNumber"],
        dob=insuree_data["dob"],
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

    logger.info(f"Hera: trying to autoenroll insuree (if applicable)")
    autoenroll_family(new_insuree, new_family)

    logger.info(f"Hera: insuree successfully created")
    return True, SUCCESS_MESSAGE


def process_life_event_notification(notification: HeraNotification):
    nin = notification.json_ext["nin"]
    context = notification.context

    hera_instance = HeraInstance()
    insuree_data = hera_instance.fetch_insuree_data_from_nin(nin)

    if context == HeraNotification.CONTEXT_BIRTH_CREATED:
        success, message = process_new_insuree(insuree_data, nin)
        notification.set_processed()
        logger.info(f"Hera: LifeEvent notification successfully processed")
        # return success, message
        return True, "success"

    error_message = f"unknown context, shouldn't happen (notification id ={notification.id})"
    return trigger_error(error_message)


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
    logger.info(f"Hera: trying to create location")

    # should we handle the case of deleted location that we try to recreate with the same code?
    # this crashes because the hera_code has unique=True -> IntegrityError when recreating

    # check if parent exists
    if location_type == LOCATION_TYPE_DISTRICT:
        parent_location = Location.objects.filter(validity_to__isnull=True, type=LOCATION_TYPE_REGION, name="The Gambia").first()
        if not parent_location:
            error_message = f"can't find the Gambia region"
            return trigger_error(error_message)

    else:
        parent_code = data["location"]["location"]["locationCode"]
        parent_mapping = get_hera_location_mapping_by_hera_code(parent_code)
        if not parent_mapping:
            error_message = f"no known parent location (parent Hera code={parent_code}, Hera code={hera_code})"
            return trigger_error(error_message)

        parent_location = parent_mapping.openimis_location

    location = Location.objects.create(
        name=get_object_name_from_hera_payload(data),
        audit_user_id=DEFAULT_AUDIT_USER_ID,
        parent=parent_location,
        type=location_type,
    )

    mapping = HeraLocationIDsMapping.objects.create(
        hera_code=hera_code,
        openimis_location=location,
        location_type=location_type
    )
    logger.info(f"Hera: location mapping created successfully")
    location.code = f"HERA{mapping.id}"
    location.save()

    if location_type == LOCATION_TYPE_DISTRICT:
        logger.info(f"Hera: adding new district to the Admin")
        admin = InteractiveUser.objects.filter(validity_to__isnull=True, id=1).first()
        UserDistrict.objects.create(
            user=admin,
            location=location,
            audit_user_id=DEFAULT_AUDIT_USER_ID,
        )

    logger.info(f"Hera: location successfully created")
    return True, SUCCESS_MESSAGE


def update_location(location: Location, data: dict, location_type: str, hera_code: str):
    logger.info(f"Hera: trying to update location")

    if location_type == LOCATION_TYPE_DISTRICT:
        parent_location = Location.objects.filter(validity_to__isnull=True, type=LOCATION_TYPE_REGION, name="The Gambia").first()
        if not parent_location:
            error_message = f"can't find the Gambia region"
            return trigger_error(error_message)

    else:
        # check if parent exists
        parent_code = data["location"]["location"]["locationCode"]
        parent_mapping = get_hera_location_mapping_by_hera_code(parent_code)
        if not parent_mapping:
            error_message = f"no known parent location (Hera code={hera_code}, Hera parent code={parent_code})"
            return trigger_error(error_message)
        parent_location = parent_mapping.openimis_location

        # check if parents are on the same level
        previous_parent_type = location.parent.type
        new_parent_type = parent_mapping.openimis_location.type
        if previous_parent_type != new_parent_type:
            error_message = (f"illegal move to other level in the pyramid - initial parent={previous_parent_type} "
                             f"new parent={new_parent_type} (Hera code={hera_code})")
            return trigger_error(error_message)

    # check if same level
    previous_type = location.type
    if previous_type != location_type:
        error_message = f"location type changed - previous={previous_type} new={location_type} (Hera code={location.code})"
        return trigger_error(error_message)

    # if all of this is ok, update
    from core import datetime
    location.save_history()
    location.name = get_object_name_from_hera_payload(data)
    location.validity_from = datetime.datetime.now()
    location.audit_user_id = DEFAULT_AUDIT_USER_ID
    location.parent = parent_location
    location.save()
    logger.info(f"Hera: location successfully updated")
    return True, SUCCESS_MESSAGE


def delete_location(mapping: HeraLocationIDsMapping):
    logger.info(f"Hera: trying to delete location")
    # Maybe there should be something in Location in order to cleanly delete a location
    # for instance, decide what to do with children locations, with families, Hfs...
    # This simply deleted the current location and leaves all the rest as it is.
    mapping.delete_location()
    logger.info(f"Hera: location successfully deleted")
    return True, SUCCESS_MESSAGE


def process_location_event(data: dict, location_type: str, operation: str):
    hera_code = data["location"]["locationCode"]
    location_mapping = get_hera_location_mapping_by_hera_code(hera_code, location_type=location_type)
    if not location_mapping:

        if operation == HeraNotification.OPERATION_CREATE:
            return create_location(data, location_type, hera_code)

        error_message = f"unknown location (Hera code={hera_code}, operation={operation})"
        return trigger_error(error_message)

    if operation == HeraNotification.OPERATION_UPDATE:
        return update_location(location_mapping.openimis_location, data, location_type, hera_code)
    elif operation == HeraNotification.OPERATION_DELETE:
        return delete_location(location_mapping)
    elif operation == HeraNotification.OPERATION_CREATE:
        error_message = f"location already exists with a mapping, can't create it again (Hera code={hera_code})"
        return trigger_error(error_message)

    error_message = f"unknown case, shouldn't happen (Hera code={hera_code})"
    return trigger_error(error_message)


def create_hf(data: dict, district: Location, hera_code: str, hf_type: str):
    logger.info(f"Hera: trying to create health facility")
    hf_name = get_object_name_from_hera_payload(data)

    # first, check if there aren't already Hfs with the same name in the same district
    existing_hfs = HealthFacility.objects.filter(validity_to__isnull=True,
                                                  name=hf_name,
                                                  location=district).all()
    if existing_hfs:
        error_message = (f"a health facility with the same name already exists in that district "
                         f"(Hera code={hera_code}, OI ID={existing_hfs})")
        return trigger_error(error_message)

    hf = HealthFacility.objects.create(
        name=hf_name,
        audit_user_id=DEFAULT_AUDIT_USER_ID,
        code="HERA-TMP",
        level=HF_LEVELS_MAPPING[hf_type],
        legal_form=HealthFacilityLegalForm.objects.filter(code="G").first(),
        location=district,
        care_type=HealthFacility.CARE_TYPE_BOTH,
    )
    mapping = HeraHFIDsMapping.objects.create(
        hera_code=hera_code,
        openimis_hf=hf,
    )

    hf.code = f"HERA{mapping.id}"
    hf.save()

    logger.info(f"Hera: health facility successfully created")
    return True, SUCCESS_MESSAGE


def update_hf(data: dict, hf: HealthFacility, new_district: Location, hf_type: str):
    logger.info(f"Hera: trying to update health facility")

    hf.save_history()

    from core import datetime
    hf.location = new_district
    hf.name = get_object_name_from_hera_payload(data)
    hf.audit_user_id = DEFAULT_AUDIT_USER_ID
    hf.level = HF_LEVELS_MAPPING[hf_type]
    hf.legal_form = HealthFacilityLegalForm.objects.filter(code="G").first()
    hf.validity_from = datetime.datetime.now()
    hf.save()

    logger.info(f"Hera: health facility successfully updated")
    return True, SUCCESS_MESSAGE


def delete_hf(mapping: HeraHFIDsMapping):
    logger.info(f"Hera: trying to delete health facility")
    # Just like delete_location, there should be something in HealthFacility that decides what happens when a HF is deleted
    # for instance, decide what to do with claim admins, claims...
    mapping.delete_hf()
    logger.info(f"Hera: health facility successfully deleted")
    return True, SUCCESS_MESSAGE


def process_hf_event(data: dict, operation: str):
    # in Hera, HFs are placed at the openIMIS Village level, but in openIMIS, they are at the openIMIS District level
    hera_hf_code = data["location"]["locationCode"]
    hf_mapping = get_hera_hf_mapping_by_hera_code(hera_hf_code)

    if operation == HeraNotification.OPERATION_CREATE or operation == HeraNotification.OPERATION_UPDATE:
        # Checking if the HF type exists
        hf_type = data["location"]["type"]
        if hf_type not in AVAILABLE_HF_TYPES:
            error_message = f"unknown type - {hf_type} (Hera code={hera_hf_code})"
            return trigger_error(error_message)

        # Checking if the district exists
        hera_district_code = data["location"]["location"]["location"]["location"]["locationCode"]
        district_mapping = get_hera_location_mapping_by_hera_code(hera_district_code, location_type=LOCATION_TYPE_DISTRICT)
        if not district_mapping:
            error_message = f"unknown district (district Hera code={hera_district_code}, Hera hf code={hera_hf_code})"
            return trigger_error(error_message)

        if not hf_mapping:
            if operation == HeraNotification.OPERATION_CREATE:
                return create_hf(data, district_mapping.openimis_location, hera_hf_code, hf_type)

            error_message = f"unknown hf, no mapping - can't update (Hera hf code={hera_hf_code})"
            return trigger_error(error_message)
        else:
            if operation == HeraNotification.OPERATION_UPDATE:
                return update_hf(data, hf_mapping.openimis_hf, district_mapping.openimis_location, hf_type)

            error_message = f"can't create hf, mapping already exists (Hera hf code={hera_hf_code}, mapping id={hf_mapping.id})"
            return trigger_error(error_message)

    elif operation == HeraNotification.OPERATION_DELETE:
        return delete_hf(hf_mapping)

    error_message = f"unknown case, shouldn't happen (Hera code={hera_hf_code})"
    return trigger_error(error_message)


def process_location_event_notification(notification: HeraNotification):
    operation = notification.operation
    context = notification.context

    if context.startswith(CONTEXT_DISTRICT_START):
        success, message = process_location_event(notification.json_ext, LOCATION_TYPE_DISTRICT, operation)
    elif context.startswith(CONTEXT_WARD_START):
        success, message = process_location_event(notification.json_ext, LOCATION_TYPE_WARD, operation)
    elif context.startswith(CONTEXT_VILLAGE_START):
        success, message = process_location_event(notification.json_ext, LOCATION_TYPE_VILLAGE, operation)
    elif context.startswith(CONTEXT_HF_START):
        success, message = process_hf_event(notification.json_ext, operation)
    else:
        notification.set_status(HeraNotification.STATUS_PROCESSED_ERROR)
        error_message = f"unknown context, shouldn't happen (notification id ={notification.id}, context={context})"
        return trigger_error(error_message)

    if success:
        notification.set_processed()
        logger.info(f"Hera: LocationEvent notification successfully processed")
    else:
        notification.set_status(HeraNotification.STATUS_PROCESSED_ERROR)

    return success, message


def process_hera_notification(notification: HeraNotification):
    topic = notification.topic

    if topic == HeraNotification.TOPIC_LIFE_EVENT:
        logger.info(f"Hera: LifeEvent notification")
        return process_life_event_notification(notification)

    elif topic == HeraNotification.TOPIC_LOCATION_EVENT:
        logger.info(f"Hera: LocationEvent notification")
        return process_location_event_notification(notification)

    error_message = f"unknown topic, shouldn't happen (notification id ={notification.id})"
    return trigger_error(error_message)


