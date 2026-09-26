# JOBBS — job search web app

A full-stack Flask site that wraps your LinkedIn scraper behind a login,
a filter UI (category, country, posting date, workplace type, result
count up to 50), a same-day results cache, and basic SEO/analytics hooks.
No paid APIs are used anywhere.

---

## 1. What's included

- **Auth**: email + password (hashed, never stored in plain text) with
  a verification email, and "Sign in with Google" (OAuth). One account
  per email address, whichever method is used first.
- **Database**: SQLite (`instance/jobbs.db`) — no external DB service
  needed. Tables: `users`, `search_cache`.
- **CSV export**: every signup also appends a row (name, email, signup
  date, verified flag, method — never a password) to
  `data/users_export.csv`, per your request for a CSV copy.
- **Scraper**: your `linkedin_harvest.py` logic, refactored into
  `app/scraper/linkedin_scraper.py` as a function that takes the UI's
  filters and runs in a background thread so the page doesn't freeze.
- **Same-day cache**: `search_cache` stores results per
  (keyword, country, date filter, workplace type, result count) per
  calendar day. A repeat of the same search on the same day is served
  instantly instead of re-scraping.
- **Security**: CSRF protection, rate limiting on auth and search
  endpoints, secure session cookies, security headers + HSTS via
  Flask-Talisman, a content-security-policy, password complexity rules,
  parameterized queries (SQLAlchemy ORM).
- **SEO**: per-page meta tags/Open Graph, `/robots.txt`, `/sitemap.xml`,
  a slot for the Google Search Console verification tag, and an
  optional Google Analytics snippet.
- **UI**: custom design ("JOBBS", navy/teal/amber palette, Fraunces +
  IBM Plex Sans), animated result cards, progress bar while a scrape
  runs, fully responsive.

## 2. Project layout

```
jobbs/
  app/
    auth/            registration, login, Google OAuth, email verification
    main/            landing page, dashboard, search API, job manager, SEO routes
    scraper/         your scraper logic + country/category/filter lists
    templates/        Jinja2 pages
    static/           css/js/logo
    models.py         User, SearchCache
    config.py         reads everything from .env
    extensions.py     Flask extension instances
  data/               users_export.csv lands here
  instance/           jobbs.db (SQLite) lands here
  wsgi.py             production entrypoint (gunicorn wsgi:app)
  run_dev.py          local dev entrypoint (python run_dev.py)
  requirements.txt
  Procfile            for Render/Railway/Heroku-style hosts
  .env.example        copy to .env and fill in
```

## 3. Run it locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in what you can — see section 4
python run_dev.py
```

Visit `http://127.0.0.1:5000`. Without SMTP configured, verification
links are printed to the terminal log instead of emailed, so you can
still test signup end-to-end locally. Without Google OAuth configured,
the "Continue with Google" button shows a friendly error instead of
crashing.

## 4. What YOU need to provide before going live

Everything below is free. Put the values in `.env` (copy from
`.env.example` first).

### a) A secret key
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste the output into `SECRET_KEY`.

### b) Google OAuth ("Sign in with Google")
1. Go to [console.cloud.google.com](https://console.cloud.google.com/) → create a project.
2. **APIs & Services → OAuth consent screen** → set it up (External, add your app name/logo, your email).
3. **APIs & Services → Credentials → Create credentials → OAuth client ID** → Application type **Web application**.
4. Under **Authorized redirect URIs**, add:
   `https://your-domain.com/auth/google/callback` (and `http://127.0.0.1:5000/auth/google/callback` for local testing).
5. Copy the **Client ID** and **Client secret** into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

### c) Email sending (for verification links)
Simplest free option — Gmail SMTP with an App Password:
1. Turn on 2-Step Verification on the Gmail account you'll send from.
2. Create an App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Put the Gmail address in `MAIL_USERNAME` and the 16-character app password in `MAIL_PASSWORD`.
(Any other SMTP provider's free tier — e.g. Brevo, Mailjet — works too; just change `MAIL_SERVER`/`MAIL_PORT`.)

### d) Google Search Console (SEO)
1. Go to [search.google.com/search-console](https://search.google.com/search-console) → **Add property** → enter your domain.
2. Choose the **HTML tag** verification method — it gives you a `content="..."` value.
3. Paste just that value into `GOOGLE_SITE_VERIFICATION` in `.env`, redeploy, then click **Verify** in Search Console.
4. Once verified, go to **Sitemaps** in Search Console and submit:
   `https://your-domain.com/sitemap.xml`

### e) Google Analytics (optional)
Create a free GA4 property at [analytics.google.com](https://analytics.google.com/), copy the
Measurement ID (`G-XXXXXXXXXX`) into `GOOGLE_ANALYTICS_ID`.

### f) Your domain
Set `SITE_URL` in `.env` to your real domain once you have one — it's
used to build absolute URLs for the sitemap and OAuth callback.

## 5. Deploying (no paid tier required)

Any host that runs Python + gunicorn works. Render's free web service
is the simplest:

1. Push this project to a GitHub repo (the `.gitignore` already keeps
   `.env`, the database, and the CSV out of git).
2. On [render.com](https://render.com) → **New → Web Service** → connect the repo.
3. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn wsgi:app --workers 1 --threads 4 --timeout 120`
   (the `Procfile` already encodes this if your host reads it automatically).
4. Add every variable from your `.env` in the host's **Environment**
   settings (do not upload the `.env` file itself).
5. Because search results and job-progress tracking are kept in this
   process's memory (see section 6), keep it to **one web instance /
   one worker**. If you outgrow that, swap the in-memory job store in
   `app/main/job_manager.py` for Celery + Redis or RQ — the rest of the
   app already calls it through a small, swappable interface.
6. SQLite's file (`instance/jobbs.db`) needs a persistent disk — most
   free tiers reset the filesystem on redeploy, so attach a small
   persistent volume if your host offers one (Render's free tier does
   not persist disk across deploys; Railway's does). If you need
   guaranteed persistence on a host without one, swap
   `DATABASE_URL` for a free-tier Postgres instance (e.g. Supabase,
   Neon, Railway Postgres) — no code changes needed beyond that URL,
   since SQLAlchemy handles both.

## 6. Things worth knowing

- **Legal note on scraping**: this reads LinkedIn's public,
  unauthenticated job-search pages (no login, no private data). Scraping
  LinkedIn is against LinkedIn's User Agreement, and LinkedIn actively
  rate-limits/blocks scraping traffic and can change its HTML at any
  time, which will eventually break the CSS selectors in
  `linkedin_scraper.py`. Keep volume modest and treat this as a personal
  or internal tool rather than a public product scraping LinkedIn at
  scale.
- **In-memory job queue**: search progress is tracked in the running
  process's memory, which is why the app is set up for a single
  worker. This keeps the whole stack free/simple; it's the one thing to
  revisit if you need to scale beyond one instance.
- **Country filter**: countries are passed to LinkedIn's search as a
  plain place name (no hardcoded internal IDs, which are undocumented
  and change silently) — add or remove entries in
  `app/scraper/countries.py`.
- **Result cap**: hard-capped at 50 per search (`SCRAPE_MAX_RESULTS_CAP`
  in `.env`) as requested.
- **CSV vs database**: `users_export.csv` is a convenience export only;
  the real source of truth (with hashed passwords) is `instance/jobbs.db`.

## 7. Quick checklist before you consider this "live"

- [ ] Real `SECRET_KEY` set
- [ ] Google OAuth client ID/secret set, redirect URI matches your domain
- [ ] SMTP credentials set (or accepted that verification links log to console)
- [ ] Domain set in `SITE_URL`
- [ ] Deployed with persistent storage for `instance/jobbs.db`
- [ ] Search Console verified + sitemap submitted
- [ ] Tried the full flow yourself: register → verify email → log in → search → see cached instant re-search
