class HeraNotificationException(Exception):
    """
    This is raised every time there is an issue during the handling of a Hera notification through the webhook.
    """
    pass


class HeraSubscriptionException(Exception):
    """
    This is raised every time there is an issue during the handling of Hera subscriptions.
    """
    pass


class HeraSetupException(Exception):
    """
    This is raised every time there is an issue with the Hera environment variables setup.
    For instance, when a required variable is not defined.
    """
    pass
