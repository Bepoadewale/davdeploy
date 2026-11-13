PYTHON ?= python3.12
VENV := .venv
PY := $(VENV)/bin/python
export PYTHONPATH := apps/api/src

.PHONY: help install lint test config-check bootstrap-local smoke local-load-smoke seed-demo-data demo demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check api-contract openapi-check openapi-update customer-plan-e2e customer-plan-persistence local-proof verify clean-local compose-logs opa-test terraform-validate kubernetes-render mcp-local validate-environment admin-diagnostics customer-aws-connection-plan customer-aws-connection-apply customer-aws-connection-destroy customer-aws-template-host-plan customer-aws-template-host-apply customer-aws-template-host-destroy pilot-guardrails-plan pilot-cloud-plan pilot-cloud-apply pilot-cloud-push-image pilot-cloud-bootstrap-runtime pilot-cloud-smoke pilot-cloud-validate pilot-cloud-destroy

help:
	@echo "davdeploy local commands"
	@echo ""
	@echo "  make install                 Create .venv and install dev dependencies"
	@echo "  make bootstrap-local         Build/start local API, worker, Postgres, OPA, Prometheus, Grafana, Tempo"
	@echo "  make smoke                   Check local service readiness"
	@echo "  make seed-demo-data          Seed realistic local developer/admin demo records"
	@echo "  make local-proof             Bootstrap, then run API contract, customer-plan E2E, seed data, trace check, verify"
	@echo "  make customer-plan-e2e       Prove developer submit, admin decision, self-approval, dry-run, destroy"
	@echo "  make config-check            Validate GitHub Actions variable/secret classification"
	@echo "  make verify                  Run lint, tests, and Compose config validation"
	@echo "  make validate-environment    Validate self-hosted configuration without cloud access"
	@echo "  make admin-diagnostics       Verify local database reachability"
	@echo "  make clean-local             Stop local stack and remove local volumes/.venv/.local"
	@echo ""
	@echo "Cloud-safety boundary: normal local targets never run Terraform apply, create AWS workload resources, write GitHub PRs, or deploy Kubernetes/GitOps."

install:
	command -v $(PYTHON) >/dev/null || { echo "Python 3.12 is required"; exit 1; }
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e '.[dev]'

lint:
	$(PY) -m ruff check apps/api/src tests scripts

test:
	$(PY) -m pytest -q

config-check:
	$(PYTHON) scripts/check_actions_configuration.py

bootstrap-local: install
	docker compose up -d --build

smoke:
	./scripts/smoke.sh

local-load-smoke:
	$(PY) scripts/local_load_smoke.py

seed-demo-data:
	$(PY) scripts/seed_demo_data.py

demo:
	$(PY) scripts/demo.py

demo-simple:
	$(PY) scripts/demo.py --simple

demo-complex:
	$(PY) scripts/demo.py --complex

demo-day2:
	$(PY) scripts/demo.py --day2

demo-degraded:
	$(PY) scripts/demo.py --degraded

demo-failure:
	$(PY) scripts/demo.py --failure

demo-readiness-failure:
	$(PY) scripts/demo.py --readiness-failure

trace-check:
	curl -fsS "$${DAVDEPLOY_TEMPO_BASE_URL:-http://127.0.0.1:3200}/ready" >/dev/null
	curl -fsS "$${DAVDEPLOY_TEMPO_BASE_URL:-http://127.0.0.1:3200}/api/search?limit=1" | grep -q 'davdeploy-api'
	@echo "Tempo received davdeploy traces."

api-contract:
	./scripts/api-contract.sh

openapi-check:
	$(PY) scripts/export_openapi.py

openapi-update:
	$(PY) scripts/export_openapi.py --write

customer-plan-e2e:
	$(PY) scripts/customer_plan_e2e.py

customer-plan-persistence:
	$(PY) scripts/customer_plan_e2e.py --verify-persistence

local-proof: bootstrap-local smoke api-contract customer-plan-e2e seed-demo-data trace-check verify

opa-test:
	docker compose exec -T opa opa test /policies

terraform-validate:
	./scripts/terraform-validate.sh

customer-aws-connection-plan:
	./scripts/customer-aws-connection.sh plan

customer-aws-connection-apply:
	./scripts/customer-aws-connection.sh apply

customer-aws-connection-destroy:
	./scripts/customer-aws-connection.sh destroy

customer-aws-template-host-plan:
	./scripts/customer-aws-template-host.sh plan

customer-aws-template-host-apply:
	./scripts/customer-aws-template-host.sh apply

customer-aws-template-host-destroy:
	./scripts/customer-aws-template-host.sh destroy

kubernetes-render:
	kubectl kustomize infrastructure/kubernetes/base >/dev/null
	@echo "Kubernetes contract rendered successfully. It was not applied to a cluster."

mcp-local:
	@test -n "$$DAVDEPLOY_TOKEN" || { echo "Set DAVDEPLOY_TOKEN first; MCP never obtains cloud credentials."; exit 1; }
	$(VENV)/bin/davdeploy-mcp

pilot-guardrails-plan:
	./scripts/pilot-cloud.sh guardrails-plan

pilot-cloud-plan:
	./scripts/pilot-cloud.sh plan

pilot-cloud-apply:
	./scripts/pilot-cloud.sh apply

pilot-cloud-push-image:
	./scripts/pilot-cloud.sh push-image

pilot-cloud-bootstrap-runtime:
	./scripts/pilot-cloud.sh bootstrap-runtime

pilot-cloud-smoke:
	./scripts/pilot-cloud.sh smoke

pilot-cloud-validate:
	./scripts/pilot-cloud.sh validate

pilot-cloud-destroy:
	./scripts/pilot-cloud.sh destroy

verify:
	$(MAKE) config-check
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) openapi-check
	docker compose config --quiet

validate-environment:
	$(PY) scripts/validate_environment.py

admin-diagnostics:
	$(PY) scripts/admin_diagnostics.py

compose-logs:
	docker compose logs --no-color

clean-local:
	docker compose down -v --remove-orphans
	rm -rf $(VENV) .local
