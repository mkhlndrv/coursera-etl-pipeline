#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="image-lab-494712"
REGION="us-central1"
SA="coursera-etl-sa@${PROJECT_ID}.iam.gserviceaccount.com"
FN_URL="$(gcloud functions describe extract-coursera --gen2 \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --format='value(serviceConfig.uri)')"
gcloud scheduler jobs create http coursera-etl-daily \
  --project="${PROJECT_ID}" --location="${REGION}" \
  --schedule="0 6 * * *" --time-zone="Europe/Madrid" \
  --uri="${FN_URL}" --http-method=POST \
  --oidc-service-account-email="${SA}" \
  --oidc-token-audience="${FN_URL}"
