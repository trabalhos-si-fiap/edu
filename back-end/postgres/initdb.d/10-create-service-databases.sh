#!/bin/bash
# Cria um banco por serviço, além do banco do legacy criado pelo POSTGRES_DB.
# Idempotente: rodar de novo num volume já inicializado não falha.
set -euo pipefail

DATABASES="auth_db learning_db commerce_db notification_db analytics_db chatbot_db"
DATABASES="$DATABASES auth_test learning_test commerce_test notification_test analytics_test chatbot_test"

for db in $DATABASES; do
  echo "Garantindo banco '$db'..."
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    SELECT 'CREATE DATABASE $db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done

echo "Bancos dos serviços prontos"
