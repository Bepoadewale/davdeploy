#!/usr/bin/env bash
set -euo pipefail
umask 077

operation="${1:-}"
script_dir="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
root="${repo_root}/infrastructure/terraform/connection-template-host"
plans_root="${repo_root}/.local/template-host-plans"
state_key="davdeploy/connection-template-host.tfstate"
manifest_tool="${repo_root}/scripts/template_host_saved_plan.py"

fail() {
  echo "$1" >&2
  exit 2
}

require() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "${name} is required"
}

if [[ "$operation" == "apply-saved-plan" ]]; then
  [[ "$#" -eq 3 ]] || fail "usage: $0 apply-saved-plan <plan-directory> <reviewed-sha256>"
else
  [[ "$#" -eq 1 ]] || fail "usage: $0 {plan|apply-saved-plan <plan-directory> <reviewed-sha256>|destroy}"
fi
case "$operation" in
  plan|apply-saved-plan|destroy) ;;
  *) fail "usage: $0 {plan|apply-saved-plan <plan-directory> <reviewed-sha256>|destroy}" ;;
esac

require EXPECTED_AWS_ACCOUNT_ID
require TF_STATE_BUCKET
require TF_LOCK_TABLE
require AWS_REGION
require DAVDEPLOY_TEMPLATE_BUCKET

if [[ -n "${AWS_PROFILE:-}" ]]; then
  account="$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)"
else
  account="$(aws sts get-caller-identity --query Account --output text)"
fi
[[ "$account" == "$EXPECTED_AWS_ACCOUNT_ID" ]] || fail "AWS account guard failed"

vars=("-var=region=${AWS_REGION}" "-var=bucket_name=${DAVDEPLOY_TEMPLATE_BUCKET}")

init_terraform() {
  terraform -chdir="$root" init -input=false \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="key=${state_key}" \
    -backend-config="dynamodb_table=${TF_LOCK_TABLE}" \
    -backend-config="region=${AWS_REGION}"
}

ensure_plan_root() {
  [[ ! -L "${repo_root}/.local" && ! -L "$plans_root" ]] || fail "Saved-plan root must not be a symlink"
  mkdir -p "$plans_root"
  chmod 700 "$plans_root"
  repo_root_real="$(cd -P "$repo_root" && pwd)"
  plans_root_real="$(cd -P "$plans_root" && pwd)"
  [[ "$plans_root_real" == "${repo_root_real}/.local/template-host-plans" ]] || \
    fail "Saved-plan root must remain under the repository .local directory"
}

case "$operation" in
  plan)
    init_terraform
    ensure_plan_root
    plan_dir="$(mktemp -d "${plans_root}/plan.XXXXXX")"
    chmod 700 "$plan_dir"
    plan_file="${plan_dir}/tfplan"

    terraform -chdir="$root" plan -input=false -no-color -out="$plan_file" "${vars[@]}"
    chmod 600 "$plan_file"
    terraform -chdir="$root" show -no-color "$plan_file"

    terraform_version="$(terraform version -json | python3 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])')"
    git_commit="$(git -C "$repo_root" rev-parse HEAD)"
    python3 "$manifest_tool" create \
      --plan "$plan_file" \
      --manifest "${plan_dir}/manifest.json" \
      --repo-root "$repo_root" \
      --terraform-root "$root" \
      --sha256 "$(shasum -a 256 "$plan_file" | awk '{print $1}')" \
      --git-commit "$git_commit" \
      --terraform-version "$terraform_version" \
      --account "$account" \
      --region "$AWS_REGION" \
      --state-bucket "$TF_STATE_BUCKET" \
      --state-key "$state_key" \
      --lock-table "$TF_LOCK_TABLE" \
      --template-bucket "$DAVDEPLOY_TEMPLATE_BUCKET"

    echo "Saved plan directory: ${plan_dir}"
    echo "Reviewed plan SHA-256: $(shasum -a 256 "$plan_file" | awk '{print $1}')"
    echo "Source commit: ${git_commit}"
    echo "After reviewing this exact plan, run apply-saved-plan with that directory and digest."
    ;;
  apply-saved-plan)
    plan_dir="$2"
    reviewed_sha256="$3"
    [[ "${CONFIRM_TEMPLATE_HOST_APPLY:-}" == "APPLY_DAVDEPLOY_TEMPLATE_HOST" ]] || \
      fail "Set CONFIRM_TEMPLATE_HOST_APPLY=APPLY_DAVDEPLOY_TEMPLATE_HOST after reviewing the saved plan"
    [[ "$reviewed_sha256" =~ ^[a-f0-9]{64}$ ]] || fail "Reviewed plan SHA-256 is invalid"
    [[ -d "$plan_dir" && ! -L "$plan_dir" ]] || fail "Saved-plan directory is unavailable"
    ensure_plan_root
    plan_dir_real="$(cd -P "$plan_dir" && pwd)"
    [[ "$plan_dir_real" == "$plans_root_real"/* ]] || fail "Saved plan must be under .local/template-host-plans"
    plan_file="${plan_dir_real}/tfplan"
    manifest_file="${plan_dir_real}/manifest.json"
    [[ -f "$plan_file" && ! -L "$plan_file" ]] || fail "Saved Terraform plan is unavailable"
    [[ -f "$manifest_file" && ! -L "$manifest_file" ]] || fail "Saved-plan manifest is unavailable"

    terraform_version="$(terraform version -json | python3 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])')"
    git_commit="$(git -C "$repo_root" rev-parse HEAD)"
    python3 "$manifest_tool" verify \
      --plan "$plan_file" \
      --manifest "$manifest_file" \
      --repo-root "$repo_root" \
      --terraform-root "$root" \
      --reviewed-sha256 "$reviewed_sha256" \
      --git-commit "$git_commit" \
      --terraform-version "$terraform_version" \
      --account "$account" \
      --region "$AWS_REGION" \
      --state-bucket "$TF_STATE_BUCKET" \
      --state-key "$state_key" \
      --lock-table "$TF_LOCK_TABLE" \
      --template-bucket "$DAVDEPLOY_TEMPLATE_BUCKET"

    init_terraform
    terraform -chdir="$root" apply -input=false "$plan_file"
    ;;
  destroy)
    [[ "${CONFIRM_TEMPLATE_HOST_DESTROY:-}" == "DESTROY_DAVDEPLOY_TEMPLATE_HOST" ]] || {
      fail "Set CONFIRM_TEMPLATE_HOST_DESTROY=DESTROY_DAVDEPLOY_TEMPLATE_HOST"
    }
    init_terraform
    terraform -chdir="$root" destroy -input=false -auto-approve "${vars[@]}"
    ;;
  *)
    fail "usage: $0 {plan|apply-saved-plan <plan-directory> <reviewed-sha256>|destroy}"
    ;;
esac
