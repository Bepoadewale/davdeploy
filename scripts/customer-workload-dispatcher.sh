#!/usr/bin/env bash
set -euo pipefail

require() { [[ -n "${!1:-}" ]] || { echo "$1 is required" >&2; exit 2; }; }
require DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON
require DAVDEPLOY_EXECUTION_OPERATION

if ! jq -e '
  type == "array" and length == 1 and
  (.[0] | type == "object" and
    ((keys | sort) == ["dependencies", "input_bindings", "instance_id", "module_id", "operation", "renderer", "resource_tags"] or
      (keys | sort) == ["dependencies", "module_id", "operation", "renderer", "resource_tags"]) and
    (.module_id | type == "string") and
    ((.instance_id // .module_id) | type == "string" and length > 0) and
    (.operation | type == "string") and
    (.dependencies | type == "array" and all(.[]; type == "string")) and
    ((.input_bindings // []) | type == "array" and all(.[];
      type == "object" and
      (keys | sort == ["input_name", "source_instance_id", "source_output"]) and
      (.input_name | type == "string" and length > 0) and
      (.source_instance_id | type == "string" and length > 0) and
      (.source_output | type == "string" and length > 0))) and
    (.resource_tags | type == "object" and all(.[]; type == "string")) and
    (.renderer | type == "object" and
      (keys | sort == ["runner_script", "terraform_root"]) and
      (.terraform_root | type == "string") and
      (.runner_script | type == "string")))
' <<<"$DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON" >/dev/null; then
  echo "Lifecycle work must contain one typed renderer entry" >&2
  exit 2
fi

module_id="$(jq -r '.[0].module_id' <<<"$DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON")"
work_operation="$(jq -r '.[0].operation' <<<"$DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON")"
terraform_root="$(jq -r '.[0].renderer.terraform_root' <<<"$DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON")"
runner_script="$(jq -r '.[0].renderer.runner_script' <<<"$DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON")"

case "$module_id:$terraform_root:$runner_script" in
  aws-managed-application:infrastructure/terraform/customer-workload-app-runner-pilot:scripts/customer-workload-app-runner-pilot.sh)
    script="scripts/customer-workload-app-runner-pilot.sh"
    ;;
  aws-serverless-api:infrastructure/terraform/customer-workload-serverless-api:scripts/customer-workload-serverless-api.sh)
    [[ "${DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION:-false}" == "true" ]] || {
      echo "Serverless API hosted certification route is disabled" >&2; exit 2;
    }
    script="scripts/customer-workload-serverless-api.sh"
    ;;
  aws-file-storage:infrastructure/terraform/customer-workload-private-s3:scripts/customer-workload-private-s3.sh)
    [[ "${DAVDEPLOY_ENABLE_PRIVATE_S3_HOSTED_CERTIFICATION:-false}" == "true" ]] || {
      echo "Private S3 hosted certification route is disabled" >&2; exit 2;
    }
    script="scripts/customer-workload-private-s3.sh"
    ;;
  *)
    echo "Module renderer is unknown or not enabled for hosted execution: ${module_id}" >&2
    exit 2
    ;;
esac

case "$module_id:$work_operation:$DAVDEPLOY_EXECUTION_OPERATION" in
  aws-managed-application:plan:plan|aws-managed-application:plan:destroy-plan|\
  aws-managed-application:apply:apply-saved-plan|\
  aws-managed-application:destroy:destroy-saved-plan|\
  aws-managed-application:build-push-image:build-push-image|\
  aws-serverless-api:plan:plan|aws-serverless-api:plan:destroy-plan|\
  aws-serverless-api:destroy_plan:destroy-plan|\
  aws-serverless-api:build_artifact:build-artifact|\
  aws-serverless-api:apply:apply-saved-plan|\
  aws-serverless-api:observe:health|\
  aws-serverless-api:destroy:destroy-saved-plan|\
  aws-serverless-api:verify_cleanup:verify-cleanup)
    ;;
  aws-file-storage:plan:plan|aws-file-storage:plan:destroy-plan|\
  aws-file-storage:destroy_plan:destroy-plan|\
  aws-file-storage:apply:apply-saved-plan|\
  aws-file-storage:observe:observe|\
  aws-file-storage:destroy:destroy-saved-plan|\
  aws-file-storage:verify_cleanup:verify-cleanup)
    ;;
  *)
    echo "Lifecycle operation does not match the approved runner operation" >&2
    exit 2
    ;;
esac

resolved_inputs_json="${DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON:-}"
[[ -n "$resolved_inputs_json" ]] || resolved_inputs_json='{}'
if ! jq -e '
  type == "object" and
  all(keys[]; . == "uploads_bucket_name") and
  all(.[]; type == "string")
' <<<"$resolved_inputs_json" >/dev/null; then
  echo "Resolved renderer inputs contain unsupported or malformed values" >&2
  exit 2
fi
if ! jq -e --argjson inputs "$resolved_inputs_json" '
  .[0] as $work |
  ($work.input_bindings // []) as $bindings |
  ($bindings | map(.input_name) | sort) == ($inputs | keys | sort) and
  all($bindings[]?; .input_name == "uploads_bucket_name" and .source_output == "bucket_name") and
  ($work.module_id == "aws-serverless-api" or ($bindings | length == 0))
' <<<"$DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON" >/dev/null; then
  echo "Resolved inputs do not match the selected renderer's declared references" >&2
  exit 2
fi

if [[ "$module_id:$work_operation:$DAVDEPLOY_EXECUTION_OPERATION" == \
  "aws-serverless-api:build_artifact:build-artifact" ]]; then
  script="scripts/customer-serverless-artifact-build.py"
  exec python3 "$script"
fi

exec bash "$script" "$DAVDEPLOY_EXECUTION_OPERATION"
