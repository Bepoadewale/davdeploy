#!/usr/bin/env bash
set -euo pipefail

operation="${1:-}"
root="infrastructure/terraform/customer-workload-app-runner-pilot"

require() {
  local name="$1"
  [[ -n "${!name:-}" ]] || { echo "${name} is required" >&2; exit 2; }
}

require EXPECTED_AWS_ACCOUNT_ID
require TF_STATE_BUCKET
require TF_LOCK_TABLE
require AWS_REGION
require DAVDEPLOY_CUSTOMER_CONNECTION_ID
require DAVDEPLOY_CUSTOMER_APP_RUNNER_ECR_ROLE_ARN
require DAVDEPLOY_CUSTOMER_APP_RUNNER_RUNTIME_ROLE_ARN
require DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN
require DAVDEPLOY_EXTERNAL_ID_SECRET_ARN
require DAVDEPLOY_EXECUTION_RUN_ID
require DAVDEPLOY_EXECUTION_RESULT_S3_URI

connection_id="${DAVDEPLOY_CUSTOMER_CONNECTION_ID}"
service_name="${DAVDEPLOY_CUSTOMER_SERVICE_NAME:-davdeploy-${connection_id}-workload}"
app_runner_service_name="${DAVDEPLOY_CUSTOMER_APP_RUNNER_SERVICE_NAME:-${service_name}}"
repository_name="${DAVDEPLOY_CUSTOMER_ECR_REPOSITORY_NAME:-davdeploy-${connection_id}-workload}"
deployment_scope="${DAVDEPLOY_CUSTOMER_DEPLOYMENT_SCOPE:-customer-sandbox}"
customer_vpc_cidr="${DAVDEPLOY_CUSTOMER_VPC_CIDR:-10.84.0.0/16}"
platform_vpc_cidr="${DAVDEPLOY_PLATFORM_VPC_CIDR:-10.42.0.0/16}"
source_repository="${DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY:-https://github.com/Bepoadewale/ai-platform-control-plane}"
source_commit="${DAVDEPLOY_CUSTOMER_SOURCE_COMMIT:-unknown}"
plan_digest="${DAVDEPLOY_CUSTOMER_PLAN_DIGEST:-customer-workload-pilot-local-approval}"
image_identifier="${DAVDEPLOY_CUSTOMER_IMAGE_IDENTIFIER:-placeholder.invalid/davdeploy-customer-workload:unset}"
enable_service="${DAVDEPLOY_ENABLE_CUSTOMER_SERVICE:-false}"
result_uri="${DAVDEPLOY_EXECUTION_RESULT_S3_URI}"
saved_plan_uri="${DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI:-${result_uri%/result.json}/terraform.tfplan}"
saved_plan_sha256="${DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256:-}"
result_file="/tmp/davdeploy-execution-result.json"
saved_plan_file="/tmp/davdeploy-${DAVDEPLOY_EXECUTION_RUN_ID}.tfplan"

aws_args=()
if [[ -n "${AWS_PROFILE:-}" ]]; then
  aws_args+=(--profile "$AWS_PROFILE")
fi
customer_aws_args=()
customer_credentials_file="/tmp/davdeploy-customer-${DAVDEPLOY_EXECUTION_RUN_ID}.credentials"
customer_profile="davdeploy-customer"
source_dir=""

cleanup() {
  rm -f "$customer_credentials_file" "$result_file" "$saved_plan_file"
  [[ -z "$source_dir" ]] || rm -rf "$source_dir"
}
trap cleanup EXIT

external_id="$(aws secretsmanager get-secret-value "${aws_args[@]}" --secret-id "$DAVDEPLOY_EXTERNAL_ID_SECRET_ARN" --query SecretString --output text)"
[[ -n "$external_id" && "$external_id" != "None" ]] || { echo "Customer connection ExternalId is unavailable" >&2; exit 3; }
[[ "$deployment_scope" == "customer-sandbox" ]] || { echo "Customer deployment scope guard failed" >&2; exit 3; }
[[ "$customer_vpc_cidr" != "$platform_vpc_cidr" ]] || { echo "Customer and platform VPC CIDRs must differ" >&2; exit 3; }

assume_customer_execution_role() {
  local credentials
  credentials="$(aws sts assume-role "${aws_args[@]}" \
    --role-arn "$DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN" \
    --role-session-name "davdeploy-customer-${DAVDEPLOY_EXECUTION_RUN_ID}" \
    --external-id "$external_id" \
    --duration-seconds 3600 \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text)"
  local customer_access_key_id customer_secret_access_key customer_session_token
  read -r customer_access_key_id customer_secret_access_key customer_session_token <<<"$credentials"
  unset external_id
  [[ -n "$customer_access_key_id" && -n "$customer_secret_access_key" && -n "$customer_session_token" ]] || {
    echo "Scoped customer execution role assumption returned incomplete credentials" >&2
    exit 3
  }
  umask 077
  cat >"$customer_credentials_file" <<EOF
[${customer_profile}]
aws_access_key_id=${customer_access_key_id}
aws_secret_access_key=${customer_secret_access_key}
aws_session_token=${customer_session_token}
EOF
  export AWS_SHARED_CREDENTIALS_FILE="$customer_credentials_file"
  customer_aws_args=(--profile "$customer_profile")
  echo "Assumed scoped customer execution role for this bounded run"
}

assume_customer_execution_role

tf_vars=(
  "-var=region=${AWS_REGION}"
  "-var=expected_account_id=${EXPECTED_AWS_ACCOUNT_ID}"
  "-var=deployment_scope=${deployment_scope}"
  "-var=connection_id=${connection_id}"
  "-var=app_runner_ecr_access_role_arn=${DAVDEPLOY_CUSTOMER_APP_RUNNER_ECR_ROLE_ARN}"
  "-var=app_runner_runtime_role_arn=${DAVDEPLOY_CUSTOMER_APP_RUNNER_RUNTIME_ROLE_ARN}"
  "-var=customer_vpc_cidr=${customer_vpc_cidr}"
  "-var=platform_vpc_cidr=${platform_vpc_cidr}"
  "-var=service_name=${service_name}"
  "-var=app_runner_service_name=${app_runner_service_name}"
  "-var=ecr_repository_name=${repository_name}"
  "-var=source_repository=${source_repository}"
  "-var=source_commit=${source_commit}"
  "-var=plan_digest=${plan_digest}"
  "-var=image_identifier=${image_identifier}"
  "-var=enable_service=${enable_service}"
)

tf_init() {
  terraform -chdir="$root" init -input=false -reconfigure \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="key=davdeploy/customer/${connection_id}/workload-app-runner.tfstate" \
    -backend-config="dynamodb_table=${TF_LOCK_TABLE}" \
    -backend-config="region=${AWS_REGION}"
}

tf_output() {
  terraform -chdir="$root" output -json
}

ensure_app_runner_service_linked_role() {
  local service_name="$1"
  local display_name="$2"
  local output
  if output="$(aws iam create-service-linked-role "${customer_aws_args[@]}" \
    --aws-service-name "$service_name" 2>&1)"; then
    echo "Created the AWS-managed ${display_name} service-linked role"
    return 0
  fi
  if [[ "$output" == *"has been taken"* || "$output" == *"already exists"* ]]; then
    echo "AWS-managed ${display_name} service-linked role already exists"
    return 0
  fi
  echo "$output" >&2
  return 1
}

write_result() {
  local phase="$1"
  local status="$2"
  local detail_file="${3:-}"
  local detail='{}'
  if [[ -n "$detail_file" && -f "$detail_file" ]]; then
    detail="$(cat "$detail_file")"
  fi
  jq -n \
    --arg run_id "$DAVDEPLOY_EXECUTION_RUN_ID" \
    --arg phase "$phase" \
    --arg status "$status" \
    --arg connection_id "$connection_id" \
    --arg digest "$plan_digest" \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson detail "$detail" \
    '{schema_version:"davdeploy.customer_execution_result.v1",run_id:$run_id,phase:$phase,status:$status,connection_id:$connection_id,plan_digest:$digest,generated_at:$generated_at,detail:$detail}' \
    >"$result_file"
  aws s3 cp "$result_file" "$result_uri" --only-show-errors
}

service_arn() {
  terraform -chdir="$root" output -raw app_runner_service_arn
}

service_url() {
  terraform -chdir="$root" output -raw app_runner_service_url
}

case "$operation" in
  plan|destroy-plan)
    tf_init
    plan_args=(-input=false -out="$saved_plan_file")
    [[ "$operation" == "destroy-plan" ]] && plan_args+=(-destroy)
    terraform -chdir="$root" plan "${plan_args[@]}" "${tf_vars[@]}"
    plan_sha256="$(shasum -a 256 "$saved_plan_file" | awk '{print $1}')"
    terraform -chdir="$root" show -json "$saved_plan_file" | jq '{
      format_version,
      terraform_version,
      resource_changes: [(.resource_changes // [])[] | {
        address,
        mode,
        type,
        name,
        provider_name,
        actions: .change.actions
      }]
    }' >/tmp/davdeploy-plan-summary.json
    aws s3 cp "$saved_plan_file" "$saved_plan_uri" --only-show-errors
    jq -n --arg saved_plan_s3_uri "$saved_plan_uri" --arg saved_plan_sha256 "$plan_sha256" --slurpfile summary /tmp/davdeploy-plan-summary.json \
      '{saved_plan_s3_uri:$saved_plan_s3_uri,saved_plan_sha256:$saved_plan_sha256,plan_summary:$summary[0]}' \
      >/tmp/davdeploy-plan-result.json
    write_result "$operation" "SUCCEEDED" /tmp/davdeploy-plan-result.json
    ;;
  apply-saved-plan)
    [[ -n "$saved_plan_sha256" ]] || {
      echo "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256 is required for an artifact-bound apply" >&2; exit 2;
    }
    tf_init
    aws s3 cp "$saved_plan_uri" "$saved_plan_file" --only-show-errors
    echo "${saved_plan_sha256}  ${saved_plan_file}" | shasum -a 256 --check --status || {
      echo "Saved Terraform plan digest mismatch" >&2; exit 3;
    }
    ensure_app_runner_service_linked_role apprunner.amazonaws.com "App Runner"
    ensure_app_runner_service_linked_role networking.apprunner.amazonaws.com "App Runner networking"
    terraform -chdir="$root" apply -input=false "$saved_plan_file"
    tf_output >/tmp/davdeploy-apply-outputs.json
    write_result "apply" "SUCCEEDED" /tmp/davdeploy-apply-outputs.json
    ;;
  destroy-saved-plan)
    [[ -n "$saved_plan_sha256" ]] || {
      echo "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256 is required for an artifact-bound destroy" >&2; exit 2;
    }
    tf_init
    aws s3 cp "$saved_plan_uri" "$saved_plan_file" --only-show-errors
    echo "${saved_plan_sha256}  ${saved_plan_file}" | shasum -a 256 --check --status || {
      echo "Saved Terraform destroy plan digest mismatch" >&2; exit 3;
    }
    terraform -chdir="$root" apply -input=false "$saved_plan_file"
    if aws apprunner list-services "${customer_aws_args[@]}" --query "ServiceSummaryList[?ServiceName=='${service_name}'].ServiceArn | [0]" --output text | grep -qv '^None$'; then
      echo "App Runner service still exists: ${service_name}" >&2; exit 1
    fi
    if aws ecr describe-repositories "${customer_aws_args[@]}" --repository-names "$repository_name" >/dev/null 2>&1; then
      echo "ECR repository still exists: ${repository_name}" >&2; exit 1
    fi
    if aws ec2 describe-vpcs "${customer_aws_args[@]}" --region "$AWS_REGION" --filters "Name=tag:Scope,Values=customer-sandbox" "Name=tag:ConnectionId,Values=${connection_id}" --query 'Vpcs[0].VpcId' --output text | grep -qv '^None$'; then
      echo "Customer sandbox VPC still exists" >&2; exit 1
    fi
    jq -n --arg proof "confirmed_absent" --arg scope "$deployment_scope" \
      '{destroy_proof:$proof, deployment_scope:$scope, connection_roles_retained:true}' \
      >/tmp/davdeploy-destroy-result.json
    write_result "destroy" "SUCCEEDED" /tmp/davdeploy-destroy-result.json
    ;;
  build-push-image)
    require DAVDEPLOY_CUSTOMER_ECR_REPOSITORY_URL
    [[ "$source_repository" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || {
      echo "DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY must be a canonical GitHub HTTPS URL" >&2; exit 2;
    }
    [[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT must be a full immutable SHA-1 commit" >&2; exit 2;
    }
    tag="${DAVDEPLOY_CUSTOMER_IMAGE_TAG:-sha-${source_commit}}"
    source_dir="$(mktemp -d /tmp/davdeploy-source-${DAVDEPLOY_EXECUTION_RUN_ID}-XXXXXX)"
    git clone --no-checkout --filter=blob:none "$source_repository" "$source_dir"
    git -C "$source_dir" checkout --detach "$source_commit"
    checked_out_commit="$(git -C "$source_dir" rev-parse HEAD)"
    [[ "$checked_out_commit" == "$source_commit" ]] || {
      echo "Pinned repository checkout did not match the approved commit" >&2; exit 3;
    }
    [[ -f "$source_dir/control-plane/Dockerfile" ]] || {
      echo "Approved repository does not contain control-plane/Dockerfile" >&2; exit 3;
    }
    repo="${DAVDEPLOY_CUSTOMER_ECR_REPOSITORY_URL}"
    registry="${repo%%/*}"
    aws ecr get-login-password "${customer_aws_args[@]}" --region "$AWS_REGION" | docker login --username AWS --password-stdin "$registry"
    docker buildx build \
      --platform linux/amd64 \
      --provenance=false \
      --sbom=false \
      --push \
      -t "${repo}:${tag}" \
      -f "$source_dir/control-plane/Dockerfile" \
      "$source_dir"
    image_digest="$(aws ecr batch-get-image "${customer_aws_args[@]}" --repository-name "$repository_name" --image-ids "imageTag=${tag}" --query 'images[0].imageId.imageDigest' --output text)"
    [[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "ECR did not return an immutable image digest" >&2; exit 3; }
    jq -n \
      --arg repository "$source_repository" \
      --arg commit "$checked_out_commit" \
      --arg image_uri "${repo}:${tag}" \
      --arg image_digest "$image_digest" \
      --arg image_identifier "${repo}@${image_digest}" \
      '{source_repository:$repository,source_commit:$commit,image_uri:$image_uri,image_digest:$image_digest,image_identifier:$image_identifier}' \
      >/tmp/davdeploy-image-build-result.json
    write_result "build-push-image" "SUCCEEDED" /tmp/davdeploy-image-build-result.json
    ;;
  wait-ready)
    tf_init
    arn="$(service_arn)"
    for _ in {1..90}; do
      status="$(aws apprunner describe-service "${customer_aws_args[@]}" --service-arn "$arn" --query 'Service.Status' --output text)"
      echo "App Runner status: ${status}"
      [[ "$status" == "RUNNING" ]] && exit 0
      [[ "$status" == "CREATE_FAILED" || "$status" == "DELETE_FAILED" || "$status" == "OPERATION_IN_PROGRESS" || "$status" == "PAUSED" ]] || true
      sleep 10
    done
    echo "Timed out waiting for App Runner service to become RUNNING" >&2
    exit 1
    ;;
  smoke)
    tf_init
    url="$(service_url)"
    curl --fail --silent --show-error --max-time 15 "${url}/healthz" | jq -e '.status == "ok"' >/dev/null
    echo "Customer workload smoke passed: ${url}/healthz returned ok"
    ;;
  destroy)
    [[ "${CONFIRM_CUSTOMER_WORKLOAD_DESTROY:-}" == "DESTROY_CUSTOMER_WORKLOAD" ]] || {
      echo "Set CONFIRM_CUSTOMER_WORKLOAD_DESTROY=DESTROY_CUSTOMER_WORKLOAD" >&2; exit 2;
    }
    tf_init
    terraform -chdir="$root" destroy -input=false -auto-approve "${tf_vars[@]}"
    ;;
  verify-absent)
    missing_service="false"
    if aws apprunner list-services "${customer_aws_args[@]}" --query "ServiceSummaryList[?ServiceName=='${service_name}'].ServiceArn | [0]" --output text | grep -qv '^None$'; then
      echo "App Runner service still exists: ${service_name}" >&2
      exit 1
    else
      missing_service="true"
    fi
    if aws ecr describe-repositories "${customer_aws_args[@]}" --repository-names "$repository_name" >/dev/null 2>&1; then
      echo "ECR repository still exists: ${repository_name}" >&2
      exit 1
    fi
    if aws ec2 describe-vpcs "${customer_aws_args[@]}" --region "$AWS_REGION" \
      --filters "Name=tag:Scope,Values=customer-sandbox" "Name=tag:ConnectionId,Values=${connection_id}" \
      --query 'Vpcs[0].VpcId' --output text | grep -qv '^None$'; then
      echo "Customer sandbox VPC still exists" >&2
      exit 1
    fi
    echo "Customer workload AWS resources absent: service=${missing_service}, ecr_repository=deleted, vpc=deleted. Connection roles are retained for future approved workloads."
    ;;
  output)
    tf_init
    tf_output
    ;;
  *)
    echo "usage: $0 {plan|destroy-plan|apply-saved-plan|destroy-saved-plan|build-push-image|wait-ready|smoke|destroy|verify-absent|output}" >&2
    exit 2
    ;;
esac
