#!/usr/bin/env bash
set -euo pipefail

terraform_bin="${DAVDEPLOY_TERRAFORM_BIN:-terraform}"
temporary_parent="${TMPDIR:-/tmp}"
temporary_parent="${temporary_parent%/}"
validation_root="$(mktemp -d "${temporary_parent}/davdeploy-tfvalidate.XXXXXX")"
plugin_cache_dir="${TF_PLUGIN_CACHE_DIR:-${XDG_CACHE_HOME:-${HOME}/.cache}/davdeploy/terraform-plugin-cache}"

cleanup() {
  case "${validation_root}" in
    "${temporary_parent}"/davdeploy-tfvalidate.*)
      rm -rf -- "${validation_root}"
      ;;
    *)
      printf 'Refusing to clean unexpected validation path: %s\n' "${validation_root}" >&2
      ;;
  esac
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "${plugin_cache_dir}"
export TF_PLUGIN_CACHE_DIR="${plugin_cache_dir}"

roots=(
  infrastructure/terraform/davdeploy-bootstrap
  infrastructure/terraform/bootstrap
  infrastructure/terraform/management-identity
  infrastructure/terraform/control-plane-runtime-identity
  infrastructure/terraform/customer-connection
  infrastructure/terraform/connection-template-host
  infrastructure/terraform/app-runner-runtime
  infrastructure/terraform/terraform-operations-bootstrap
  infrastructure/terraform/serverless-control-plane
  infrastructure/terraform/customer-workload-app-runner-pilot
  infrastructure/terraform/customer-workload-serverless-api
  infrastructure/terraform/renderers/app-runner-plan
  infrastructure/terraform/pilot
)

"${terraform_bin}" fmt -check -recursive infrastructure/terraform

for root in "${roots[@]}"; do
  root_key="${root//\//-}"
  export TF_DATA_DIR="${validation_root}/${root_key}"
  "${terraform_bin}" -chdir="${root}" init -backend=false -input=false
  "${terraform_bin}" -chdir="${root}" validate
done
