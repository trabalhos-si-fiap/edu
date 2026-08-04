#!/bin/bash
# Creates the dedicated test database on first Postgres boot.
# Runs once (docker-entrypoint-initdb.d scripts execute only when the data
# volume is empty). To recreate the test DB on an existing volume, either
# wipe the `postgres_data` volume or run `CREATE DATABASE edu_test` manually.
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE edu_test;
    GRANT ALL PRIVILEGES ON DATABASE edu_test TO $POSTGRES_USER;
EOSQL
