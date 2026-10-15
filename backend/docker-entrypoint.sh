#!/bin/sh
set -e
sh scripts/ensure-db.sh
exec python -m app.main
