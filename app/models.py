import json
import secrets
from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # null if Google-only account
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw_password)


class SearchCache(db.Model):
    """
    Caches a scraped result set for a given (keyword, country, date filter,
    workplace type, result count) combination, keyed also by the calendar
    day it was scraped on. If another user repeats the same search on the
    same day, results are served instantly from here instead of re-scraping.
    """
    __tablename__ = "search_cache"

    id = db.Column(db.Integer, primary_key=True)
    search_key = db.Column(db.String(400), nullable=False, index=True)
    keyword = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(120), nullable=False)
    date_posted = db.Column(db.String(20), nullable=False)   # r86400 / r604800 / r2592000 / ""
    workplace_type = db.Column(db.String(20), nullable=False)  # any / onsite / remote / hybrid
    result_count = db.Column(db.Integer, nullable=False)

    scraped_on = db.Column(db.Date, default=date.today, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    results_json = db.Column(db.Text, nullable=False)  # JSON list of job dicts
    total_jobs = db.Column(db.Integer, default=0)

    def get_results(self):
        return json.loads(self.results_json)

    def set_results(self, jobs: list):
        self.results_json = json.dumps(jobs, ensure_ascii=False)
        self.total_jobs = len(jobs)


def new_token() -> str:
    return secrets.token_urlsafe(32)
