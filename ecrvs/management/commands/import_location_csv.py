import os
import csv

from django.core.management import BaseCommand

from ecrvs.models import HeraLocationIDsMapping
from ecrvs.services import get_hera_location_mapping_by_hera_id
from location.models import Location

LOCATION_TYPE_REGION = "R"
LOCATION_TYPE_DISTRICT = "D"
LOCATION_TYPE_WARD = "W"
LOCATION_TYPE_VILLAGE = "V"
LOCATION_TYPES = [LOCATION_TYPE_REGION, LOCATION_TYPE_DISTRICT, LOCATION_TYPE_WARD, LOCATION_TYPE_VILLAGE]

REGION_PARENT_ID_LABEL = "parent_id"
REGION_INF0 = {
    "parent": REGION_PARENT_ID_LABEL,
    "headers": [
        "id",
        "name",
        REGION_PARENT_ID_LABEL,
    ]

}

LGA_PARENT_ID_LABEL = "country_id"
LGA_INFO = {
    "parent": LGA_PARENT_ID_LABEL,
    "headers": [
        "id",
        "name",
        LGA_PARENT_ID_LABEL,
    ]
}

DISTRICT_PARENT_ID_LABEL = "subdivision_id"
DISTRICT_INFO = {
    "parent": DISTRICT_PARENT_ID_LABEL,
    "headers": [
        "id",
        "name",
        DISTRICT_PARENT_ID_LABEL,
    ]
}

SETTLEMENT_PARENT_ID_LABEL = "district_id"
SETTLEMENT_INFO = {
    "parent": SETTLEMENT_PARENT_ID_LABEL,
    "headers": [
        "id",
        "name",
        "subdivision_id",
        SETTLEMENT_PARENT_ID_LABEL,
        "longitude",
        "latitude",
        "rural_urban_area",
    ]
}

LOCATION_INFO = {
    LOCATION_TYPE_REGION: REGION_INF0,
    LOCATION_TYPE_DISTRICT: LGA_INFO,
    LOCATION_TYPE_WARD: DISTRICT_INFO,
    LOCATION_TYPE_VILLAGE: SETTLEMENT_INFO,
}

DEFAULT_SYSTEM_AUDIT_USER_ID = -1


def get_parent_id_from_row(row: dict, location_type: str):
    parent_label = LOCATION_INFO[location_type]["parent"]
    result = int(row[parent_label]) if row[parent_label] else None
    return result


def update_location(location: Location, new_name: str, new_type: str, new_parent_id: int):
    old_name = location.name
    old_type = location.type
    old_parent_id = location.parent_id

    if old_name != new_name or old_type != new_type or old_parent_id != new_parent_id:
        from core import datetime
        location.save_history()
        location.name = new_name
        location.type = new_type
        location.parent_id = new_parent_id
        location.audit_user_id = DEFAULT_SYSTEM_AUDIT_USER_ID
        location.validity_from = datetime.datetime.now()
        location.save()
        return True

    return False


class Command(BaseCommand):
    help = "This command will import Locations from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_location",
                            nargs=1,
                            type=str,
                            help="Absolute path to the Location CSV file")
        parser.add_argument('--type',
                            type=str,
                            dest='type',
                            required=True,
                            help=f'Location type. Supported types are: {LOCATION_TYPES}',
                            choices=LOCATION_TYPES)

    def handle(self, *args, **options):
        file_location = options["csv_location"][0]
        if not os.path.isfile(file_location):
            print(f"Error - {file_location} is not a correct file path.")
        else:
            with open(file_location, mode='r', encoding='utf-8-sig') as csv_file:

                total_rows = 0
                total_location_created = 0
                total_location_updated = 0
                total_location_skipped = 0
                total_mapping_created = 0
                total_error_unknown_parent_hera_id = 0
                total_error_moving_to_other_level = 0

                location_type = options.get("type", None)

                print(f"*** Starting to import locations from {file_location} - location type={location_type} ***")

                csv_reader = csv.DictReader(csv_file, delimiter=',')
                for row in csv_reader:

                    total_rows += 1
                    location_name = row["name"].strip()

                    # first checking if everything is ok with the parent Location
                    parent_id = get_parent_id_from_row(row, location_type)
                    parent_mapping = get_hera_location_mapping_by_hera_id(parent_id)
                    if parent_id and not parent_mapping:
                        total_error_unknown_parent_hera_id += 1
                        print(f"\tError line {total_rows} - unknown parent id ({parent_id})")
                        continue

                    existing_mapping = get_hera_location_mapping_by_hera_id(row["id"], location_type)
                    if existing_mapping:
                        was_updated = update_location(existing_mapping.openimis_location, location_name, location_type, parent_id)
                        if was_updated:
                            total_location_updated += 1
                        else:
                            total_location_skipped += 1
                    else:  # There is no mapping yet

                        existing_location = Location.objects.filter(validity_to__isnull=True,
                                                                    type=location_type,
                                                                    parent_id=parent_id,
                                                                    name=location_name) \
                                                            .first()

                        if not existing_location:  # The location does not exist yet

                            new_location = Location.objects.create(
                                name=location_name,
                                type=location_type,
                                parent_id=parent_id,
                                audit_user_id=DEFAULT_SYSTEM_AUDIT_USER_ID,
                            )
                            location_for_mapping = new_location

                            new_location.code = f"HERA{new_location.id}"
                            new_location.save()
                            total_location_created += 1

                        else:  # The Location already exists
                            # Checking if the location was moved to another level in the pyramid, which is not supported
                            new_parent_type = parent_mapping.openimis_location.parent.type
                            existing_parent_type = existing_location.parent.type
                            if new_parent_type != existing_parent_type:
                                total_error_moving_to_other_level += 1
                                print(f"\tError line {total_rows} - moving location to other level in the pyramid. "
                                      f"Parent before-{existing_parent_type} - parent now-{new_parent_type}.")
                                continue

                            location_for_mapping = existing_location
                            was_updated = update_location(existing_location, location_name, location_type, parent_id)
                            if was_updated:
                                total_location_updated += 1
                            else:
                                total_location_skipped += 1

                        # Whether the Location already exists or not, the mapping still needs to be made
                        HeraLocationIDsMapping.objects.create(
                            hera_id=row["id"],
                            openimis_id=location_for_mapping,
                            location_type=location_type,
                        )
                        total_mapping_created += 1

                print("------------------------")
                print("Upload finished:")
                print(f"\t- total row received: {total_rows}")
                print(f"\t- locations created: {total_location_created}")
                print(f"\t- locations updated: {total_location_updated}")
                print(f"\t- locations skipped: {total_location_skipped} (useless updates)")
                print(f"\t- mappings created: {total_mapping_created}")
                print(f"\t- errors - unknown parent: {total_error_unknown_parent_hera_id}")
                print(f"\t- errors - moving to other level: {total_error_moving_to_other_level}\n")
