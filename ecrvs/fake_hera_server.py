import uuid


def fake_hera_insuree():
    return {
        "firstName": "TEST1",
        "lastName": "TEST1",
        "dob": "2022-08-20",
        "gender": "SEX::MALE",
        "mobileNumber": "082582",
        "occupation": None,
        "isLocal": "false",
        "residentialProvince": "PROVINCE::SEKONG",
        "residentialDistrict": "DISTRICT::KALEUM",
        "residentialVillage": "PLACE::ACHING_AKEO",
        "residentialAlley": None,
        "residentialHouseNumber": None,
        "motherFirstName": "Brandie",
        "motherLastName": "Barton",
        "registrationProvince": "PROVINCE::BOKEO",
        "registrationDistrict": "DISTRICT::HUOIXAI",
        "registrationVillage": "PLACE::XOT",
        "fatherFirstName": "Larry",
        "fatherLastName": "Hayes",
        "birthProvince": "PROVINCE::SEKONG",
        "birthDistrict": "DISTRICT::KALEUM",
        "birthVillage": "PLACE::ACHING_AKEO",
        "healthFacility": None,
        "placeOfBirthType": "BIRTH_LOCATION_TYPE::HOME",
        "height": None,
        "weight": None,
        "certificateNumber": "BC0000001676",
    }


def fake_hera_auth():
    token = """
    eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJPMEVqWFZvTU1hMFlOcVBNajhnRWdXSk8
    dfS1NiVzh5Mm8wcUR6QjdoeVkwIn0.eyJleHAiOjE2OTUxNDY0NDYsImlhdCI6MTY5NTExNzY0NiwianRpIjoiODM
    wMTUwNGUtZWIwYy00OWEwLTk1OGMtZTdlMDMwMTM4YzlmIiwiaXNzIjoiaHR0cHM6Ly9hdXRoLmxhby10ZXN0MDMud2Nj
    LWhlcmEuY29tL3JlYWxtcy9IZXJhIiwic3ViIjoiZTE2ZGJhOGYtMWIyMy00MmY5LTkwODYtMGZlYjhlOGViOGJiIiwidH
    lwIjoiQmVhcmVyIiwiYXpwIjoiaGVyYS1tMm0iLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsiZGVmYXVsdC1yb2xlcy1oZ
    XJhIl19LCJzY29wZSI6InByb2ZpbGUgZW1haWwgcmVnaXN0cmF0aW9uOnJlYWQiLCJjbGllbnRIb3N0IjoiNjIuNzIuOTcuMjE5
    IiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJjbGllbnRJZCI6ImhlcmEtbTJtIiwicHJlZmVycmVkX3VzZXJuYW1lIjoic2VydmljZS
    1hY2NvdW50LWhlcmEtbTJtIiwiY2xpZW50QWRkcmVzcyI6IjYyLjcyLjk3LjIxOSJ9.Ljrg4JjJujAkJ8v11pULggID30e_YOgWIdZ29WL
    xHE0PgtnzzD_3zUum5HL6zkl4_8c5I0EZsOZJR-fifePZ9Fey9dGk-yFx-HORGPXP6K6FBX_rPmSgiFI3lnjMJpTxkT1CSulxRJKYrDkXQtw-
    Kg9ATTJOxGAafQXP2jp167Q",
    """
    return {
        "access_token": token,
        "expires_in": 28800,
        "refresh_expires_in": 0,
        "token_type": "Bearer",
        "not-before-policy": 0,
        "scope": "profile email registration:read"
    }


def fake_hera_subscription():
    random_uuid = str(uuid.uuid4())
    return {
        "uuid": random_uuid,
        "topic": "LifeEventTopic",
        "protocol": None,
        "address": "https://testwcc.requestcatcher.com",
        "policy": None,
        "active": None,
    }