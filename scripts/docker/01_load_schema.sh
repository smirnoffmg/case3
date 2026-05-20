#!/bin/sh
# Strip `CREATE DATABASE` / `\connect` lines (the docker image already
# created $POSTGRES_DB) and pipe the rest of the DDL into psql.
set -eu

sed -e '/^CREATE DATABASE/d' -e '/^\\connect/d' /schema/data_model.sql \
  | psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
