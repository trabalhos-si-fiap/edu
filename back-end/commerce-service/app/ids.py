import uuid

import uuid_utils


def new_uuid() -> uuid.UUID:
    """Gera um UUIDv7 (ordenado no tempo) como `uuid.UUID` da stdlib.

    Mesma função de `legacy/app/core/ids.py`. Id ordenado no tempo preserva
    a localidade de inserção no índice B-tree do Postgres; UUIDv4 aleatório
    fragmenta o índice a cada insert.
    """
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
