import csv
import os

from core import datetime
from django.core.management.base import BaseCommand
from django.db.models import Q
from location.models import Location

from insuree.models import Gender, Insuree
from insuree.test_helpers import create_test_insuree, create_test_photo
from insuree.services import reset_insuree_before_update, is_modulo_10_number_valid


def replace_dict_key(dictionary: dict, old_key: str, new_key: str):
    dictionary[new_key] = dictionary[old_key]
    dictionary.pop(old_key)


def remove_dict_keys(dictionary: dict, keys: list):
    for key in keys:
        dictionary.pop(key, None)


def generate_location_filters(lga_name, district_name, settlement_name):
    return Q(validity_to__isnull=True) \
           & Q(name=settlement_name) \
           & Q(type="V") \
           & Q(parent__name=district_name) \
           & Q(parent__validity_to__isnull=True) \
           & Q(parent__type="W") \
           & Q(parent__parent__name=lga_name) \
           & Q(parent__parent__validity_to__isnull=True) \
           & Q(parent__parent__type="D")


def return_lga(lga_name):
    return Location.objects.filter(validity_to__isnull=True, type="D", name=lga_name).first()


GENDERS = {
    "FEMALE": Gender.objects.get(code='F'),
    "MALE": Gender.objects.get(code='M'),
}

# LGA IDs mapped to Villages IDs
UNKNOWN_VILLAGES = {
    539: 4873, # Banjul
    541: 4874, # Brikama
    542: 4875, # Mansakonko
    543: 4876, # Kerewan
    544: 4877, # Kuntaur
    547: 4878, # Janjanbureh
    2861: 4879, # Basse
    2960: 4880, # Kanifing
}


class Command(BaseCommand):
    help = "This command will import Insurees from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_location",
                            nargs=1,
                            type=str,
                            help="Absolute path to the CSV file")
        parser.add_argument(
            '-a',
            '--autoenroll',
            action='store_true',
            dest='autoenroll',
            help='Automatically enrolls the Insuree if they are eligible to autoenrollment',
        )

    def handle(self, *args, **options):
        file_location = options["csv_location"][0]
        if not os.path.isfile(file_location):
            print(f"Error - {file_location} is not a correct file path.")
        else:
            with open(file_location, mode='r', encoding='utf-8-sig') as csv_file:

                total_rows = 0
                total_created = 0
                total_updated = 0
                total_errors = 0
                total_autoenrollments = 0
                photo_root = os.environ.get("PHOTO_ROOT_PATH", "/data/photos")
                auto_enrollment = options["autoenroll"]

                print(f"**** Starting to import insurees from {file_location} ***")

                csv_reader = csv.DictReader(csv_file, delimiter=';')
                for row in csv_reader:

                    total_rows += 1

                    json_ext = {}
                    validity_from = datetime.datetime.now()

                    # Making a copy of raw data to store in json + cleaning fields
                    for key in row:
                        row[key] = row[key].strip()
                        json_ext[key] = row[key]
                    row["json_ext"] = json_ext

                    # Checking NIN validity
                    if not is_modulo_10_number_valid(row["nin"]):
                        print(f"{total_rows:7,} - Error: Insuree {row['nin']} - invalid NIN checksum")
                        total_errors += 1
                        continue

                    if len(row["nin"]) != 12:
                        print(f"{total_rows:7,} - Error: Insuree {row['nin']} - invalid NIN length")
                        total_errors += 1
                        continue

                    # Changing key names if data is ok as is
                    replace_dict_key(row, "nin", "chf_id")
                    replace_dict_key(row, "family_name", "last_name")
                    replace_dict_key(row, "given_name", "other_names")
                    replace_dict_key(row, "date_of_birth", "dob")
                    replace_dict_key(row, "mobile_number", "phone")

                    # Adding new keys and editing data
                    row["head"] = True
                    row["validity_from"] = validity_from
                    # row["dob"] = datetime.datetime.strptime(row["dob"], '%d/%m/%Y').strftime('%Y-%m-%d')
                    row["place_of_birth"] = row["pob_health_facility"] if row["pob_health_facility"] else row["pob_city"]
                    row["gender"] = GENDERS.get(row["sex"], Gender.objects.get(code='O'))
                    row["father_name"] = f"{row['father_name']} {row['father_lastname']}"
                    row["mother_name"] = f"{row['mother_name']} {row['mother_lastname']}"
                    row["is_local"] = row["nationality"] == row["pob_country"]

                    # Removing fields that are not directly stored
                    remove_dict_keys(row, ["id", "nationality", "sex", "father_lastname", "mother_lastname",
                                           "contact_person", "pob_place_type", "pob_country", "pob_lga",
                                           "pob_district", "pob_city", "pob_health_facility", "content_type",
                                           "document_type"])
                    photo_filename = row.pop("filename")
                    photo_date = row.pop("registration_date")

                    # Checking if the Insuree already exists
                    existing_insuree = Insuree.objects.filter(chf_id=row["chf_id"]).first()

                    if existing_insuree:
                        # TODO: update the Insuree's residence through their family, if eCRVS handles residence change
                        # TODO: same for Insuree's picture if it changes
                        existing_insuree.save_history()

                        # Removing location fields
                        remove_dict_keys(row, ["res_country", "res_lga", "res_district", "res_city",
                                               "por_lga", "por_district", "por_city"])
                        row["audit_user_id"] = -1

                        [setattr(existing_insuree, key, row[key]) for key in row]
                        existing_insuree.validity_from = validity_from
                        existing_insuree.save()
                        total_updated += 1
                        print(f"{total_rows:7,} - Insuree {row['chf_id']} updated")

                    else:
                        # Preparing the Family data
                        family_props = {
                            "validity_from": validity_from
                        }

                        # Filtering the person's residence location
                        if row["res_city"] and row["res_district"] and row["res_lga"]:
                            location_filters = generate_location_filters(row["res_lga"],
                                                                         row["res_district"],
                                                                         row["res_city"])
                        else:
                            # No information on the person's residence -> registration place
                            location_filters = generate_location_filters(row["por_lga"],
                                                                         row["por_district"],
                                                                         row["por_city"])

                        # Trying to link the Insuree to their Location
                        location = Location.objects.filter(location_filters).first()
                        if location:
                            family_props["location"] = location
                        else:
                            if row["res_city"] and row["res_district"] and row["res_lga"]:
                                location_string = f"Residence={row['res_lga']} - {row['res_district']} - {row['res_city']}"
                                lga_name = row["res_lga"]
                            else:
                                location_string = f"Registration={row['por_lga']} - {row['por_district']} - {row['por_city']}"
                                lga_name = row["por_lga"]

                            # The location does not exist, trying to link it now to one of the "unknown" villages
                            lga = return_lga(lga_name)

                            if not lga:
                                # Skipping this Insuree because its LGA is incorrect (not in our list)
                                total_errors += 1
                                print(f"{total_rows:7,} - Error: Insuree {row['chf_id']} - unknown LGA. "
                                      f"Location invalid: [{location_string}]")
                                continue
                            else:
                                village_id = UNKNOWN_VILLAGES[lga.id]
                                village = Location.objects.filter(id=village_id).first()
                                family_props["location"] = village

                        # Removing location fields
                        remove_dict_keys(row, ["res_country", "res_lga", "res_district", "res_city",
                                               "por_lga", "por_district", "por_city"])

                        # Inserting data into the DB
                        insuree = create_test_insuree(with_family=True, is_head=True, custom_props=row,
                                                      family_custom_props=family_props)
                        photo_props = {
                            "photo": "",
                            "chf_id": insuree.chf_id,
                            "folder": photo_root,
                            "filename": photo_filename,
                            "validity_from": validity_from,
                            "date": photo_date,
                        }
                        photo = create_test_photo(insuree_id=insuree.id, officer_id=-1, custom_props=photo_props)
                        insuree.photo = photo
                        insuree.save()

                        if auto_enrollment:
                            from autoenroll.services import autoenroll_family
                            autoenroll_family(insuree)
                            total_autoenrollments += 1

                        total_created += 1

                        if location:
                            print(f"{total_rows:7,} - Insuree {row['chf_id']} created with location.")
                        else:
                            print(f"{total_rows:7,} - Insuree {row['chf_id']} created in unknown location. "
                                  f"Location invalid: [{location_string}]")

                print(f"Import finished - {total_rows} lines received:")
                print(f"\t- {total_created} insurees created")
                print(f"\t- {total_updated} insurees updated")
                print(f"\t- {total_autoenrollments} automatic enrollments")
                print(f"\t- {total_errors} errors")
