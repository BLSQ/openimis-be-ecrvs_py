import os
import csv

from django.core.management import BaseCommand

from ecrvs.services import get_hera_location_mapping_by_hera_id
from location.models import HealthFacility, HealthFacilityLegalForm

TYPE_COMMUNITY_CLINIC = "Community Clinic"
TYPE_COMMUNITY_CLINIC_2 = "Commmunity Clinic"
TYPE_HOSPITAL = "Hospital"
TYPE_MAJ_CENTER = "Major Health Centre"
TYPE_MIN_CENTER = "Minor Health Centre"
TYPE_VILLAGE_OPD = "Village OPD"
AVAILABLE_TYPES = [
    TYPE_COMMUNITY_CLINIC,
    TYPE_COMMUNITY_CLINIC_2,
    TYPE_HOSPITAL,
    TYPE_MAJ_CENTER,
    TYPE_MIN_CENTER,
    TYPE_VILLAGE_OPD
]

LEVELS_MAPPING = {
    TYPE_COMMUNITY_CLINIC: HealthFacility.LEVEL_DISPENSARY,
    TYPE_COMMUNITY_CLINIC_2: HealthFacility.LEVEL_DISPENSARY,
    TYPE_VILLAGE_OPD: HealthFacility.LEVEL_DISPENSARY,
    TYPE_MIN_CENTER: HealthFacility.LEVEL_HEALTH_CENTER,
    TYPE_MAJ_CENTER: HealthFacility.LEVEL_HEALTH_CENTER,
    TYPE_HOSPITAL: HealthFacility.LEVEL_HOSPITAL,
}

HEADER_LOCATION_HERA_ID = "city_id"
DEFAULT_SYSTEM_AUDIT_USER_ID = -1


def update_hf(hf: HealthFacility, new_name: str, new_level: str, new_village_id: int):
    old_name = hf.name
    old_level = hf.level
    old_village_id = hf.location_id

    if old_name != new_name or old_level != new_level or old_village_id != new_village_id:
        from core import datetime
        hf.save_history()
        hf.name = new_name
        hf.level = new_level
        hf.location_id = new_village_id
        hf.audit_user_id = DEFAULT_SYSTEM_AUDIT_USER_ID
        hf.validity_from = datetime.datetime.now()
        hf.save()
        return True

    return False


class Command(BaseCommand):
    help = "This command will import Health Facilities from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_location",
                            nargs=1,
                            type=str,
                            help="Absolute path to the Health Facility CSV file")

    def handle(self, *args, **options):
        file_location = options["csv_location"][0]
        if not os.path.isfile(file_location):
            print(f"Error - {file_location} is not a correct file path.")
        else:
            with open(file_location, mode='r', encoding='utf-8-sig') as csv_file:

                total_rows = 0
                total_hfs_created = 0
                total_hfs_updated = 0
                total_hfs_skipped = 0
                total_mapping_created = 0
                total_error_unknown_village_hera_id = 0
                total_error_no_village_hera_id = 0
                total_error_unknown_type = 0

                location_type = options.get("type", None)
                legal_form = HealthFacilityLegalForm.objects.filter(code="G").first()

                print(f"*** Starting to import health facilities from {file_location} ***")

                csv_reader = csv.DictReader(csv_file, delimiter=',')
                for row in csv_reader:

                    total_rows += 1
                    hf_name = row["name"].strip()
                    hf_type = row["type"].strip()
                    hf_village_id = int(row[HEADER_LOCATION_HERA_ID].strip())

                    if hf_type not in AVAILABLE_TYPES:
                        total_error_unknown_type += 1
                        print(f"\tError line {total_rows} - unknown type ({location_type})")
                        continue

                    if not hf_village_id:
                        total_error_no_village_hera_id += 1
                        print(f"\tError line {total_rows} - no village id")
                        continue

                    village_mapping = get_hera_location_mapping_by_hera_id(hf_village_id)
                    if not village_mapping:
                        total_error_unknown_village_hera_id += 1
                        print(f"\tError line {total_rows} - unknown village HERA id ({hf_village_id})")
                        continue

                    existing_hf = HealthFacility.objects.filter(validity_to__isnull=True,
                                                                level=LEVELS_MAPPING[hf_type],
                                                                name=hf_name,
                                                                location=village_mapping.openimis_location) \
                                                        .first()
                    if existing_hf:
                        was_updated = update_hf(existing_hf,
                                                hf_name,
                                                LEVELS_MAPPING[hf_type],
                                                village_mapping.openimis_location.id)
                        if was_updated:
                            total_hfs_updated += 1
                        else:
                            total_hfs_skipped += 1
                    else:
                        HealthFacility.objects.create(
                            level=LEVELS_MAPPING[hf_type],
                            location=village_mapping.openimis_location,
                            name=hf_name,
                            code=f"HF{village_mapping.hera_id}",
                            type=HealthFacility.CARE_TYPE_BOTH,
                            audit_user_id=-1,
                            legal_form=legal_form,
                            care_type="B"
                        )

                        total_hfs_created += 1

                print("------------------------")
                print("Upload finished:")
                print(f"\t- total row received: {total_rows}")
                print(f"\t- health facilities created: {total_hfs_created}")
                print(f"\t- health facilities updated: {total_hfs_updated}")
                print(f"\t- health facilities skipped: {total_hfs_skipped} (no update needed because values were identical)")
                print(f"\t- mappings created: {total_mapping_created}")
                print(f"\t- errors - unknown village: {total_error_unknown_village_hera_id}")
                print(f"\t- errors - no village id: {total_error_no_village_hera_id}")
                print(f"\t- errors - unknown type: {total_error_unknown_type}")
