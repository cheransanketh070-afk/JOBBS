"""
The primary, secure record of accounts lives in the SQL database (models.User),
with hashed passwords. The user also asked for signup data to additionally be
kept in a CSV. To avoid ever putting credentials in a flat file, this export
only ever contains non-secret fields (name, email, signup date, verified
status) — never the password or its hash.
"""
import csv
import os
from pathlib import Path
from filelock import FileLock  # type: ignore

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "users_export.csv"
LOCK_PATH = str(CSV_PATH) + ".lock"

FIELDS = ["id", "name", "email", "signup_date", "is_verified", "signup_method"]


def append_user_to_csv(user):
    DATA_DIR.mkdir(exist_ok=True)
    file_exists = CSV_PATH.exists()

    with FileLock(LOCK_PATH, timeout=5):
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "signup_date": user.created_at.isoformat() if user.created_at else "",
                    "is_verified": user.is_verified,
                    "signup_method": "google" if user.google_id else "password",
                }
            )
