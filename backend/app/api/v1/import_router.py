"""Import router module (renamed to avoid Python import conflict)."""

from app.api.v1 import import_csv

router = import_csv.router

