from django.apps import AppConfig


DEFAULT_CONFIG = {
    "gql_hera_subscription_search_perms": ["124000"],
    "gql_hera_subscription_create_perms": ["124001"],
    "gql_hera_subscription_delete_perms": ["124002"],
    "gql_hera_notification_search_perms": ["125000"],
}


class EcrvsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ecrvs'

    gql_hera_subscription_search_perms = None
    gql_hera_subscription_create_perms = None
    gql_hera_subscription_delete_perms = None
    gql_hera_notification_search_perms = None

    def ready(self):
        from core.models import ModuleConfiguration

        cfg = ModuleConfiguration.get_or_default(self.name, DEFAULT_CONFIG)
        self.__load_config(cfg)

    @classmethod
    def __load_config(cls, cfg):
        for field in cfg:
            if hasattr(EcrvsConfig, field):
                setattr(EcrvsConfig, field, cfg[field])
