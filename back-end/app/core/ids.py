import uuid

import uuid_utils


def new_uuid() -> uuid.UUID:
    """Generate a time-ordered UUIDv7 as a stdlib uuid.UUID.

    Time-ordered UUIDs preserve insertion locality in the Postgres B-tree,
    avoiding the fragmentation caused by random UUIDv4 primary keys.
    """
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
