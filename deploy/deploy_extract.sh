#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="image-lab-494712"
REGION="us-central1"
BUCKET_NAME="image-lab-bucket-17662"
SA="coursera-etl-sa@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud functions deploy extract-coursera \
  --gen2 --project="${PROJECT_ID}" --region="${REGION}" \
  --runtime=python311 --source=./extract_function \
  --entry-point=extract_coursera \
  --trigger-http --no-allow-unauthenticated \
  --service-account="${SA}" \
  --memory=512Mi --timeout=540s \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BUCKET_NAME=${BUCKET_NAME},GCS_PREFIX=coursera,PAGE_SIZE=100,MAX_PAGES=3"
