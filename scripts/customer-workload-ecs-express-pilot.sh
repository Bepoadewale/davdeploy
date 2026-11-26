#!/usr/bin/env bash
set -euo pipefail

operation="${1:-}"
root="infrastructure/terraform/customer-workload-ecs-express-pilot"
platform_profile="${AWS_PROFILE:-}"
original_credentials_file="${AWS_SHARED_CREDENTIALS_FILE:-${HOME}/.aws/credentials}"

require() {
  local name="$1"
  [[ -n "${!name:-}" ]] || { echo "$name is required" >&2; exit 2; }
}

for name in AWS_REGION EXPECTED_AWS_ACCOUNT_ID DAVDEPLOY_PLAN_ARTIFACT_BUCKET \
  DAVDEPLOY_CUSTOMER_STATE_BUCKET \
  DAVDEPLOY_CUSTOMER_STATE_KMS_KEY_ARN \
  DAVDEPLOY_CUSTOMER_CONNECTION_ID DAVDEPLOY_CUSTOMER_PROJECT_ID \
  DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN DAVDEPLOY_EXTERNAL_ID_SECRET_ARN \
  DAVDEPLOY_EXECUTION_RUN_ID DAVDEPLOY_EXECUTION_RESULT_S3_URI \
  DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI DAVDEPLOY_CUSTOMER_PLAN_DIGEST \
  DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY DAVDEPLOY_CUSTOMER_SOURCE_COMMIT; do
  require "$name"
done

case "$operation" in
  plan|apply-saved-plan) saved_plan_kind="apply" ;;
  destroy-plan|destroy-saved-plan) saved_plan_kind="destroy" ;;
  observe|verify-cleanup|build-artifact) saved_plan_kind="apply" ;;
  *)
    echo "allowed operations: plan, apply-saved-plan, observe, destroy-plan, destroy-saved-plan, verify-cleanup, build-artifact" >&2
    exit 2
    ;;
esac
if [[ "$operation" == "build-artifact" ]]; then
  require DAVDEPLOY_CUSTOMER_IMAGE_PUBLISH_ROLE_ARN
  [[ "$DAVDEPLOY_CUSTOMER_IMAGE_PUBLISH_ROLE_ARN" =~ ^arn:aws:iam::${EXPECTED_AWS_ACCOUNT_ID}:role/[A-Za-z0-9+=,.@_/-]+$ ]] || {
    echo "Customer image publisher role must belong to the expected AWS account" >&2; exit 2;
  }
fi

connection_id="$DAVDEPLOY_CUSTOMER_CONNECTION_ID"
project_id="$DAVDEPLOY_CUSTOMER_PROJECT_ID"
run_id="$DAVDEPLOY_EXECUTION_RUN_ID"
scope="${connection_id}:${project_id}:${AWS_REGION}"
scope_hash="$(printf '%s' "$scope" | shasum -a 256 | awk '{print substr($1, 1, 24)}')"
service_name="davdeploy-ecs-${scope_hash}"
repository_name="$service_name"
result_uri="$DAVDEPLOY_EXECUTION_RESULT_S3_URI"
saved_plan_uri="$DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"
artifact_bucket="$DAVDEPLOY_PLAN_ARTIFACT_BUCKET"
customer_state_bucket="$DAVDEPLOY_CUSTOMER_STATE_BUCKET"
customer_state_kms_key_arn="$DAVDEPLOY_CUSTOMER_STATE_KMS_KEY_ARN"
image_identifier="${DAVDEPLOY_CUSTOMER_IMAGE_IDENTIFIER:-}"
saved_plan_sha256="${DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256:-}"
plan_file="/tmp/davdeploy-ecs-express-${run_id}.tfplan"
result_file="/tmp/davdeploy-ecs-express-${run_id}-result.json"
credentials_file="/tmp/davdeploy-ecs-express-${run_id}.credentials"
error_file="/tmp/davdeploy-ecs-express-${run_id}.err"
health_file="/tmp/davdeploy-ecs-express-${run_id}.health"
docker_config="/tmp/davdeploy-ecs-express-${run_id}-docker"
customer_profile="davdeploy-customer"
publisher_profile="davdeploy-customer-image-publisher"
customer_aws_args=(--profile "$customer_profile")

[[ "$EXPECTED_AWS_ACCOUNT_ID" =~ ^[0-9]{12}$ ]] || { echo "Expected AWS account ID is invalid" >&2; exit 2; }
[[ "$AWS_REGION" =~ ^[a-z]{2}(-gov|-cn)?-[a-z]+-[0-9]+$ ]] || { echo "AWS region is invalid" >&2; exit 2; }
[[ "$DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN" =~ ^arn:aws:iam::${EXPECTED_AWS_ACCOUNT_ID}:role/[A-Za-z0-9+=,.@_/-]+$ ]] || {
  echo "Customer execution role must belong to the expected AWS account" >&2; exit 2;
}
[[ "$artifact_bucket" =~ ^[A-Za-z0-9.-]{3,63}$ ]] || { echo "Plan artifact bucket is invalid" >&2; exit 2; }
[[ "$customer_state_bucket" =~ ^[A-Za-z0-9.-]{3,63}$ ]] || { echo "Customer Terraform state bucket is invalid" >&2; exit 2; }
[[ "$customer_state_kms_key_arn" =~ ^arn:aws:kms:${AWS_REGION}:${EXPECTED_AWS_ACCOUNT_ID}:key/[a-f0-9-]{36}$ ]] || {
  echo "Customer Terraform state KMS key must belong to the expected account and region" >&2; exit 2;
}
[[ "$connection_id" =~ ^[a-z0-9-]{8,30}$ ]] || { echo "Customer connection identifier is invalid" >&2; exit 2; }
[[ "$project_id" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || { echo "Customer project identifier is invalid" >&2; exit 2; }
[[ "$run_id" =~ ^[A-Za-z0-9_-]{1,80}$ ]] || { echo "Execution run identifier is invalid" >&2; exit 2; }
[[ "$DAVDEPLOY_CUSTOMER_PLAN_DIGEST" =~ ^[a-f0-9]{64}$ ]] || { echo "Customer plan digest must be a SHA-256 digest" >&2; exit 2; }
[[ "$DAVDEPLOY_CUSTOMER_SOURCE_COMMIT" =~ ^[a-f0-9]{40}$ ]] || { echo "Customer source commit must be a full Git SHA-1" >&2; exit 2; }
[[ "$result_uri" =~ ^s3://[A-Za-z0-9.-]+/[A-Za-z0-9_./=-]+$ ]] || { echo "Execution result URI is invalid" >&2; exit 2; }
[[ "$saved_plan_uri" =~ ^s3://[A-Za-z0-9.-]+/[A-Za-z0-9_./=-]+$ ]] || { echo "Saved plan URI is invalid" >&2; exit 2; }
artifact_prefix="s3://${artifact_bucket}/davdeploy/customer/${connection_id}/projects/${project_id}/"
saved_plan_prefix="${artifact_prefix}${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}/${saved_plan_kind}/"
[[ "$result_uri" == "${artifact_prefix}runs/${run_id}/result.json" ]] || { echo "Execution result must be stored in this project's run prefix" >&2; exit 2; }
[[ "$saved_plan_uri" == "$saved_plan_prefix"* ]] || { echo "Saved plan must be stored in this plan's digest prefix" >&2; exit 2; }

if [[ -n "$image_identifier" && ! "$image_identifier" =~ ^[0-9]{12}\.dkr\.ecr\.${AWS_REGION}\.amazonaws\.com/${repository_name}@sha256:[a-f0-9]{64}$ ]]; then
  echo "ECS Express image must be a same-account, same-region digest in this project's repository" >&2
  exit 2
fi

cleanup() {
  rm -f "$plan_file" "$result_file" "$credentials_file" "$error_file" "$health_file"
  [[ ! -d "$docker_config" ]] || rm -rf "$docker_config"
}
trap cleanup EXIT

platform_aws() {
  if [[ -n "$platform_profile" ]]; then
    AWS_SHARED_CREDENTIALS_FILE="$original_credentials_file" aws --profile "$platform_profile" "$@"
  else
    AWS_SHARED_CREDENTIALS_FILE="$original_credentials_file" aws "$@"
  fi
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
: >"$credentials_file"
chmod 600 "$credentials_file"
cat >>"$credentials_file" <<EOF
[${customer_profile}]
aws_access_key_id=${customer_access_key_id}
aws_secret_access_key=${customer_secret_access_key}
aws_session_token=${customer_session_token}
EOF
unset customer_access_key_id customer_secret_access_key customer_session_token
export AWS_SHARED_CREDENTIALS_FILE="$credentials_file"
customer_account_id="$(aws sts get-caller-identity "${customer_aws_args[@]}" --query Account --output text)"
[[ "$customer_account_id" == "$EXPECTED_AWS_ACCOUNT_ID" ]] || { echo "Assumed customer role is in the wrong AWS account" >&2; exit 3; }
if [[ "$operation" == "build-artifact" ]]; then
  external_id="$(platform_aws secretsmanager get-secret-value \
    --secret-id "$DAVDEPLOY_EXTERNAL_ID_SECRET_ARN" --query SecretString --output text)"
  publisher_credentials="$(platform_aws sts assume-role \
    --role-arn "$DAVDEPLOY_CUSTOMER_IMAGE_PUBLISH_ROLE_ARN" \
    --role-session-name "davdeploy-image-${run_id}" --external-id "$external_id" \
    --duration-seconds 3600 --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text)"
  unset external_id
  read -r publisher_access_key_id publisher_secret_access_key publisher_session_token <<<"$publisher_credentials"
  unset publisher_credentials
  [[ -n "${publisher_access_key_id:-}" && -n "${publisher_secret_access_key:-}" && -n "${publisher_session_token:-}" ]] || {
    echo "Scoped customer image publisher role assumption returned incomplete credentials" >&2; exit 3;
  }
  cat >>"$credentials_file" <<EOF
[${publisher_profile}]
aws_access_key_id=${publisher_access_key_id}
aws_secret_access_key=${publisher_secret_access_key}
aws_session_token=${publisher_session_token}
EOF
  unset publisher_access_key_id publisher_secret_access_key publisher_session_token
fi

verify_customer_state_backend() {
  local versioning public_access ownership encryption bucket_location kms_key
  bucket_location="$(aws s3api get-bucket-location "${customer_aws_args[@]}" \
    --bucket "$customer_state_bucket" --expected-bucket-owner "$EXPECTED_AWS_ACCOUNT_ID" \
    --query LocationConstraint --output text)"
  [[ "$bucket_location" == "None" ]] && bucket_location="us-east-1"
  [[ "$bucket_location" == "$AWS_REGION" ]] || { echo "Customer Terraform state bucket must be in the selected Region" >&2; return 1; }
  versioning="$(aws s3api get-bucket-versioning "${customer_aws_args[@]}" \
    --bucket "$customer_state_bucket" --expected-bucket-owner "$EXPECTED_AWS_ACCOUNT_ID" \
    --query Status --output text)"
  [[ "$versioning" == "Enabled" ]] || { echo "Customer Terraform state bucket versioning must be enabled" >&2; return 1; }
  public_access="$(aws s3api get-public-access-block "${customer_aws_args[@]}" \
    --bucket "$customer_state_bucket" --expected-bucket-owner "$EXPECTED_AWS_ACCOUNT_ID")"
  jq -e '.PublicAccessBlockConfiguration | .BlockPublicAcls == true and .IgnorePublicAcls == true and .BlockPublicPolicy == true and .RestrictPublicBuckets == true' \
    <<<"$public_access" >/dev/null || { echo "Customer Terraform state bucket must block all public access" >&2; return 1; }
  ownership="$(aws s3api get-bucket-ownership-controls "${customer_aws_args[@]}" \
    --bucket "$customer_state_bucket" --expected-bucket-owner "$EXPECTED_AWS_ACCOUNT_ID")"
  jq -e 'any(.OwnershipControls.Rules[]?; .ObjectOwnership == "BucketOwnerEnforced")' \
    <<<"$ownership" >/dev/null || { echo "Customer Terraform state bucket must enforce bucket-owner ownership" >&2; return 1; }
  encryption="$(aws s3api get-bucket-encryption "${customer_aws_args[@]}" \
    --bucket "$customer_state_bucket" --expected-bucket-owner "$EXPECTED_AWS_ACCOUNT_ID")"
  jq -e --arg key "$customer_state_kms_key_arn" \
    'any(.ServerSideEncryptionConfiguration.Rules[]?; .ApplyServerSideEncryptionByDefault.SSEAlgorithm == "aws:kms" and .ApplyServerSideEncryptionByDefault.KMSMasterKeyID == $key)' \
    <<<"$encryption" >/dev/null || { echo "Customer Terraform state bucket must use the configured customer KMS key" >&2; return 1; }
  kms_key="$(aws kms describe-key "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --key-id "$customer_state_kms_key_arn")"
  jq -e '.KeyMetadata.KeyState == "Enabled" and .KeyMetadata.KeyManager == "CUSTOMER" and .KeyMetadata.KeyUsage == "ENCRYPT_DECRYPT"' \
    <<<"$kms_key" >/dev/null || { echo "Customer Terraform state KMS key must be enabled and customer-managed" >&2; return 1; }
}

tf_vars=(
  "-var=region=${AWS_REGION}"
  "-var=customer_profile=${customer_profile}"
  "-var=expected_account_id=${EXPECTED_AWS_ACCOUNT_ID}"
  "-var=connection_id=${connection_id}"
  "-var=project_id=${project_id}"
  "-var=source_repository=${DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY}"
  "-var=source_commit=${DAVDEPLOY_CUSTOMER_SOURCE_COMMIT}"
  "-var=plan_digest=${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}"
  "-var=enable_service=$([[ -n "$image_identifier" ]] && echo true || echo false)"
)
if [[ -n "$image_identifier" ]]; then tf_vars+=("-var=image_identifier=${image_identifier}"); fi

tf_init() {
  terraform -chdir="$root" init -input=false -reconfigure \
    -backend-config="bucket=${customer_state_bucket}" \
    -backend-config="key=davdeploy/customer/${connection_id}/projects/${project_id}/regions/${AWS_REGION}/ecs-express.tfstate" \
    -backend-config="region=${AWS_REGION}" \
    -backend-config="profile=${customer_profile}" \
    -backend-config="encrypt=true" \
    -backend-config="kms_key_id=${customer_state_kms_key_arn}" \
    -backend-config="use_lockfile=true"
}

verify_service_absent() {
  local service_arn="arn:aws:ecs:${AWS_REGION}:${EXPECTED_AWS_ACCOUNT_ID}:service/default/${service_name}"
  if aws ecs describe-express-gateway-service "${customer_aws_args[@]}" \
    --service-arn "$service_arn" >/dev/null 2>"$error_file"; then
    echo "ECS Express service remains after cleanup: ${service_name}" >&2
    return 1
  fi
  if ! grep -Eqi 'ResourceNotFound|ServiceNotFound|NotFoundException' "$error_file"; then
    echo "Could not verify ECS Express service cleanup" >&2
    return 1
  fi
  rm -f "$error_file"
}

verify_foundation_absent() {
  local vpc_id
  vpc_id="$(aws ec2 describe-vpcs "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --filters "Name=tag:ConnectionId,Values=${connection_id}" "Name=tag:ProjectId,Values=${project_id}" \
    --query 'Vpcs[].VpcId' --output text)"
  [[ -z "$vpc_id" || "$vpc_id" == "None" ]] || { echo "Customer VPC remains after cleanup" >&2; return 1; }
  if aws ecr describe-repositories "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --repository-names "$repository_name" >/dev/null 2>"$error_file"; then
    echo "Customer ECR repository remains after cleanup" >&2
    return 1
  fi
  if ! grep -Eqi 'RepositoryNotFoundException' "$error_file"; then
    echo "Could not verify ECR repository cleanup" >&2
    return 1
  fi
  rm -f "$error_file"
  for role_suffix in execution infrastructure; do
    if aws iam get-role "${customer_aws_args[@]}" --role-name "${service_name}-${role_suffix}" >/dev/null 2>"$error_file"; then
      echo "Customer ECS role remains after cleanup" >&2
      return 1
    fi
    if ! grep -Eqi 'NoSuchEntity' "$error_file"; then
      echo "Could not verify customer ECS role cleanup" >&2
      return 1
    fi
    rm -f "$error_file"
  done
  local log_group
  log_group="$(aws logs describe-log-groups "${customer_aws_args[@]}" --region "$AWS_REGION" \
    --log-group-name-prefix "/aws/ecs/${service_name}" \
    --query "logGroups[?logGroupName=='/aws/ecs/${service_name}'].logGroupName | [0]" --output text)"
  [[ -z "$log_group" || "$log_group" == "None" ]] || {
    echo "Customer ECS log group remains after cleanup" >&2; return 1;
  }
}

verify_customer_state_backend

case "$operation" in
  plan|destroy-plan)
    tf_init
    plan_args=(-input=false -out="$plan_file" "${tf_vars[@]}")
    [[ "$operation" == "destroy-plan" ]] && plan_args+=(-destroy)
    terraform -chdir="$root" plan "${plan_args[@]}"
    plan_sha256="$(shasum -a 256 "$plan_file" | awk '{print $1}')"
    terraform -chdir="$root" show -json "$plan_file" | jq '{format_version,terraform_version,resource_changes:[(.resource_changes // [])[]|{address,mode,type,name,provider_name,actions:.change.actions}]}' >"${result_file}.summary"
    platform_aws s3 cp "$plan_file" "$saved_plan_uri" --only-show-errors
    jq -n --arg saved_plan_s3_uri "$saved_plan_uri" --arg saved_plan_sha256 "$plan_sha256" \
      --slurpfile summary "${result_file}.summary" \
      '{saved_plan_s3_uri:$saved_plan_s3_uri,saved_plan_sha256:$saved_plan_sha256,plan_summary:$summary[0]}' >"${result_file}.detail"
    write_result "$operation" "SUCCEEDED" "${result_file}.detail"
    ;;
  apply-saved-plan|destroy-saved-plan)
    [[ -n "$saved_plan_sha256" && "$saved_plan_sha256" =~ ^[a-f0-9]{64}$ ]] || {
      echo "A valid approved saved-plan SHA-256 is required" >&2; exit 2;
    }
    tf_init
    platform_aws s3 cp "$saved_plan_uri" "$plan_file" --only-show-errors
    echo "${saved_plan_sha256}  ${plan_file}" | shasum -a 256 --check --status || {
      echo "Saved Terraform plan digest mismatch" >&2; exit 3;
    }
    terraform -chdir="$root" apply -input=false "$plan_file"
    terraform -chdir="$root" output -json >"${result_file}.outputs"
    write_result "$operation" "SUCCEEDED" "${result_file}.outputs"
    ;;
  observe)
    tf_init
    ingress="$(terraform -chdir="$root" output -json ingress_paths | jq -r '[.[] | select(.access_type == "PUBLIC") | .endpoint][0] // empty')"
    [[ "$ingress" == https://* ]] || { echo "ECS Express did not expose a verified HTTPS endpoint" >&2; exit 3; }
    curl --fail --silent --show-error --max-time 20 --max-filesize 4096 \
      --output "$health_file" "${ingress%/}/healthz"
    [[ "$(wc -c <"$health_file" | tr -d ' ')" -le 4096 ]] || {
      echo "ECS Express health response exceeded its size limit" >&2; exit 3;
    }
    jq -e '.status == "ok" and .scope == "same-account-customer-sandbox"' "$health_file" >/dev/null || {
      echo "ECS Express health response did not match the approved workload contract" >&2; exit 3;
    }
    jq -n --arg health_url "${ingress%/}/healthz" --slurpfile health "$health_file" \
      '{health_url:$health_url,response:$health[0]}' >"${result_file}.observation"
    write_result "$operation" "SUCCEEDED" "${result_file}.observation"
    ;;
  build-artifact)
    tf_init
    repository_url="$(terraform -chdir="$root" output -raw ecr_repository_url)"
    repository_arn="arn:aws:ecr:${AWS_REGION}:${EXPECTED_AWS_ACCOUNT_ID}:repository/${repository_name}"
    [[ "$repository_url" == "${EXPECTED_AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${repository_name}" ]] || {
      echo "ECR output does not match the customer account, region, and project" >&2; exit 3;
    }
    source_dir="tests/fixtures/customer-ecs-express-health"
    [[ -f "${source_dir}/Dockerfile" ]] || { echo "Approved ECS health fixture is unavailable" >&2; exit 3; }
    mkdir -m 700 "$docker_config"
    export DOCKER_CONFIG="$docker_config"
    aws ecr get-login-password --profile "$publisher_profile" --region "$AWS_REGION" | \
      docker login --username AWS --password-stdin "${EXPECTED_AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" >/dev/null
    image_tag="$service_name-${DAVDEPLOY_CUSTOMER_SOURCE_COMMIT}"
    docker build --platform linux/amd64 --tag "${repository_url}:${image_tag}" "$source_dir"
    docker push "${repository_url}:${image_tag}"
    image_digest="$(aws ecr describe-images --profile "$publisher_profile" --region "$AWS_REGION" \
      --repository-name "$repository_name" --image-ids "imageTag=${image_tag}" \
      --query 'imageDetails[0].imageDigest' --output text)"
    [[ "$image_digest" =~ ^sha256:[a-f0-9]{64}$ ]] || { echo "ECR did not return an immutable image digest" >&2; exit 3; }
    jq -n --arg repository_arn "$repository_arn" --arg image_identifier "${repository_url}@${image_digest}" \
      --arg image_digest "$image_digest" '{repository_arn:$repository_arn,image_identifier:$image_identifier,image_digest:$image_digest}' >"${result_file}.artifact"
    write_result "$operation" "SUCCEEDED" "${result_file}.artifact"
    ;;
  verify-cleanup)
    verify_service_absent
    verify_foundation_absent
    jq -n '{cleanup_proof:"confirmed_absent",customer_workload:"ecs-express"}' >"${result_file}.cleanup"
    write_result "$operation" "SUCCEEDED" "${result_file}.cleanup"
    ;;
esac
