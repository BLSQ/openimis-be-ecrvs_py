import datetime
import logging

from django.core.management import BaseCommand
from django.core.paginator import Paginator

from claim.models import Claim, ClaimAdmin
from core.models import InteractiveUser, Officer
from insuree.models import Insuree
from location.models import Location, OfficerVillage

HERA_UNKNOWN_VILLAGE_ID = 5857
FIRST_HERA_LOCATION_ID = 4881

logger = logging.getLogger(__name__)


OLD_LGA_BANJUL_ID = 539
OLD_LGA_BASSE_ID = 2861
OLD_LGA_BRIKAMA_ID = 541
OLD_LGA_JANJANBUREH_ID = 547
OLD_LGA_KANIFING_ID = 2960
OLD_LGA_KUNTAUR_ID = 544
OLD_LGA_KEREWAN_ID = 543
OLD_LGA_MANSAKONKO_ID = 542

NEW_LGA_BANJUL_ID = 4882
NEW_LGA_BASSE_ID = 4884
NEW_LGA_BRIKAMA_ID = 4885
NEW_LGA_JANJANBUREH_ID = 4887
NEW_LGA_KANIFING_ID = 4886
NEW_LGA_KUNTAUR_ID = 4883
NEW_LGA_KEREWAN_ID = 4881
NEW_LGA_MANSAKONKO_ID = 4888
NEW_LGA_UNKNOWN_ID = 4889
CURRENT_LGAS = [
    NEW_LGA_BANJUL_ID,
    NEW_LGA_BASSE_ID,
    NEW_LGA_BRIKAMA_ID,
    NEW_LGA_JANJANBUREH_ID,
    NEW_LGA_KANIFING_ID,
    NEW_LGA_KUNTAUR_ID,
    NEW_LGA_KEREWAN_ID,
    NEW_LGA_MANSAKONKO_ID,
    NEW_LGA_UNKNOWN_ID,
]

MAPPING_OLD_DISTRICTS_TO_NEW_DISTRICTS = {
    OLD_LGA_BANJUL_ID: 4882,  # 110 Banjul
    OLD_LGA_KEREWAN_ID: 4881,  # 160 Kerewan
    OLD_LGA_KUNTAUR_ID: 4883,  # 170 Kuntaur
    OLD_LGA_BASSE_ID: 4884,  # 120 Basse
    OLD_LGA_BRIKAMA_ID: 4885,  # 130 Brikama
    OLD_LGA_KANIFING_ID: 4886,  # 150 Kanifing
    OLD_LGA_JANJANBUREH_ID: 4887,  # 140 Janjanbureh
    OLD_LGA_MANSAKONKO_ID: 4888  # 180 Mansakonko
}

# IDs manually fetched from the DB
MAPPING_OLD_WARDS_TO_NEW_DISTRICTS = {
    582: NEW_LGA_MANSAKONKO_ID,  # 180 Mansakonko
    583: NEW_LGA_MANSAKONKO_ID,  # 180 Mansakonko
    584: NEW_LGA_MANSAKONKO_ID,  # 180 Mansakonko
    585: NEW_LGA_MANSAKONKO_ID,  # 180 Mansakonko
    586: NEW_LGA_MANSAKONKO_ID,  # 180 Mansakonko
    587: NEW_LGA_MANSAKONKO_ID,  # 180 Mansakonko
    545: NEW_LGA_KUNTAUR_ID,  # 170 Kuntaur
    546: NEW_LGA_KUNTAUR_ID,  # 170 Kuntaur
    595: NEW_LGA_KUNTAUR_ID,  # 170 Kuntaur
    596: NEW_LGA_KUNTAUR_ID,  # 170 Kuntaur
    597: NEW_LGA_KUNTAUR_ID,  # 170 Kuntaur
    588: NEW_LGA_KEREWAN_ID,  # 160 Kerewan
    589: NEW_LGA_KEREWAN_ID,  # 160 Kerewan
    590: NEW_LGA_KEREWAN_ID,  # 160 Kerewan
    591: NEW_LGA_KEREWAN_ID,  # 160 Kerewan
    592: NEW_LGA_KEREWAN_ID,  # 160 Kerewan
    593: NEW_LGA_KEREWAN_ID,  # 160 Kerewan
    594: NEW_LGA_KEREWAN_ID,  # 160 Kerewan
    2961: NEW_LGA_KANIFING_ID,  # 150 Kanifing
    2962: NEW_LGA_KANIFING_ID,  # 150 Kanifing
    2963: NEW_LGA_KANIFING_ID,  # 150 Kanifing
    2964: NEW_LGA_KANIFING_ID,  # 150 Kanifing
    2965: NEW_LGA_KANIFING_ID,  # 150 Kanifing
    2966: NEW_LGA_KANIFING_ID,  # 150 Kanifing
    2967: NEW_LGA_KANIFING_ID,  # 150 Kanifing
    548: NEW_LGA_JANJANBUREH_ID,  # 140 Janjanbureh
    549: NEW_LGA_JANJANBUREH_ID,  # 140 Janjanbureh
    765: NEW_LGA_JANJANBUREH_ID,  # 140 Janjanbureh
    766: NEW_LGA_JANJANBUREH_ID,  # 140 Janjanbureh
    767: NEW_LGA_JANJANBUREH_ID,  # 140 Janjanbureh
    844: NEW_LGA_JANJANBUREH_ID,  # 140 Janjanbureh
    573: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    574: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    575: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    576: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    577: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    578: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    579: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    580: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    581: NEW_LGA_BRIKAMA_ID,  # 130 Brikama
    1065: NEW_LGA_BASSE_ID,  # 120 Basse
    1066: NEW_LGA_BASSE_ID,  # 120 Basse
    1067: NEW_LGA_BASSE_ID,  # 120 Basse
    1068: NEW_LGA_BASSE_ID,  # 120 Basse
    1069: NEW_LGA_BASSE_ID,  # 120 Basse
    1070: NEW_LGA_BASSE_ID,  # 120 Basse
    550: NEW_LGA_BASSE_ID,  # 120 Basse
    553: NEW_LGA_BANJUL_ID,  # 110 Banjul
    552: NEW_LGA_BANJUL_ID,  # 110 Banjul
    551: NEW_LGA_BANJUL_ID,  # 110 Banjul
}


def get_villages_in_each_lga():
    mapping = {}
    for lga in CURRENT_LGAS:
        mapping[lga] = get_villages_in_lga(lga)
    return mapping


def get_villages_in_lga(lga_id):
    villages = (Location.objects.filter(validity_to__isnull=True,
                                        parent__parent_id=lga_id,
                                        type="V")
                                .values_list('id', flat=True))
    return villages


class Command(BaseCommand):
    help = """
        This command will clean old enrollment officer villages in order to use the ones that are coming from Hera."
    """

    def handle(self, *args, **options):

        error_message = ("This command was created in order to clean data on the GMB production instance after the eCRVS integration."
                         "It was a one shot and should not be used again.")
        print(error_message)
        logger.error(error_message)
        return

        logger.info("*** CLEANING ENROLLMENT OFFICER VILLAGES ***")

        total = 0
        created = 0
        error = 0

        village_ids_per_lga = get_villages_in_each_lga()
        from core import datetime
        now = datetime.datetime.now()

        # Fetching all enrollment officers
        officers = (Officer.objects.filter(validity_to__isnull=True)
                                   .prefetch_related("officer_villages")
                                   .prefetch_related("officer_villages__location"))
        for officer in officers:
            logger.info(f"\tprocessing {officer.code}")
            new_lga_set = set()

            villages = officer.officer_villages.filter(validity_to__isnull=True)
            for village in villages:
                ward_id = village.location.parent_id
                total += 1

                # Trying to find in which lga/district each village is
                new_lga = MAPPING_OLD_WARDS_TO_NEW_DISTRICTS.get(ward_id, NEW_LGA_UNKNOWN_ID)
                if new_lga == NEW_LGA_UNKNOWN_ID:
                    logger.warning(f"\t\tno mapping for {village.id} - parent id {ward_id}")
                    error += 1
                new_lga_set.add(new_lga)

            # now that we know all the lgas, let's create a new EO village for each village in the new pyramid in that LGA
            for lga in new_lga_set:
                new_villages = village_ids_per_lga[lga]
                for village in new_villages:
                    # not using bulk create because of technical limitations with django and MSSQL - see bulk_create doc
                    new_village = OfficerVillage.objects.create(
                        officer=officer,
                        audit_user_id=-1,
                        location_id=village,
                        validity_from=now,
                    )
                    created += 1
            logger.info(f"\tfinished processing {officer.code}")

        logger.info("**************************************")
        logger.info(f"Total old EO villages: {total}")
        logger.info(f"Total new EO created: {created}")
        logger.info(f"Total errors no mapping: {error}")
