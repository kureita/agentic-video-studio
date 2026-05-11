#!/usr/bin/env bash
# Apply CORS configuration to the Kureita S3 bucket so the browser can load
# presigned media URLs with crossOrigin="anonymous" (required by Remotion's
# client-side renderer).
#
# Run once per environment (or whenever scripts/s3-cors.json changes).
#
# Usage:
#   AWS_PROFILE=kureita ./scripts/configure-s3-cors.sh
#   ./scripts/configure-s3-cors.sh kureita ap-south-1
#
set -euo pipefail

BUCKET="${1:-${S3_BUCKET:-kureita}}"
REGION="${2:-${AWS_REGION:-ap-south-1}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/s3-cors.json"

if ! command -v aws >/dev/null 2>&1; then
    echo "error: aws CLI not found in PATH" >&2
    exit 1
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "error: missing ${CONFIG_FILE}" >&2
    exit 1
fi

echo "Applying CORS to s3://${BUCKET} (region=${REGION})"
aws s3api put-bucket-cors \
    --bucket "${BUCKET}" \
    --region "${REGION}" \
    --cors-configuration "file://${CONFIG_FILE}"

echo "Current CORS configuration:"
aws s3api get-bucket-cors --bucket "${BUCKET}" --region "${REGION}"
