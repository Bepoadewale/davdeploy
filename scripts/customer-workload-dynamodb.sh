#!/usr/bin/env bash
set -euo pipefail

operation="${1:-}"
root="infrastructure/terraform/customer-workload-dynamodb"

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

case "$operation" in
  plan|apply-saved-plan) saved_plan_kind="apply" ;;
  destroy-plan|destroy-saved-plan) saved_plan_kind="destroy" ;;
  observe|verify-cleanup) saved_plan_kind="apply" ;;
  *) echo "allowed operations: plan, destroy-plan, apply-saved-plan, observe, destroy-saved-plan, verify-cleanup" >&2; exit 2 ;;
esac

connection_id="$DAVDEPLOY_CUSTOMER_CONNECTION_ID"
project_id="$DAVDEPLOY_CUSTOMER_PROJECT_ID"
run_id="$DAVDEPLOY_EXECUTION_RUN_ID"
project_scope="${connection_id}:${project_id}:${AWS_REGION}"
project_suffix="$(printf '%s' "$project_scope" | shasum -a 256 | awk '{print substr($1, 1, 20)}')"
table_name="davdeploy-${EXPECTED_AWS_ACCOUNT_ID}-${AWS_REGION}-${project_suffix}"
result_uri="$DAVDEPLOY_EXECUTION_RESULT_S3_URI"
saved_plan_uri="$DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"
saved_plan_sha256="${DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256:-}"
plan_file="/tmp/davdeploy-dynamodb-${run_id}.tfplan"
result_file="/tmp/davdeploy-dynamodb-${run_id}-result.json"
credentials_file="/tmp/davdeploy-dynamodb-${run_id}.credentials"
error_file="/tmp/davdeploy-dynamodb-${run_id}.err"
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
[[ "$DAVDEPLOY_CUSTOMER_PLAN_DIGEST" =~ ^[a-f0-9]{64}$ ]] || { echo "Customer plan digest must be a SHA-256 digest" >&2; exit 2; }
[[ "$result_uri" =~ ^s3://[A-Za-z0-9.-]+/[A-Za-z0-9_./=-]+$ ]] || { echo "Execution result URI is invalid" >&2; exit 2; }
[[ "$saved_plan_uri" =~ ^s3://[A-Za-z0-9.-]+/[A-Za-z0-9_./=-]+$ ]] || { echo "Saved plan URI is invalid" >&2; exit 2; }
customer_state_prefix="s3://${TF_STATE_BUCKET}/davdeploy/customer/${connection_id}/projects/${project_id}/"
saved_plan_prefix="${customer_state_prefix}${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}/${saved_plan_kind}/"
[[ "$result_uri" == "${customer_state_prefix}runs/${run_id}/result.json" ]] || { echo "Execution result must be stored in this project's run prefix" >&2; exit 2; }
[[ "$saved_plan_uri" == "$saved_plan_prefix"* ]] || { echo "Saved plan must be stored in this plan's digest prefix" >&2; exit 2; }

cleanup() {
  rm -f "$plan_file" "$result_file" "$credentials_file" "$error_file" \
    "${result_file}.summary" "${result_file}.plan" "${result_file}.outputs" \
    "${result_file}.observation" "${result_file}.cleanup"
}
trap cleanup EXIT

platform_aws() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then aws --profile "$AWS_PROFILE" "$@"; else aws "$@"; fi
}
customer_aws_args=(--profile "$customer_profile")

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
cat >>"$credentials_file" <<EOF2
[${customer_profile}]
aws_access_key_id=${customer_access_key_id}
aws_secret_access_key=${customer_secret_access_key}
aws_session_token=${customer_session_token}
EOF2
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
)

tf_init() {
  terraform -chdir="$root" init -input=false -reconfigure \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="key=davdeploy/customer/${connection_id}/projects/${project_id}/regions/${AWS_REGION}/dynamodb.tfstate" \
    -backend-config="dynamodb_table=${TF_LOCK_TABLE}" \
    -backend-config="region=${AWS_REGION}"
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

assert_table_empty_for_destroy() {
  if ! aws dynamodb describe-table "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --table-name "$table_name" >/dev/null 2>"$error_file"; then
    if grep -Eqi 'ResourceNotFoundException|ResourceNotFound' "$error_file"; then
      rm -f "$error_file"
      return 0
    fi
    cat "$error_file" >&2
    echo "Could not check DynamoDB contents before destroy" >&2
    return 1
  fi
  local scan_result item_count has_more
  scan_result="$(aws dynamodb scan "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --table-name "$table_name" --limit 1 --select COUNT --no-paginate)"
  item_count="$(jq -r '.Count // 0' <<<"$scan_result")"
  has_more="$(jq -r 'has("LastEvaluatedKey")' <<<"$scan_result")"
  [[ "$item_count" == "0" && "$has_more" == "false" ]] || {
    echo "DynamoDB table contains data or emptiness could not be confirmed safely. Export or remove its items before destroying this table." >&2
    return 1
  }
}

verify_table_absent() {
  if aws dynamodb describe-table "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --table-name "$table_name" >/dev/null 2>"$error_file"; then
    echo "DynamoDB table remains after cleanup: ${table_name}" >&2
    return 1
  fi
  if ! grep -Eqi 'ResourceNotFoundException|ResourceNotFound' "$error_file"; then
    cat "$error_file" >&2
    echo "Could not verify DynamoDB cleanup" >&2
    return 1
  fi
  rm -f "$error_file"
  [[ -z "$(terraform -chdir="$root" state list)" ]] || {
    echo "Terraform state still contains resources after cleanup" >&2; return 1;
  }
}

observe_table() {
  local description backup tags attempt
  description="$(aws dynamodb describe-table "${customer_aws_args[@]}" --region "$AWS_REGION" --table-name "$table_name")"
  jq -e '.Table.TableStatus == "ACTIVE" and .Table.BillingModeSummary.BillingMode == "PAY_PER_REQUEST" and .Table.SSEDescription.Status == "ENABLED"' \
    <<<"$description" >/dev/null
  for attempt in {1..40}; do
    backup="$(aws dynamodb describe-continuous-backups "${customer_aws_args[@]}" --region "$AWS_REGION" --table-name "$table_name")"
    if jq -e '.ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus == "ENABLED"' \
      <<<"$backup" >/dev/null; then
      break
    fi
    if [[ "$attempt" == "40" ]]; then
      echo "DynamoDB point-in-time recovery did not become ready within 10 minutes" >&2
      return 1
    fi
    sleep 15
  done
  tags="$(aws dynamodb list-tags-of-resource "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --resource-arn "$(jq -r '.Table.TableArn' <<<"$description")")"
  jq -e --arg connection "$connection_id" --arg project "$project_id" \
    --arg plan "$DAVDEPLOY_CUSTOMER_PLAN_DIGEST" \
    '([.Tags[]? | select(.Key == "ManagedBy" and .Value == "davdeploy")] | length == 1) and
     ([.Tags[]? | select(.Key == "DavDeployConnection" and .Value == $connection)] | length == 1) and
     ([.Tags[]? | select(.Key == "DavDeployProject" and .Value == $project)] | length == 1) and
     ([.Tags[]? | select(.Key == "DavDeployPlan" and .Value == $plan)] | length == 1)' \
    <<<"$tags" >/dev/null
}

case "$operation" in
  plan|destroy-plan)
    if [[ "$operation" == "destroy-plan" ]]; then assert_table_empty_for_destroy; fi
    tf_init
    plan_args=(-input=false -out="$plan_file")
    [[ "$operation" != "destroy-plan" ]] || plan_args+=(-destroy)
    terraform -chdir="$root" plan "${plan_args[@]}" "${tf_vars[@]}"
    plan_sha256="$(shasum -a 256 "$plan_file" | awk '{print $1}')"
    terraform -chdir="$root" show -json "$plan_file" \
      | jq '{format_version,terraform_version,resource_changes:[(.resource_changes // [])[] | {address,mode,type,name,provider_name,actions:.change.actions}]}' \
      >"${result_file}.summary"
    platform_aws s3 cp "$plan_file" "$saved_plan_uri" --only-show-errors
    jq -n --arg saved_plan_s3_uri "$saved_plan_uri" --arg saved_plan_sha256 "$plan_sha256" \
      --arg table_name "$table_name" --argjson summary "$(cat "${result_file}.summary")" \
      '{saved_plan_s3_uri:$saved_plan_s3_uri,saved_plan_sha256:$saved_plan_sha256,table_name:$table_name,plan_summary:$summary}' \
      >"${result_file}.plan"
    write_result "$operation" "SUCCEEDED" "${result_file}.plan"
    ;;
  apply-saved-plan|destroy-saved-plan)
    require DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256
    [[ "$saved_plan_sha256" =~ ^[a-f0-9]{64}$ ]] || { echo "Saved Terraform plan SHA-256 is invalid" >&2; exit 2; }
    tf_init
    if [[ "$operation" == "destroy-saved-plan" ]]; then assert_table_empty_for_destroy; fi
    platform_aws s3 cp "$saved_plan_uri" "$plan_file" --only-show-errors
    echo "${saved_plan_sha256}  ${plan_file}" | shasum -a 256 --check --status || {
      echo "Saved Terraform plan digest mismatch" >&2; exit 3;
    }
    terraform -chdir="$root" apply -input=false "$plan_file"
    if [[ "$operation" == "apply-saved-plan" ]]; then
      terraform -chdir="$root" output -json >"${result_file}.outputs"
      jq -n --arg saved_plan_sha256 "$saved_plan_sha256" \
        --argjson outputs "$(cat "${result_file}.outputs")" \
        '{saved_plan_sha256:$saved_plan_sha256,outputs:$outputs}' >"${result_file}.plan"
      write_result "apply" "SUCCEEDED" "${result_file}.plan"
    else
      verify_table_absent
      jq -n --arg saved_plan_sha256 "$saved_plan_sha256" \
        '{saved_plan_sha256:$saved_plan_sha256,cleanup:"confirmed_absent"}' >"${result_file}.cleanup"
      write_result "destroy" "SUCCEEDED" "${result_file}.cleanup"
    fi
    ;;
  observe)
    tf_init
    observe_table
    jq -n --arg table_name "$table_name" \
      '{table_name:$table_name,health:"active_on_demand_encrypted_and_point_in_time_recoverable"}' \
      >"${result_file}.observation"
    write_result "observe" "SUCCEEDED" "${result_file}.observation"
    ;;
  verify-cleanup)
    tf_init
    verify_table_absent
    jq -n --arg table_name "$table_name" \
      '{table_name:$table_name,cleanup:"confirmed_absent"}' >"${result_file}.cleanup"
    write_result "verify-cleanup" "SUCCEEDED" "${result_file}.cleanup"
    ;;
esac
