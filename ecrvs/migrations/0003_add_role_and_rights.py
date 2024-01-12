# Generated by Django 3.2.16 on 2023-10-12 13:45

from django.db import migrations
from django.db.migrations import RunPython

RIGHT_HERA_SUBSCRIPTIONS_SEARCH = 124000
RIGHT_HERA_SUBSCRIPTIONS_CREATE = 124001
RIGHT_HERA_SUBSCRIPTIONS_DELETE = 124002
RIGHT_HERA_NOTIFICATIONS_SEARCH = 125000
RIGHTS = [
    RIGHT_HERA_SUBSCRIPTIONS_SEARCH,
    RIGHT_HERA_SUBSCRIPTIONS_CREATE,
    RIGHT_HERA_SUBSCRIPTIONS_DELETE,
    RIGHT_HERA_NOTIFICATIONS_SEARCH,
]

ROLE_HERA_ADMINISTRATOR = "Hera Administrator"
AUDIT_USER_ID = -1


def set_up_hera_administrator(apps, schema_editor):
    # Sets up the Hera Admin role along with its rights, and adds this role to the Admin
    # If this has already been done, this function doesn't do anything

    RoleRight = apps.get_model("core", "RoleRight")

    existing_rights = RoleRight.objects.filter(right_id__in=RIGHTS, validity_to__isnull=True).all()
    if existing_rights:
        # rights were already setup, there is no need to recreate everything
        return

    Role = apps.get_model("core", "Role")
    InteractiveUser = apps.get_model("core", "InteractiveUser")
    UserRole = apps.get_model("core", "UserRole")

    # Create a new role
    hera_admin_role = Role.objects.create(
        name=ROLE_HERA_ADMINISTRATOR,
        is_system=0,
        is_blocked=False,
        audit_user_id=AUDIT_USER_ID
    )

    # Add each right to the new role
    for right in RIGHTS:
        RoleRight.objects.create(
            role=hera_admin_role,
            right_id=right,
            audit_user_id=AUDIT_USER_ID,
        )

    admin = InteractiveUser.objects.filter(validity_to__isnull=True, id=1, login_name="Admin").first()
    if not admin:
        raise ValueError("Can't find the administrator")

    # Grant this new role to the Admin
    UserRole.objects.create(
        user=admin,
        role=hera_admin_role,
        audit_user_id=AUDIT_USER_ID,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ecrvs', '0002_hera_subscription_fixes_and_mutations'),
    ]

    operations = [
        migrations.RunPython(set_up_hera_administrator, RunPython.noop),
    ]
