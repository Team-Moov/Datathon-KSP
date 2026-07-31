import uuid

NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def to_uuid(raw_id):
    if raw_id is None or raw_id == "":
        return None
    return uuid.uuid5(NAMESPACE, raw_id)