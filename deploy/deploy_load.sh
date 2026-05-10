#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="image-lab-494712"
REGION="us-central1"
BUCKET_NAME="image-lab-bucket-17662"
SA="coursera-etl-sa@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud functions deploy load-to-bigquery \
  --gen2 --project="${PROJECT_ID}" --region="${REGION}" \
  --runtime=python311 --source=./load_function \
  --entry-point=load_to_bigquery \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=${BUCKET_NAME}" \
  --service-account="${SA}" \
  --memory=512Mi --timeout=540s \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BQ_DATASET=coursera,BQ_TABLE=courses,BQ_LOCATION=US,GCS_PREFIX=coursera/"
