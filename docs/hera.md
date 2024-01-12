# Hera eCRVS Integration - Documentation

This documentation will describe the Hera integration.

## Current implementations
- Hera 3.0 - The Gambia

## Hera 3.0 in The Gambia
### Description
In The Gambia, Hera is the main source for all data related to population, locations (districts, villages...) and health facilities. 
Any new/updated/deleted data in Hera is therefore reflected later on in openIMIS.

Hera works with a subscription system: you first subscribe to a topic and later receive notifications through a webhook.

In some cases, the notification contains all the necessary information (locations, HFs). 
In others, it contains an ID that can be used to fetch the full information in a Hera endpoint (insurees).

For more details on how Hera works, please refer to the Hera documentation on the shared drive. 
The shared drive also contains various examples of Hera notifications.

### Goal
The goal of this integration is for an openIMIS instance to:
- be able to subscribe to any Hera topic
- be able to receive any Hera notification through a webhook and fetch extra information if needed
- store all the relevant information for openIMIS

### Workflow
1. Insert in the backend settings the list of fields that are going to be fetched for insurees - called `HERA_INSUREE_FIELDS_TO_FETCH`. For instance:
``
HERA_INSUREE_FIELDS_TO_FETCH = [
    "firstName",
    "lastName",
    "gender",
    "dob"
]
``
2. Start the backend with the following environment variables defined
   - `HERA_LOGIN_URL`: the keycloak instance where Hera login is done
   - `HERA_DATA_URL`: the Hera instance where subscriptions can be made and from which data comes 
   - `HERA_LOGIN_SECRET`: the secret required for logging in
   - `HERA_WEBHOOK_ADDRESS`: the webhook address that is going to receive the Hera notifications (= the URL of the server where this module is installed)
3. Subscribe to any desired Hera topic through the webpage for instance
4. Wait to receive a notification (or send manually a fake one on the webhook)
   - All the notifications are stored.
   - Then, they are processed if possible and applicable (= if there is no error). Custom exceptions are raised in case of errors such as updating or deleting nonexistent data. Error messages are logged.
   - The only exception to the processing of incorrect data is related to insuree creation: 
   if a `BIRTH_REGISTRATION_CREATED` notification is received and there already is an Insuree with the same NIN, 
   then this person is updated. This was done on purpose for the initial data load, but shouldn't happen afterward.


### Main differences between Hera & openIMIS

There are differences in terminology on the location level:

| Hera                                         | openIMIS | The Gambia | 
|----------------------------------------------|----------|------------|
| / (theoretically country, but it's not sent) | Region   | /          |
| Province                                     | District | LGA        |
| District                                     | Ward     | District   |
| Place                                        | Village  | Settlement |

There are conceptual differences on the health facility level:

|                                       | Hera                                 | openIMIS                                |
|---------------------------------------|--------------------------------------|-----------------------------------------|
| HF is a location?                     | yes                                  | no                                      |
| Linked to which level on the pyramid? | below the last level (Place/Village) | at the second level (Province/District) |

The Hera population data is stored as openIMIS Insuree/Family (depending on the fields).


### ORM mapping:

| Database table name            | Django Model             | Optional Comments                                                 |
|--------------------------------|--------------------------|-------------------------------------------------------------------|
| tblHeraHFIDsMapping            | HeraHFIDsMapping         | mapping Hera health facility IDs to openIMIS health facility IDs  |
| tblHeraLocationIDsMapping      | HeraLocationIDsMapping   | mapping Hera location IDs to openIMIS location IDs                |            
| tblHeraNotification            | HeraNotification         | /                                                                 |
| tblHeraSubscription            | HeraSubscription         | /                                                                 |
| ecrvs_HeraSubscriptionMutation | HeraSubscriptionMutation | /                                                                 |


### GraphQL Queries
* hera_notifications
* hera_subscriptions


### GraphQL Mutations
* create_hera_subscription
* delete_hera_subscription


### GraphQL Mutations
Rights required:
* gql_hera_subscription_search_perms: (default: `["124000"]`)
* gql_hera_subscription_create_perms: (default: `["124001"]`)
* gql_hera_subscription_delete_perms: (default: `["124002"]`)
* gql_hera_notification_search_perms: (default: `["125000"]`)


### Tests
To be added. Only tested manually with Postman.

### Various comments
As of January 2024, the Hera API is:
- not completely stable (when they have a new version, the responses sometimes change, even if the documentation is the same and the requests are the same)
- not consistent (the errors are sent in various ways - or sometimes nothing is returned at all -, depending on the endpoint. Various internal error codes are also returned, even though they look like HTTP status codes, but they are not)
