#!/usr/bin/env bash
set -euo pipefail

operation="${1:-}"
root="infrastructure/terraform/customer-workload-serverless-api"

require() {
  local name="$1"
  [[ -n "${!name:-}" ]] || { echo "$name is required" >&2; exit 2; }
}

for name in AWS_REGION EXPECTED_AWS_ACCOUNT_ID TF_STATE_BUCKET TF_LOCK_TABLE \
  DAVDEPLOY_CUSTOMER_CONNECTION_ID DAVDEPLOY_CUSTOMER_PROJECT_ID DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN \
  DAVDEPLOY_EXTERNAL_ID_SECRET_ARN DAVDEPLOY_EXECUTION_RUN_ID \
  DAVDEPLOY_EXECUTION_RESULT_S3_URI DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI \
  DAVDEPLOY_CUSTOMER_PLAN_DIGEST; do
  require "$name"
done

case "${1:-}" in
  plan|apply-saved-plan) saved_plan_kind="apply" ;;
  destroy-plan|destroy-saved-plan) saved_plan_kind="destroy" ;;
  health|verify-cleanup) saved_plan_kind="apply" ;;
  *)
    echo "allowed operations: plan, apply-saved-plan, health, destroy-plan, destroy-saved-plan, verify-cleanup" >&2
    exit 2
    ;;
esac

connection_id="$DAVDEPLOY_CUSTOMER_CONNECTION_ID"
project_id="$DAVDEPLOY_CUSTOMER_PROJECT_ID"
run_id="$DAVDEPLOY_EXECUTION_RUN_ID"
project_scope="${connection_id}:${project_id}"
project_suffix="$(printf '%s' "$project_scope" | shasum -a 256 | awk '{print substr($1, 1, 32)}')"
service_name="davdeploy-${project_suffix}-api"
resolved_inputs_json="${DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON:-}"
[[ -n "$resolved_inputs_json" ]] || resolved_inputs_json='{}'
uploads_scope="${connection_id}:${project_id}:${AWS_REGION}"
uploads_suffix="$(printf '%s' "$uploads_scope" | shasum -a 256 | awk '{print substr($1, 1, 20)}')"
expected_uploads_bucket="davdeploy-${EXPECTED_AWS_ACCOUNT_ID}-${AWS_REGION}-${uploads_suffix}"
result_uri="$DAVDEPLOY_EXECUTION_RESULT_S3_URI"
saved_plan_uri="$DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"
artifact_uri="${DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI:-}"
artifact_sha256="${DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256:-}"
saved_plan_sha256="${DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256:-}"
artifact="/tmp/davdeploy-serverless-${connection_id}-${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}.zip"
plan_file="/tmp/davdeploy-serverless-${run_id}.tfplan"
result_file="/tmp/davdeploy-serverless-${run_id}-result.json"
credentials_file="/tmp/davdeploy-serverless-${run_id}.credentials"
lambda_error="/tmp/davdeploy-serverless-${run_id}-lambda-check.err"
customer_profile="davdeploy-customer"

[[ "$EXPECTED_AWS_ACCOUNT_ID" =~ ^[0-9]{12}$ ]] || { echo "Expected AWS account ID is invalid" >&2; exit 2; }
[[ "$AWS_REGION" =~ ^[a-z]{2}(-gov|-cn)?-[a-z]+-[0-9]+$ ]] || { echo "AWS region is invalid" >&2; exit 2; }
[[ "$DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN" =~ ^arn:aws(-us-gov|-cn)?:iam::${EXPECTED_AWS_ACCOUNT_ID}:role/[A-Za-z0-9+=,.@_/-]+$ ]] || {
  echo "Customer execution role must belong to the expected AWS account" >&2; exit 2;
}
[[ "$TF_STATE_BUCKET" =~ ^[A-Za-z0-9.-]{3,63}$ ]] || { echo "Terraform state bucket is invalid" >&2; exit 2; }
[[ "$TF_LOCK_TABLE" =~ ^[A-Za-z0-9_.-]{3,255}$ ]] || { echo "Terraform lock table name is invalid" >&2; exit 2; }
[[ "$connection_id" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || { echo "Customer connection identifier is invalid" >&2; exit 2; }
[[ "$project_id" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || { echo "Customer project identifier is invalid" >&2; exit 2; }
[[ "$run_id" =~ ^[A-Za-z0-9_-]{1,80}$ ]] || { echo "Execution run identifier is invalid" >&2; exit 2; }
[[ "$service_name" =~ ^[A-Za-z][A-Za-z0-9_-]{0,56}$ ]] || { echo "Customer service name is invalid" >&2; exit 2; }
[[ "$DAVDEPLOY_CUSTOMER_PLAN_DIGEST" =~ ^[a-f0-9]{64}$ ]] || { echo "Customer plan digest must be a SHA-256 digest" >&2; exit 2; }
if ! jq -e 'type == "object" and all(keys[]; . == "uploads_bucket_name") and all(.[]; type == "string")' \
  <<<"$resolved_inputs_json" >/dev/null; then
  echo "Resolved renderer inputs contain unsupported or malformed values" >&2; exit 2
fi
uploads_bucket_name="$(jq -r '.uploads_bucket_name // empty' <<<"$resolved_inputs_json")"
if [[ -n "$uploads_bucket_name" && "$uploads_bucket_name" != "$expected_uploads_bucket" ]]; then
  echo "The uploads bucket reference does not match this account, project and region" >&2; exit 2
fi
[[ "$result_uri" =~ ^s3://[A-Za-z0-9.-]+/[A-Za-z0-9_./=-]+$ ]] || { echo "Execution result URI is invalid" >&2; exit 2; }
[[ "$saved_plan_uri" =~ ^s3://[A-Za-z0-9.-]+/[A-Za-z0-9_./=-]+$ ]] || { echo "Saved plan URI is invalid" >&2; exit 2; }
customer_state_prefix="s3://${TF_STATE_BUCKET}/davdeploy/customer/${connection_id}/projects/${project_id}/"
saved_plan_prefix="${customer_state_prefix}${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}/${saved_plan_kind}/"
[[ "$result_uri" == "${customer_state_prefix}runs/${run_id}/result.json" ]] || { echo "Execution result must be stored in this project's run prefix" >&2; exit 2; }
[[ "$saved_plan_uri" == "$saved_plan_prefix"* ]] || { echo "Saved plan must be stored in this plan's digest prefix" >&2; exit 2; }

cleanup() {
  rm -f "$artifact" "$plan_file" "$result_file" "$credentials_file" \
    "${result_file}.summary" "${result_file}.plan" "${result_file}.outputs" \
    "${result_file}.cleanup" "${result_file}.health" "$lambda_error" \
    "/tmp/davdeploy-serverless-${run_id}-role-check.err"
}
trap cleanup EXIT

platform_aws() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws --profile "$AWS_PROFILE" "$@"
  else
    aws "$@"
  fi
}
customer_aws_args=(--profile "davdeploy-customer")

external_id="$(platform_aws secretsmanager get-secret-value \
  --secret-id "$DAVDEPLOY_EXTERNAL_ID_SECRET_ARN" --query SecretString --output text)"
[[ -n "$external_id" && "$external_id" != "None" ]] || { echo "Customer connection ExternalId is unavailable" >&2; exit 3; }
credentials="$(platform_aws sts assume-role \
  --role-arn "$DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN" \
  --role-session-name "davdeploy-${run_id}" --external-id "$external_id" \
  --duration-seconds 3600 --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text)"
unset external_id
read -r customer_access_key_id customer_secret_access_key customer_session_token <<<"$credentials"
unset credentials
[[ -n "${customer_access_key_id:-}" && -n "${customer_secret_access_key:-}" && -n "${customer_session_token:-}" ]] || {
  echo "Scoped customer execution role assumption returned incomplete credentials" >&2; exit 3;
}
umask 077
original_credentials_file="${AWS_SHARED_CREDENTIALS_FILE:-${HOME}/.aws/credentials}"
if [[ -f "$original_credentials_file" ]]; then
  awk -v target="[${customer_profile}]" 'BEGIN { skip = 0 } /^\[/ { skip = ($0 == target) } !skip { print }' \
    "$original_credentials_file" >"$credentials_file"
else
  : >"$credentials_file"
fi
cat >>"$credentials_file" <<EOF
[${customer_profile}]
aws_access_key_id=${customer_access_key_id}
aws_secret_access_key=${customer_secret_access_key}
aws_session_token=${customer_session_token}
EOF
unset customer_access_key_id customer_secret_access_key customer_session_token
export AWS_SHARED_CREDENTIALS_FILE="$credentials_file"
customer_account_id="$(aws sts get-caller-identity "${customer_aws_args[@]}" --query Account --output text)"
[[ "$customer_account_id" == "$EXPECTED_AWS_ACCOUNT_ID" ]] || {
  echo "Assumed customer role is in the wrong AWS account" >&2; exit 3;
}

tf_vars=(
  "-var=region=${AWS_REGION}"
  "-var=expected_account_id=${EXPECTED_AWS_ACCOUNT_ID}"
  "-var=connection_id=${connection_id}"
  "-var=project_id=${project_id}"
  "-var=plan_digest=${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}"
  "-var=service_name=${service_name}"
  "-var=artifact_path=${artifact}"
  "-var=customer_profile=${customer_profile}"
  "-var=uploads_bucket_name=${uploads_bucket_name}"
)

tf_init() {
  terraform -chdir="$root" init -input=false -reconfigure \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="key=davdeploy/customer/${connection_id}/projects/${project_id}/serverless-api.tfstate" \
    -backend-config="dynamodb_table=${TF_LOCK_TABLE}" \
    -backend-config="region=${AWS_REGION}"
}

download_artifact() {
  require DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI
  require DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256
  [[ "$artifact_uri" =~ ^s3://[A-Za-z0-9.-]+/[A-Za-z0-9_./=-]+$ ]] || { echo "Serverless artifact URI is invalid" >&2; exit 2; }
  local artifact_prefix="s3://${TF_STATE_BUCKET}/davdeploy/customer/${connection_id}/projects/${project_id}/artifacts/${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}/"
  [[ "$artifact_uri" == "$artifact_prefix"* && "$artifact_uri" == */lambda.zip ]] || {
    echo "Serverless artifact must be stored under this project's approved plan prefix" >&2; exit 2;
  }
  local artifact_run_id="${artifact_uri#"$artifact_prefix"}"
  artifact_run_id="${artifact_run_id%/lambda.zip}"
  [[ "$artifact_run_id" =~ ^[A-Za-z0-9_-]{1,80}$ ]] || {
    echo "Serverless artifact run identifier is invalid" >&2; exit 2;
  }
  [[ "$artifact_sha256" =~ ^[a-f0-9]{64}$ ]] || { echo "Serverless artifact SHA-256 is invalid" >&2; exit 2; }
  platform_aws s3 cp "$artifact_uri" "$artifact" --only-show-errors
  echo "${artifact_sha256}  ${artifact}" | shasum -a 256 --check --status || {
    echo "Serverless artifact digest mismatch" >&2; exit 3;
  }
}

write_result() {
  local phase="$1" status="$2" detail_file="${3:-}"
  local detail='{}'
  if [[ -n "$detail_file" && -f "$detail_file" ]]; then detail="$(cat "$detail_file")"; fi
  jq -n --arg run_id "$run_id" --arg phase "$phase" --arg status "$status" \
    --arg connection_id "$connection_id" --arg project_id "$project_id" \
    --arg plan_digest "$DAVDEPLOY_CUSTOMER_PLAN_DIGEST" \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --argjson detail "$detail" \
    '{schema_version:"davdeploy.customer_execution_result.v1",run_id:$run_id,phase:$phase,status:$status,connection_id:$connection_id,project_id:$project_id,plan_digest:$plan_digest,generated_at:$generated_at,detail:$detail}' \
    >"$result_file"
  platform_aws s3 cp "$result_file" "$result_uri" --only-show-errors
}

verify_absent() {
  local function_name="$service_name"
  local api_name="${service_name}-http"
  if aws lambda get-function "${customer_aws_args[@]}" --region "$AWS_REGION" --function-name "$function_name" >/dev/null 2>"$lambda_error"; then
    echo "Lambda function remains after cleanup: ${function_name}" >&2; return 1
  elif ! grep -Eq 'ResourceNotFoundException|Function not found' "$lambda_error"; then
    cat "$lambda_error" >&2
    echo "Could not verify Lambda cleanup" >&2
    return 1
  fi
  rm -f "$lambda_error"
  local role_error="/tmp/davdeploy-serverless-${run_id}-role-check.err"
  if aws iam get-role "${customer_aws_args[@]}" --role-name "${service_name}-lambda" >/dev/null 2>"$role_error"; then
    echo "Lambda execution role remains after cleanup: ${service_name}-lambda" >&2; return 1
  elif ! grep -Eq 'NoSuchEntity|cannot be found' "$role_error"; then
    cat "$role_error" >&2
    echo "Could not verify IAM role cleanup" >&2
    rm -f "$role_error"
    return 1
  fi
  rm -f "$role_error"
  local api_ids
  api_ids="$(aws apigatewayv2 get-apis "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --query "Items[?Name=='${api_name}'].ApiId" --output text)"
  [[ -z "$api_ids" || "$api_ids" == "None" ]] || { echo "HTTP API remains after cleanup: ${api_name}" >&2; return 1; }
  [[ -z "$(terraform -chdir="$root" state list)" ]] || { echo "Terraform state still contains resources after cleanup" >&2; return 1; }
}

case "$operation" in
  plan|destroy-plan)
    download_artifact
    tf_init
    plan_args=(-input=false -out="$plan_file")
    [[ "$operation" != "destroy-plan" ]] || plan_args+=(-destroy)
    terraform -chdir="$root" plan "${plan_args[@]}" "${tf_vars[@]}"
    plan_sha256="$(shasum -a 256 "$plan_file" | awk '{print $1}')"
    terraform -chdir="$root" show -json "$plan_file" | jq '{format_version,terraform_version,resource_changes:[(.resource_changes // [])[] | {address,mode,type,name,provider_name,actions:.change.actions}]}' >"${result_file}.summary"
    platform_aws s3 cp "$plan_file" "$saved_plan_uri" --only-show-errors
    jq -n --arg saved_plan_s3_uri "$saved_plan_uri" --arg saved_plan_sha256 "$plan_sha256" \
      --arg artifact_sha256 "$artifact_sha256" \
      --argjson summary "$(cat "${result_file}.summary")" \
      '{saved_plan_s3_uri:$saved_plan_s3_uri,saved_plan_sha256:$saved_plan_sha256,artifact_sha256:$artifact_sha256,plan_summary:$summary}' >"${result_file}.plan"
    write_result "$operation" "SUCCEEDED" "${result_file}.plan"
    ;;
  apply-saved-plan|destroy-saved-plan)
    require DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256
    [[ "$saved_plan_sha256" =~ ^[a-f0-9]{64}$ ]] || { echo "Saved Terraform plan SHA-256 is invalid" >&2; exit 2; }
    download_artifact
    tf_init
    platform_aws s3 cp "$saved_plan_uri" "$plan_file" --only-show-errors
    echo "${saved_plan_sha256}  ${plan_file}" | shasum -a 256 --check --status || {
      echo "Saved Terraform plan digest mismatch" >&2; exit 3;
    }
    terraform -chdir="$root" apply -input=false "$plan_file"
    if [[ "$operation" == "apply-saved-plan" ]]; then
      terraform -chdir="$root" output -json >"${result_file}.outputs"
      jq -n --arg saved_plan_sha256 "$saved_plan_sha256" --arg artifact_sha256 "$artifact_sha256" \
        --argjson outputs "$(cat "${result_file}.outputs")" \
        '{saved_plan_sha256:$saved_plan_sha256,artifact_sha256:$artifact_sha256,outputs:$outputs}' >"${result_file}.apply"
      write_result "apply" "SUCCEEDED" "${result_file}.apply"
    else
      verify_absent
      jq -n --arg saved_plan_sha256 "$saved_plan_sha256" \
        '{saved_plan_sha256:$saved_plan_sha256,cleanup:"confirmed_absent"}' >"${result_file}.cleanup"
      write_result "destroy" "SUCCEEDED" "${result_file}.cleanup"
    fi
    ;;
  health)
    tf_init
    endpoint="$(terraform -chdir="$root" output -raw api_endpoint)"
    body="$(curl --fail --silent --show-error --max-time 15 "${endpoint}/")"
    jq -n --arg endpoint "$endpoint" --arg response "$body" '{endpoint:$endpoint,response:$response}' >"${result_file}.health"
    write_result "health" "SUCCEEDED" "${result_file}.health"
    ;;
  verify-cleanup)
    tf_init
    verify_absent
    jq -n '{cleanup:"confirmed_absent"}' >"${result_file}.cleanup"
    write_result "verify-cleanup" "SUCCEEDED" "${result_file}.cleanup"
    ;;
  *)
    exit 2
    ;;
esac
