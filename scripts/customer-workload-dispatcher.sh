#!/usr/bin/env bash
set -euo pipefail

require() { [[ -n "${!1:-}" ]] || { echo "$1 is required" >&2; exit 2; }; }
require DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON
require DAVDEPLOY_EXECUTION_OPERATION

if ! jq -e '
  type == "array" and length == 1 and
  (.[0] | type == "object" and
    (keys | sort == ["dependencies", "module_id", "operation", "renderer", "resource_tags"]) and
    (.module_id | type == "string") and
    (.operation | type == "string") and
    (.dependencies | type == "array" and all(.[]; type == "string")) and
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
  *)
    echo "Module renderer is unknown or not enabled for hosted execution: ${module_id}" >&2
    exit 2
    ;;
esac

case "$work_operation:$DAVDEPLOY_EXECUTION_OPERATION" in
  plan:plan|plan:destroy-plan|apply:apply-saved-plan|destroy:destroy-saved-plan|build-push-image:build-push-image)
    ;;
  *)
    echo "Lifecycle operation does not match the approved runner operation" >&2
    exit 2
    ;;
esac

if [[ "$(jq '.[0].dependencies | length' <<<"$DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON")" -ne 0 ]]; then
  echo "This renderer accepts no unresolved module dependencies" >&2
  exit 2
fi

exec bash "$script" "$DAVDEPLOY_EXECUTION_OPERATION"
