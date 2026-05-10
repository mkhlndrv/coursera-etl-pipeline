# Pulls Coursera courses, writes NDJSON to GCS.
import os
import json
import time
import logging
from datetime import datetime, timezone

import functions_framework
import requests
from google.cloud import storage

log = logging.getLogger("extract_coursera")
logging.basicConfig(level=logging.INFO)

BASE_URL = "https://api.coursera.org/api/courses.v1"

FIELDS = ",".join([
    "name", "slug", "description", "workload", "photoUrl",
    "partnerIds", "instructorIds", "specializations",
    "primaryLanguages", "subtitleLanguages", "partnerLogo",
    "certificates", "courseType", "categories",
])

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Coursera-ETL/1.0)",
}

PROJECT_ID  = os.environ["PROJECT_ID"]
BUCKET_NAME = os.environ["BUCKET_NAME"]
GCS_PREFIX  = os.environ.get("GCS_PREFIX", "coursera")
PAGE_SIZE   = int(os.environ.get("PAGE_SIZE", "100"))
MAX_PAGES   = int(os.environ.get("MAX_PAGES", "3"))   # 0 = no cap
SLEEP_SEC   = float(os.environ.get("SLEEP_SEC", "0.3"))


def fetch_page(start, limit):
    r = requests.get(
        BASE_URL,
        params={"start": start, "limit": limit, "fields": FIELDS},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_all():
    out, start, page = [], 0, 0
    while True:
        data = fetch_page(start, PAGE_SIZE)
        elements = data.get("elements", [])
        out.extend(elements)
        page += 1
        log.info("page=%d fetched=%d running=%d", page, len(elements), len(out))

        nxt = data.get("paging", {}).get("next")
        if not nxt or not elements:
            break
        if MAX_PAGES and page >= MAX_PAGES:
            break
        start = int(nxt)
        time.sleep(SLEEP_SEC)
    return out


def _join(xs):
    # flatten arrays so BQ autodetect treats them as strings
    return "|".join(xs or [])


def to_row(c):
    slug = c.get("slug")
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "slug": slug,
        "url": f"https://www.coursera.org/learn/{slug}" if slug else None,
        "description": c.get("description"),
        "workload": c.get("workload"),
        "courseType": c.get("courseType"),
        "primaryLanguages":  _join(c.get("primaryLanguages")),
        "subtitleLanguages": _join(c.get("subtitleLanguages")),
        "partnerIds":        _join(c.get("partnerIds")),
        "instructorIds":     _join(c.get("instructorIds")),
        "specializations":   _join(c.get("specializations")),
        "certificates":      _join(c.get("certificates")),
        "categories":        _join(c.get("categories")),
        "photoUrl": c.get("photoUrl"),
        "partnerLogo": c.get("partnerLogo"),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


@functions_framework.http
def extract_coursera(request):
    rows = [to_row(c) for c in fetch_all()]
    ndjson = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    object_name = f"{GCS_PREFIX}/courses_{ts}.ndjson"

    storage.Client(project=PROJECT_ID) \
        .bucket(BUCKET_NAME) \
        .blob(object_name) \
        .upload_from_string(ndjson, content_type="application/x-ndjson")

    msg = f"wrote {len(rows)} rows to gs://{BUCKET_NAME}/{object_name}"
    log.info(msg)
    return (msg, 200)
