#!/usr/bin/env bash
set -euo pipefail

operation="${1:-}"
root="infrastructure/terraform/customer-workload-serverless-api"

require() { [[ -n "${!1:-}" ]] || { echo "$1 is required" >&2; exit 2; }; }
for name in AWS_REGION EXPECTED_AWS_ACCOUNT_ID TF_STATE_BUCKET TF_LOCK_TABLE \
  DAVDEPLOY_CUSTOMER_CONNECTION_ID DAVDEPLOY_EXECUTION_RUN_ID \
  DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256; do
  require "$name"
done

connection_id="$DAVDEPLOY_CUSTOMER_CONNECTION_ID"
service_name="${DAVDEPLOY_CUSTOMER_SERVICE_NAME:-davdeploy-${connection_id}-api}"
artifact="/tmp/davdeploy-serverless-${DAVDEPLOY_EXECUTION_RUN_ID}.zip"
plan_file="/tmp/davdeploy-serverless-${DAVDEPLOY_EXECUTION_RUN_ID}.tfplan"

cleanup() { rm -f "$artifact" "$plan_file"; }
trap cleanup EXIT

aws_args=()
[[ -z "${AWS_PROFILE:-}" ]] || aws_args+=(--profile "$AWS_PROFILE")

download_artifact() {
  aws s3 cp "${DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI}" "$artifact" --only-show-errors
  echo "${DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256}  ${artifact}" | shasum -a 256 --check --status
}

tf_init() {
  terraform -chdir="$root" init -input=false -reconfigure \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="key=davdeploy/customer/${connection_id}/serverless-api.tfstate" \
    -backend-config="dynamodb_table=${TF_LOCK_TABLE}" \
    -backend-config="region=${AWS_REGION}"
}

tf_vars=(
  "-var=region=${AWS_REGION}"
  "-var=expected_account_id=${EXPECTED_AWS_ACCOUNT_ID}"
  "-var=connection_id=${connection_id}"
  "-var=plan_digest=${DAVDEPLOY_CUSTOMER_PLAN_DIGEST:?DAVDEPLOY_CUSTOMER_PLAN_DIGEST is required}"
  "-var=service_name=${service_name}"
  "-var=artifact_path=${artifact}"
)

case "$operation" in
  plan)
    download_artifact; tf_init
    terraform -chdir="$root" plan -input=false -out="$plan_file" "${tf_vars[@]}"
    ;;
  apply)
    download_artifact; tf_init
    terraform -chdir="$root" apply -input=false -auto-approve "${tf_vars[@]}"
    ;;
  health)
    tf_init
    endpoint="$(terraform -chdir="$root" output -raw api_endpoint)"
    curl --fail --silent --show-error --max-time 15 "${endpoint}/" >/dev/null
    ;;
  destroy)
    download_artifact; tf_init
    terraform -chdir="$root" destroy -input=false -auto-approve "${tf_vars[@]}"
    ;;
  verify-cleanup)
    tf_init
    [[ -z "$(terraform -chdir="$root" state list)" ]]
    ;;
  *)
    echo "allowed operations: plan, apply, health, destroy, verify-cleanup" >&2
    exit 2
    ;;
esac
