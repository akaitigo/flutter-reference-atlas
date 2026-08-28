CORE_COMMIT := cf9e6e2d981305c83f970c1f21a1ddc9c1109263
CORE_DIR ?= ../reference-atlas-core
ATLAS_BIN ?= .tools/bin/atlas
ATLAS_GO_CACHE ?= $(CURDIR)/.tools/go-build
CORE_SNAPSHOT ?= $(CURDIR)/.tools/reference-atlas-core-cf9e6e2
FORMAL_SDK ?= $(CURDIR)/.tools/flutter-3.47.1/flutter
FORMAL_FLUTTER ?= $(FORMAL_SDK)/bin/flutter
FORMAL_DART ?= $(FORMAL_SDK)/bin/dart
FORMAL_ENV ?= env XDG_CONFIG_HOME=$(CURDIR)/.tools/xdg-config

.PHONY: atlas-bootstrap atlas-validate atlas-audit overlay-validate validate formal-local format analyze dart-test flutter-test test skill-eval runbooks legal check

atlas-bootstrap:
	@git -C "$(CORE_DIR)" cat-file -e "$(CORE_COMMIT)^{commit}" || { echo "エラー: Core commit $(CORE_COMMIT)を参照できません。"; exit 1; }
	@mkdir -p .tools/bin
	@mkdir -p "$(CORE_SNAPSHOT)"
	@git -C "$(CORE_DIR)" archive "$(CORE_COMMIT)" | tar -x -C "$(CORE_SNAPSHOT)"
	@cd "$(CORE_SNAPSHOT)" && GOCACHE="$(ATLAS_GO_CACHE)" go build -o "$(CURDIR)/$(ATLAS_BIN)" ./cmd/atlas

atlas-validate:
	@$(ATLAS_BIN) validate atlas.yaml mastery.yaml sources.lock.yaml coverage.yaml skill.package.yaml third_party/manifest.yaml provenance.yaml evals/flutter-router.skill-eval.json evidence/container-conflict.evidence.yaml evidence/formal-local-closure.evidence.yaml evidence/router-eval.evidence.yaml
	@for claim in claims/*.claim.json; do $(ATLAS_BIN) validate "$$claim" || exit 1; done

atlas-audit:
	@$(ATLAS_BIN) audit .

overlay-validate:
	@GOCACHE="$(ATLAS_GO_CACHE)" go run ./tooling/atlascheck
	@python3 tooling/generate_claim_entities.py --check

validate: atlas-validate atlas-audit overlay-validate

formal-local:
	@mkdir -p .tools/xdg-config
	@$(FORMAL_ENV) $(FORMAL_DART) run tooling/evidence_capture/bin/capture.dart --sdk "$(FORMAL_SDK)" --output .tools/formal-local-latest.json

format:
	@$(FORMAL_DART) format --output=none --set-exit-if-changed labs tooling/evidence_capture reference-systems/operations-workspace/lib reference-systems/operations-workspace/test reference-systems/operations-workspace/integration_test reference-systems/operations-workspace/test_driver
	@gofmt -w tooling/atlascheck

analyze:
	@cd reference-systems/operations-workspace && $(FORMAL_ENV) $(FORMAL_FLUTTER) analyze
	@$(FORMAL_DART) analyze labs/platform-integration

dart-test:
	@$(FORMAL_DART) run labs/offline-conflict-resolution/bin/verify.dart
	@$(FORMAL_DART) run labs/operations-drill/bin/verify.dart
	@$(FORMAL_DART) run labs/security-boundary/bin/verify.dart
	@$(FORMAL_DART) run labs/platform-integration/bin/verify.dart
	@$(FORMAL_DART) run labs/platform-integration/test/source_contract_verifier_test.dart
	@$(FORMAL_DART) run labs/platform-integration/bin/verify_ffi_runtime.dart
	@python3 -m unittest tooling/surface_inventory/test_generate.py
	@python3 tooling/surface_inventory/generate.py --sdk-root "$(FORMAL_SDK)" --output baseline/public-surface-inventory.json --check
	@GOCACHE="$(ATLAS_GO_CACHE)" go test ./tooling/atlascheck

flutter-test:
	@cd labs/framework-element-reconciliation && $(FORMAL_ENV) $(FORMAL_FLUTTER) test
	@cd labs/framework-rendering-pipeline && $(FORMAL_ENV) $(FORMAL_FLUTTER) test
	@cd labs/widget-lifecycle && $(FORMAL_ENV) $(FORMAL_FLUTTER) test
	@cd reference-systems/operations-workspace && $(FORMAL_ENV) $(FORMAL_FLUTTER) test

test: dart-test flutter-test

skill-eval:
	@python3 evals/evaluate.py --output evidence/artifacts/router-eval-report.json --skill-eval-output evals/flutter-router.skill-eval.json

runbooks:
	@scripts/validate-runbooks.sh

legal:
	@test -s LICENSE
	@test -s NOTICE
	@test -s third_party/manifest.yaml
	@test -s sbom.spdx.json
	@python3 tooling/generate_supply_chain.py --check
	@python3 tooling/generate_provenance.py --check
	@scripts/check-publication-hygiene.sh

check: formal-local validate test analyze skill-eval runbooks legal
