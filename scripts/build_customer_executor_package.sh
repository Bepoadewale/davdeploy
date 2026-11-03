#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_path="${1:-${repo_root}/dist/customer-executor/davdeploy-customer-executor.zip}"
case "${output_path}" in
  /*) ;;
  *) output_path="${repo_root}/${output_path}" ;;
esac

build_root="$(mktemp -d "${TMPDIR:-/tmp}/davdeploy-customer-executor.XXXXXX")"
cleanup() {
  case "${build_root}" in
    "${TMPDIR:-/tmp}"/davdeploy-customer-executor.*) rm -rf -- "${build_root}" ;;
    *) printf 'Refusing to clean unexpected path: %s\n' "${build_root}" >&2 ;;
  esac
}
trap cleanup EXIT

mkdir -p "$(dirname "${output_path}")" "${build_root}/package/infrastructure/terraform" "${build_root}/package/scripts"
rm -f "${output_path}"
cp -R "${repo_root}/infrastructure/terraform/customer-workload-app-runner-pilot" \
  "${build_root}/package/infrastructure/terraform/"
cp -R "${repo_root}/infrastructure/terraform/customer-workload-serverless-api" \
  "${build_root}/package/infrastructure/terraform/"
rm -rf "${build_root}/package/infrastructure/terraform/customer-workload-app-runner-pilot/.terraform"
rm -f "${build_root}/package/infrastructure/terraform/customer-workload-app-runner-pilot/.terraform.lock.hcl"
rm -rf "${build_root}/package/infrastructure/terraform/customer-workload-serverless-api/.terraform"
rm -f "${build_root}/package/infrastructure/terraform/customer-workload-serverless-api/.terraform.lock.hcl"
cp "${repo_root}/scripts/customer-workload-app-runner-pilot.sh" "${build_root}/package/scripts/"
cp "${repo_root}/scripts/customer-workload-serverless-api.sh" "${build_root}/package/scripts/"
cp "${repo_root}/scripts/customer-serverless-artifact-build.py" "${build_root}/package/scripts/"
cp "${repo_root}/scripts/customer-workload-dispatcher.sh" "${build_root}/package/scripts/"
(
  cd "${build_root}/package"
  zip -qr "${output_path}" .
)
printf 'Built %s\n' "${output_path}"
