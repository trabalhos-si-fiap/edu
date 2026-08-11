import uuid

import uuid_utils


def new_uuid() -> uuid.UUID:
    """UUIDv7 (ordenado no tempo) como `uuid.UUID` da stdlib.

    Preserva a localidade de inserção no índice B-tree do Postgres; UUIDv4
    aleatório fragmenta o índice a cada insert.
    """
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
