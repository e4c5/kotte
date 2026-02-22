"""Import router module (renamed to avoid Python import conflict)."""

from app.api.v1 import csv_importer

router = csv_importer.router

