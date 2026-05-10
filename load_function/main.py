# Triggered by GCS object.finalize. Loads the new NDJSON file into BigQuery.
import os
import logging

import functions_framework
from google.cloud import bigquery

log = logging.getLogger("load_to_bq")
logging.basicConfig(level=logging.INFO)

PROJECT_ID = os.environ["PROJECT_ID"]
DATASET    = os.environ.get("BQ_DATASET", "coursera")
TABLE      = os.environ.get("BQ_TABLE", "courses")
LOCATION   = os.environ.get("BQ_LOCATION", "US")
PREFIX     = os.environ.get("GCS_PREFIX", "coursera/")


@functions_framework.cloud_event
def load_to_bigquery(cloud_event):
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]

    # ignore anything that isn't one of our NDJSON drops
    if not name.startswith(PREFIX) or not name.endswith(".ndjson"):
        log.info("skipping %s", name)
        return

    uri = f"gs://{bucket}/{name}"
    table_id = f"{PROJECT_ID}.{DATASET}.{TABLE}"

    bq = bigquery.Client(project=PROJECT_ID)
    bq.create_dataset(bigquery.Dataset(f"{PROJECT_ID}.{DATASET}"), exists_ok=True)

    job = bq.load_table_from_uri(
        uri,
        table_id,
        location=LOCATION,
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            autodetect=True,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    )
    job.result()
    log.info("loaded %d rows from %s into %s", job.output_rows, uri, table_id)
