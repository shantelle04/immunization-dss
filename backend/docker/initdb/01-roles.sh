#!/bin/bash
# Runs once, when the database volume is first created. The app and the test suite get separate roles.
set -euo pipefail

for var in POSTGRES_PASSWORD DB_PASSWORD DB_TEST_PASSWORD; do
  value="${!var}"
  if [[ ${#value} -lt 16 || "$value" == changeme* ]]; then
    echo "initdb: $var must be at least 16 characters and not the .env.example placeholder" >&2
    exit 1
  fi
done
if [[ "$DB_USER" == "$DB_TEST_USER" ]]; then
  echo "initdb: DB_USER and DB_TEST_USER must be different roles" >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  -v app_user="$DB_USER" -v app_password="$DB_PASSWORD" -v app_db="$DB_NAME" \
  -v test_user="$DB_TEST_USER" -v test_password="$DB_TEST_PASSWORD" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';
CREATE ROLE :"test_user" LOGIN CREATEDB PASSWORD :'test_password';
CREATE DATABASE :"app_db" OWNER :"app_user";
SQL
