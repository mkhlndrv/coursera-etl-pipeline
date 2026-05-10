# coursera-etl-pipeline

Daily ETL on GCP. Pulls the Coursera course catalog, writes NDJSON to GCS,
loads it into BigQuery. Two Cloud Functions plus a Scheduler job.

```
Scheduler -> extract-coursera -> GCS -> load-to-bigquery -> BigQuery
```

## Config

- project: `image-lab-494712`
- region: `us-central1`
- bucket: `image-lab-bucket-17662`, prefix `coursera/`
- BigQuery: `coursera.courses` (US)
- service account: `coursera-etl-sa`
- schedule: `0 6 * * *` Europe/Madrid

## Setup

```bash
gcloud auth login
gcloud config set project image-lab-494712

gcloud services enable \
  cloudfunctions.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  eventarc.googleapis.com pubsub.googleapis.com cloudscheduler.googleapis.com \
  storage.googleapis.com bigquery.googleapis.com
```

The bucket must exist and its region must match the function region.
`us-central1` function + `US` multi-region bucket works.

Service account and roles:

```bash
PROJECT_ID=image-lab-494712
SA=coursera-etl-sa@${PROJECT_ID}.iam.gserviceaccount.com

gcloud iam service-accounts create coursera-etl-sa \
  --project="${PROJECT_ID}" --display-name="Coursera ETL pipeline"

for ROLE in \
  roles/storage.objectAdmin \
  roles/storage.admin \
  roles/bigquery.dataEditor \
  roles/bigquery.jobUser \
  roles/eventarc.eventReceiver \
  roles/run.invoker \
  roles/cloudfunctions.invoker
do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA}" --role="${ROLE}"
done
```

`storage.admin` is needed because the Eventarc trigger validation calls
`storage.buckets.get`, which `storage.objectAdmin` does not cover.

The default Cloud Build compute SA also needs the build role, otherwise
function deploys prompt and abort:

```bash
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"
```

Eventarc on GCS needs the GCS service agent to have `pubsub.publisher`.
Bootstrap the service identities first:

```bash
gcloud beta services identity create --service=eventarc.googleapis.com --project="${PROJECT_ID}"
gcloud beta services identity create --service=pubsub.googleapis.com   --project="${PROJECT_ID}"
```

Force-create the GCS service agent (it doesn't always exist until you
call the storage API once):

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://storage.googleapis.com/storage/v1/projects/${PROJECT_ID}/serviceAccount"
```

Then bind `pubsub.publisher` to it. Note the `tr -d` — `gcloud storage
service-agent` prints leading whitespace that breaks the IAM call:

```bash
GCS_SA="$(gcloud storage service-agent --project="${PROJECT_ID}" | tr -d '[:space:]')"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${GCS_SA}" --role="roles/pubsub.publisher"
```

## Deploy

```bash
bash deploy/deploy_extract.sh
bash deploy/deploy_load.sh
bash deploy/create_scheduler.sh
```

If `deploy_load.sh` fails the first time with a 403 on `storage.buckets.get`,
wait ~30s for IAM to propagate and run it again.

## Run

```bash
gcloud scheduler jobs run coursera-etl-daily --location=us-central1
```

## Verify

```bash
gsutil ls gs://image-lab-bucket-17662/coursera/
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) FROM `image-lab-494712.coursera.courses`'
```

## Env vars

`extract-coursera`:

- `PROJECT_ID`, `BUCKET_NAME` — required
- `GCS_PREFIX` — default `coursera`
- `PAGE_SIZE` — default `100`
- `MAX_PAGES` — default `3` (~300 rows). Set `0` for the full catalog (~21k).
- `SLEEP_SEC` — default `0.3`

`load-to-bigquery`:

- `PROJECT_ID` — required
- `BQ_DATASET` / `BQ_TABLE` / `BQ_LOCATION` — default `coursera` / `courses` / `US`
- `GCS_PREFIX` — default `coursera/`

## Notes

- Each load uses `WRITE_TRUNCATE`, so the table reflects the latest file only.
- Schema is autodetected; expect drift if Coursera changes fields.
