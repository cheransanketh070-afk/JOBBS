import hashlib
from datetime import date

from flask import (
    Blueprint, render_template, request, jsonify, current_app, Response, url_for
)
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import SearchCache
from app.scraper.countries import COUNTRIES, WORKPLACE_TYPES, DATE_POSTED, POPULAR_CATEGORIES
from app.scraper.linkedin_scraper import run_search
from app.main.job_manager import start_job, get_job, cancel_job

main_bp = Blueprint("main", __name__)


def _make_search_key(keyword, country, date_key, workplace_key, max_results) -> str:
    raw = f"{keyword.strip().lower()}|{country.strip().lower()}|{date_key}|{workplace_key}|{max_results}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        countries=COUNTRIES,
        workplace_types=WORKPLACE_TYPES,
        date_posted=DATE_POSTED,
        categories=POPULAR_CATEGORIES,
    )


@main_bp.route("/api/search", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def api_search():
    payload = request.get_json(silent=True) or {}

    keyword = (payload.get("keyword") or "").strip()
    country = (payload.get("country") or "Worldwide").strip()
    date_key = payload.get("date_posted") or "any"
    workplace_key = payload.get("workplace_type") or "any"
    try:
        max_results = int(payload.get("max_results") or 25)
    except (TypeError, ValueError):
        max_results = 25

    if not keyword:
        return jsonify({"error": "Please enter a job category or keyword."}), 400
    if len(keyword) > 100:
        return jsonify({"error": "Keyword is too long."}), 400
    if country not in COUNTRIES:
        return jsonify({"error": "Unknown country."}), 400
    if date_key not in DATE_POSTED:
        return jsonify({"error": "Unknown date filter."}), 400
    if workplace_key not in WORKPLACE_TYPES:
        return jsonify({"error": "Unknown workplace type."}), 400

    cap = current_app.config.get("SCRAPE_MAX_RESULTS_CAP", 50)
    max_results = max(5, min(max_results, cap))

    search_key = _make_search_key(keyword, country, date_key, workplace_key, max_results)

    cached = SearchCache.query.filter_by(
        search_key=search_key, scraped_on=date.today()
    ).order_by(SearchCache.created_at.desc()).first()

    if cached:
        return jsonify({
            "cached": True,
            "jobs": cached.get_results(),
            "total": cached.total_jobs,
            "scraped_on": cached.scraped_on.isoformat(),
        })

    concurrency = current_app.config.get("SCRAPE_CONCURRENCY", 5)
    job_id = start_job(
        run_search,
        keyword=keyword,
        country=country,
        date_posted_key=date_key,
        workplace_key=workplace_key,
        max_results=max_results,
        concurrency=concurrency,
    )

    return jsonify({
        "cached": False,
        "job_id": job_id,
        "meta": {
            "search_key": search_key,
            "keyword": keyword,
            "country": country,
            "date_posted": date_key,
            "workplace_type": workplace_key,
            "max_results": max_results,
        },
    })


@main_bp.route("/api/search/status/<job_id>")
@login_required
def api_search_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404

    if job["status"] == "running":
        return jsonify({
            "status": "running",
            "progress": job["progress"],
            "total": job["total"],
        })

    if job["status"] == "error":
        return jsonify({"status": "error", "error": job["error"]}), 200

    # done — persist to cache the first time it's fetched
    meta_key = request.args.get("search_key")
    jobs_result = job["result"] or []

    if meta_key:
        exists = SearchCache.query.filter_by(
            search_key=meta_key, scraped_on=date.today()
        ).first()
        if not exists:
            entry = SearchCache(
                search_key=meta_key,
                keyword=request.args.get("keyword", ""),
                country=request.args.get("country", ""),
                date_posted=request.args.get("date_posted_key", "any"),
                workplace_type=request.args.get("workplace_key", "any"),
                result_count=len(jobs_result),
            )
            entry.set_results(jobs_result)
            db.session.add(entry)
            db.session.commit()

    return jsonify({"status": "done", "jobs": jobs_result, "total": len(jobs_result)})


@main_bp.route("/api/search/cancel/<job_id>", methods=["POST"])
@login_required
def api_search_cancel(job_id):
    cancel_job(job_id)
    return jsonify({"cancelled": True})


# --- SEO -------------------------------------------------------------

@main_bp.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /dashboard",
        "Disallow: /api/",
        f"Sitemap: {url_for('main.sitemap_xml', _external=True)}",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@main_bp.route("/sitemap.xml")
def sitemap_xml():
    pages = [
        url_for("main.index", _external=True),
        url_for("auth.login", _external=True),
        url_for("auth.register", _external=True),
    ]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml.append(f"<url><loc>{p}</loc></url>")
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")
