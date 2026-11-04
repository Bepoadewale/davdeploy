#!/usr/bin/env bash
set -euo pipefail

operation="${1:-}"
root="infrastructure/terraform/customer-workload-private-s3"

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
  *)
    echo "allowed operations: plan, destroy-plan, apply-saved-plan, observe, destroy-saved-plan, verify-cleanup" >&2
    exit 2
    ;;
esac

connection_id="$DAVDEPLOY_CUSTOMER_CONNECTION_ID"
project_id="$DAVDEPLOY_CUSTOMER_PROJECT_ID"
run_id="$DAVDEPLOY_EXECUTION_RUN_ID"
project_scope="${connection_id}:${project_id}:${AWS_REGION}"
project_suffix="$(printf '%s' "$project_scope" | shasum -a 256 | awk '{print substr($1, 1, 20)}')"
bucket_name="davdeploy-${EXPECTED_AWS_ACCOUNT_ID}-${AWS_REGION}-${project_suffix}"
result_uri="$DAVDEPLOY_EXECUTION_RESULT_S3_URI"
saved_plan_uri="$DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"
saved_plan_sha256="${DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256:-}"
plan_file="/tmp/davdeploy-private-s3-${run_id}.tfplan"
result_file="/tmp/davdeploy-private-s3-${run_id}-result.json"
credentials_file="/tmp/davdeploy-private-s3-${run_id}.credentials"
error_file="/tmp/davdeploy-private-s3-${run_id}.err"
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
[[ "$bucket_name" =~ ^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$ ]] || { echo "Derived S3 bucket name is invalid" >&2; exit 2; }
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
)

tf_init() {
  terraform -chdir="$root" init -input=false -reconfigure \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="key=davdeploy/customer/${connection_id}/projects/${project_id}/private-s3.tfstate" \
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

verify_bucket_absent() {
  if aws s3api head-bucket "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --bucket "$bucket_name" >/dev/null 2>"$error_file"; then
    echo "Private storage bucket remains after cleanup: ${bucket_name}" >&2
    return 1
  fi
  if ! grep -Eqi 'Not Found|404|NoSuchBucket' "$error_file"; then
    cat "$error_file" >&2
    echo "Could not verify private storage cleanup" >&2
    return 1
  fi
  rm -f "$error_file"
  [[ -z "$(terraform -chdir="$root" state list)" ]] || {
    echo "Terraform state still contains resources after cleanup" >&2; return 1;
  }
}

observe_bucket() {
  aws s3api head-bucket "${customer_aws_args[@]}" --region "$AWS_REGION" --bucket "$bucket_name"
  aws s3api get-public-access-block "${customer_aws_args[@]}" --region "$AWS_REGION" --bucket "$bucket_name" \
    | jq -e '.PublicAccessBlockConfiguration | .BlockPublicAcls == true and .IgnorePublicAcls == true and .BlockPublicPolicy == true and .RestrictPublicBuckets == true' >/dev/null
  aws s3api get-bucket-ownership-controls "${customer_aws_args[@]}" --region "$AWS_REGION" --bucket "$bucket_name" \
    | jq -e 'any(.OwnershipControls.Rules[]?; .ObjectOwnership == "BucketOwnerEnforced")' >/dev/null
  aws s3api get-bucket-encryption "${customer_aws_args[@]}" --region "$AWS_REGION" --bucket "$bucket_name" \
    | jq -e 'any(.ServerSideEncryptionConfiguration.Rules[]?; .ApplyServerSideEncryptionByDefault.SSEAlgorithm == "AES256")' >/dev/null
  aws s3api get-bucket-versioning "${customer_aws_args[@]}" --region "$AWS_REGION" --bucket "$bucket_name" \
    | jq -e '.Status == "Enabled"' >/dev/null
  aws s3api get-bucket-policy "${customer_aws_args[@]}" --region "$AWS_REGION" --bucket "$bucket_name" --query Policy --output text \
    | jq -e 'any(.Statement[]?; .Effect == "Deny" and (.Action == "s3:*" or ((.Action | type) == "array" and (.Action | index("s3:*") != null))) and .Condition.Bool["aws:SecureTransport"] == "false")' >/dev/null
}

assert_bucket_empty_for_destroy() {
  if ! aws s3api head-bucket "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --bucket "$bucket_name" >/dev/null 2>"$error_file"; then
    if grep -Eqi 'Not Found|404|NoSuchBucket' "$error_file"; then
      rm -f "$error_file"
      return 0
    fi
    cat "$error_file" >&2
    echo "Could not check storage contents before destroy" >&2
    return 1
  fi
  if ! aws s3api list-object-versions "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --bucket "$bucket_name" \
    | jq -e '((.Versions // []) | length == 0) and ((.DeleteMarkers // []) | length == 0)' >/dev/null; then
    echo "Private storage contains current or previous object versions. Export or remove the data before destroying this bucket." >&2
    return 1
  fi
}

case "$operation" in
  plan|destroy-plan)
    if [[ "$operation" == "destroy-plan" ]]; then assert_bucket_empty_for_destroy; fi
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
      --arg bucket_name "$bucket_name" --argjson summary "$(cat "${result_file}.summary")" \
      '{saved_plan_s3_uri:$saved_plan_s3_uri,saved_plan_sha256:$saved_plan_sha256,bucket_name:$bucket_name,plan_summary:$summary}' \
      >"${result_file}.plan"
    write_result "$operation" "SUCCEEDED" "${result_file}.plan"
    ;;
  apply-saved-plan|destroy-saved-plan)
    require DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256
    [[ "$saved_plan_sha256" =~ ^[a-f0-9]{64}$ ]] || { echo "Saved Terraform plan SHA-256 is invalid" >&2; exit 2; }
    tf_init
    if [[ "$operation" == "destroy-saved-plan" ]]; then assert_bucket_empty_for_destroy; fi
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
      verify_bucket_absent
      jq -n --arg saved_plan_sha256 "$saved_plan_sha256" \
        '{saved_plan_sha256:$saved_plan_sha256,cleanup:"confirmed_absent"}' >"${result_file}.cleanup"
      write_result "destroy" "SUCCEEDED" "${result_file}.cleanup"
    fi
    ;;
  observe)
    tf_init
    observe_bucket
    jq -n --arg bucket_name "$bucket_name" \
      '{bucket_name:$bucket_name,health:"private_encrypted_versioned_and_tls_only"}' >"${result_file}.observation"
    write_result "observe" "SUCCEEDED" "${result_file}.observation"
    ;;
  verify-cleanup)
    tf_init
    verify_bucket_absent
    jq -n --arg bucket_name "$bucket_name" \
      '{bucket_name:$bucket_name,cleanup:"confirmed_absent"}' >"${result_file}.cleanup"
    write_result "verify_cleanup" "SUCCEEDED" "${result_file}.cleanup"
    ;;
esac
