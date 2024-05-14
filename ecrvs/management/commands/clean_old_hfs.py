import logging

from django.core.management import BaseCommand
from django.core.paginator import Paginator

from claim.models import Claim, ClaimAdmin
from core.models import InteractiveUser
from insuree.models import Insuree
from location.models import Location

HERA_UNKNOWN_VILLAGE_ID = 5857
FIRST_HERA_HF_ID = 133

logger = logging.getLogger(__name__)


MAPPING_HF_IDS = {
    8: 235,
    9: 199,
    10: 140,
    11: 138,
    12: 180,
    13: 202,
    14: 187,
    15: 227,
    16: 233,
    17: 146,
    18: 145,
    19: 195,
    20: 256,
    21: 142,
    22: 144,
    23: 135,
    24: 209,
    25: 168,
    26: 148,
    27: 283,
    28: 177,
    29: 240,
    30: 212,
    31: 275,
    32: 200,
    33: 259,
    34: 152,
    35: 171,
    36: 178,
    37: 215,
    38: 193,
    39: 133,
    40: 239,
    41: 174,
    42: 248,
    43: 210,
    44: 268,
    45: 196,
    46: 179,
    48: 218,
    50: 280,
    51: 203,
    52: 204,
    53: 184,
    54: 186,
    55: 150,
    56: 190,
    57: 267,
    58: 165,
    59: 226,
    60: 278,
    61: 230,
    62: 284,
    63: 249,
    64: 237,
    65: 205,
    66: 191,
    67: 192,
    68: 262,
    69: 167,
    70: 201,
    71: 198,
    72: 236,
    73: 176,
    74: 163,
    75: 143,
    76: 231,
    77: 258,
    78: 158,
    79: 139,
    80: 244,
    81: 151,
    82: 266,
    83: 271,
    84: 234,
    85: 175,
    86: 254,
    87: 222,
    88: 136,
    89: 238,
    90: 185,
    91: 182,
    92: 206,
    93: 157,
    94: 223,
    95: 261,
    96: 225,
    97: 273,
    98: 247,
    99: 246,
    100: 170,
    101: 253,
    102: 153,
    103: 173,
    104: 172,
    105: 154,
    106: 245,
    107: 219,
    108: 164,
    109: 189,
    110: 208,
    111: 255,
    112: 161,
    113: 243,
    114: 147,
    115: 213,
    116: 181,
    117: 207,
    118: 224,
    119: 279,
    120: 277,
    121: 281,
    122: 216,
    123: 220,
    124: 166,
    125: 188,
    126: 214,
    127: 149,
    128: 156
}


def print_result(results: dict, element: str):
    logger.info("**************************************")
    logger.info(f"Total {element}: {results['total']}")
    logger.info(f"- updated: {results['updated']}")
    logger.info(f"- skipped: {results['skipped']}")
    logger.info(f"- error no mapping: {results['error']}\n\n")


def clean_users():
    logger.info("*** CLEANING HFS IN USERS ***")

    total = 0
    skipped = 0
    updated = 0
    error = 0

    users = InteractiveUser.objects.filter(validity_to__isnull=True, health_facility_id__isnull=False).all()
    for user in users:
        total += 1
        logger.info(f"\tprocessing {user.id}")

        current_hf_id = user.health_facility_id

        if current_hf_id >= FIRST_HERA_HF_ID:
            logger.info(f"\t\talready in the new HF, nothing to do")
            skipped += 1
            continue

        new_hf_id = MAPPING_HF_IDS.get(current_hf_id, None)
        if not new_hf_id:
            logger.warning(f"\t\tunknown hf id, not in mapping ({current_hf_id})")
            error += 1
            continue

        user.health_facility_id = new_hf_id
        user.save()
        updated += 1
        logger.info(f"\t\tuser updated - was in ID {current_hf_id}, now in {new_hf_id}")

    print_result(
        {
            "total": total,
            "skipped": skipped,
            "updated": updated,
            "error": error,
        },
        "users"
    )


def clean_claims():
    logger.info("*** CLEANING HFS IN CLAIMS ***")

    total = 0
    skipped = 0
    updated = 0
    error = 0

    claims = Claim.objects.all()
    for claim in claims:
        total += 1
        logger.info(f"\tprocessing {claim.id}")

        current_hf_id = claim.health_facility_id

        if current_hf_id >= FIRST_HERA_HF_ID:
            logger.info(f"\t\talready in the new HF, nothing to do")
            skipped += 1
            continue

        new_hf_id = MAPPING_HF_IDS.get(current_hf_id, None)
        if not new_hf_id:
            logger.warning(f"\t\tunknown hf id, not in mapping ({current_hf_id})")
            error += 1
            continue

        claim.health_facility_id = new_hf_id
        claim.save()
        updated += 1
        logger.info(f"\t\tclaim updated - was in ID {current_hf_id}, now in {new_hf_id}")

    print_result(
        {
            "total": total,
            "skipped": skipped,
            "updated": updated,
            "error": error,
        },
        "claims"
    )


def clean_claim_admins():
    logger.info("*** CLEANING HFS IN CLAIM ADMINS ***")

    total = 0
    skipped = 0
    updated = 0
    error = 0

    claim_admins = ClaimAdmin.objects.all()
    for claim_admin in claim_admins:
        total += 1
        logger.info(f"\tprocessing {claim_admin.id}")

        current_hf_id = claim_admin.health_facility_id

        if current_hf_id >= FIRST_HERA_HF_ID:
            logger.info(f"\t\talready in the new HF, nothing to do")
            skipped += 1
            continue

        new_hf_id = MAPPING_HF_IDS.get(current_hf_id, None)
        if not new_hf_id:
            logger.warning(f"\t\tunknown hf id, not in mapping ({current_hf_id})")
            error += 1
            continue

        claim_admin.health_facility_id = new_hf_id
        claim_admin.save()
        updated += 1
        logger.info(f"\t\tclaim admin updated - was in ID {current_hf_id}, now in {new_hf_id}")

    print_result(
        {
            "total": total,
            "skipped": skipped,
            "updated": updated,
            "error": error,
        },
        "claim admins"
    )


class Command(BaseCommand):
    help = """
        This command will clean old health facilities in various places in the system in order to use the ones that are coming from Hera."
        This command will update: 
            - users, 
            - claim administrators,
            - claims, 
    """

    def handle(self, *args, **options):
        error_message = (
            "This command was created in order to clean data on the GMB production instance after the eCRVS integration."
            "It was a one shot and should not be used again.")
        print(error_message)
        logger.error(error_message)
        return

        clean_users()
        clean_claims()
        clean_claim_admins()
