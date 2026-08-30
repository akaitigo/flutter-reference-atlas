CORE_COMMIT := cf9e6e2d981305c83f970c1f21a1ddc9c1109263
CORE_DIR ?= ../reference-atlas-core
ATLAS_BIN ?= .tools/bin/atlas
CORE_V2_COMMIT := 072d7ca77981f51754e824d70c6d4ecd55ea67e5
CORE_V2_DIR ?= ../reference-atlas-core
ATLAS_V2_BIN ?= .tools/bin/atlas-v2
ATLAS_GO_CACHE ?= $(CURDIR)/.tools/go-build
CORE_SNAPSHOT ?= $(CURDIR)/.tools/reference-atlas-core-cf9e6e2
CORE_V2_SNAPSHOT ?= $(CURDIR)/.tools/reference-atlas-core-072d7ca
FE_DEPTH_REFERENCE_DIR ?= ../frontend-behavior-atlas
FE_REFERENCE_SYSTEM_DIR ?= ../frontend-behavior-atlas
FORMAL_SDK ?= $(CURDIR)/.tools/flutter-3.47.1/flutter
FORMAL_FLUTTER ?= $(FORMAL_SDK)/bin/flutter
FORMAL_DART ?= $(FORMAL_SDK)/bin/dart
FORMAL_ENV ?= env XDG_CONFIG_HOME=$(CURDIR)/.tools/xdg-config DASH__SUPPRESS_ANALYTICS=true FLUTTER_SUPPRESS_ANALYTICS=true

.PHONY: atlas-bootstrap atlas-v2-bootstrap atlas-validate atlas-audit core-v2-audit evidence-dependency-local evidence-dependency-audit overlay-validate sdk-binding-check ci-supply-chain-check authority-extract authority-review-queue authority-baseline-init authority-verify definitive-audit depth-reference-audit scenario-reference-audit non-regression-audit definitive-web-runtime reference-scenario-runtime scenario-proof validate formal-local format analyze dart-test flutter-test test skill-eval runbooks legal check

atlas-bootstrap:
	@git -C "$(CORE_DIR)" cat-file -e "$(CORE_COMMIT)^{commit}" || { echo "エラー: Core commit $(CORE_COMMIT)を参照できません。"; exit 1; }
	@mkdir -p .tools/bin
	@mkdir -p "$(CORE_SNAPSHOT)"
	@git -C "$(CORE_DIR)" archive "$(CORE_COMMIT)" | tar -x -C "$(CORE_SNAPSHOT)"
	@cd "$(CORE_SNAPSHOT)" && GOCACHE="$(ATLAS_GO_CACHE)" go build -o "$(CURDIR)/$(ATLAS_BIN)" ./cmd/atlas

atlas-v2-bootstrap:
	@git -C "$(CORE_V2_DIR)" cat-file -e "$(CORE_V2_COMMIT)^{commit}" || { echo "エラー: Core v2 commit $(CORE_V2_COMMIT)を参照できません。"; exit 1; }
	@mkdir -p .tools/bin
	@mkdir -p "$(CORE_V2_SNAPSHOT)"
	@git -C "$(CORE_V2_DIR)" archive "$(CORE_V2_COMMIT)" | tar -x -C "$(CORE_V2_SNAPSHOT)"
	@cd "$(CORE_V2_SNAPSHOT)" && GOCACHE="$(ATLAS_GO_CACHE)" go build -o "$(CURDIR)/$(ATLAS_V2_BIN)" ./cmd/atlas

atlas-validate:
	@$(ATLAS_BIN) validate atlas.yaml mastery.yaml sources.lock.yaml coverage.yaml skill.package.yaml third_party/manifest.yaml provenance.yaml evals/flutter-router.skill-eval.json evidence/android-emulator-integration.evidence.yaml evidence/container-conflict.evidence.yaml evidence/definitive-android-method-channel.evidence.yaml evidence/definitive-router-eval.evidence.yaml evidence/definitive-web-chrome.evidence.yaml evidence/formal-local-closure.evidence.yaml evidence/reference-scenario-runtime.evidence.yaml evidence/router-eval.evidence.yaml
	@for claim in claims/*.claim.json; do $(ATLAS_BIN) validate "$$claim" || exit 1; done

atlas-audit:
	@$(ATLAS_BIN) audit .

core-v2-audit:
	@$(ATLAS_V2_BIN) audit . --gate definitive

evidence-dependency-local:
	@python3 tooling/evidence_dependency/graph.py --check --check-baseline
	@python3 -m unittest tooling/evidence_dependency/test_graph.py

evidence-dependency-audit: evidence-dependency-local
	@$(ATLAS_V2_BIN) validate evidence/dependency-graph.json
	@$(ATLAS_V2_BIN) audit . --gate evidence-dependency

overlay-validate:
	@GOCACHE="$(ATLAS_GO_CACHE)" go run ./tooling/atlascheck
	@python3 tooling/generate_claim_entities.py --check

sdk-binding-check:
	@test -n "$(strip $(FORMAL_SDK))" || { echo "エラー: FORMAL_SDKが空です。"; exit 1; }
	@python3 -m unittest tooling/sdk_binding/test_verify.py
	@python3 tooling/sdk_binding/verify.py --sdk-root "$(FORMAL_SDK)"

ci-supply-chain-check:
	@python3 -m unittest tooling/ci_supply_chain/test_verify.py
	@python3 tooling/ci_supply_chain/verify.py

definitive-audit: sdk-binding-check
	@python3 -m unittest tooling/definitive_inventory/test_generate.py
	@python3 -m unittest tooling/definitive_android/test_report.py
	@python3 tooling/definitive_inventory/generate.py --sdk-root "$(FORMAL_SDK)" --check
	@$(MAKE) authority-verify
	@python3 -m unittest tooling/fe_parity/test_generate.py
	@python3 tooling/fe_parity/generate.py --check
	@$(MAKE) scenario-proof
	@$(MAKE) evidence-dependency-local

authority-extract:
	@python3 tooling/authority_extraction/extract.py
	@python3 tooling/authority_extraction/body_inventory.py
	@$(MAKE) authority-review-queue

authority-review-queue:
	@python3 tooling/authority_extraction/review_queue.py

authority-baseline-init:
	@python3 tooling/authority_extraction/body_baseline.py --write

authority-verify:
	@python3 -m unittest tooling/authority_extraction/test_verify.py
	@python3 -m unittest tooling/authority_extraction/test_body_inventory.py
	@python3 -m unittest tooling/authority_extraction/test_body_baseline.py
	@python3 -m unittest tooling/authority_extraction/test_review_queue.py
	@python3 tooling/authority_extraction/verify.py
	@python3 tooling/authority_extraction/verify_body_inventory.py
	@python3 tooling/authority_extraction/body_baseline.py
	@python3 tooling/authority_extraction/verify_review_queue.py

depth-reference-audit:
	@python3 tooling/fe_parity/generate.py --check --check-reference --reference-root "$(FE_DEPTH_REFERENCE_DIR)"

scenario-reference-audit:
	@python3 tooling/scenario_proof/generate.py --check --check-reference --reference-root "$(FE_REFERENCE_SYSTEM_DIR)"

non-regression-audit:
	@python3 -m unittest tooling/non_regression/test_audit.py
	@python3 tooling/non_regression/audit.py --check-snapshot
	@python3 tooling/evidence_dependency/graph.py --check --check-baseline

definitive-web-runtime:
	@FLUTTER_ATLAS_WEB_ARTIFACT="$(CURDIR)/.tools/definitive-web/ci-report.json" \
		FLUTTER_ATLAS_WEB_JS_LOG="$(CURDIR)/.tools/definitive-web/ci-js.log" \
		FLUTTER_ATLAS_WEB_WASM_LOG="$(CURDIR)/.tools/definitive-web/ci-wasm.log" \
		scripts/definitive-web-runtime.sh

reference-scenario-runtime:
	@FLUTTER_ATLAS_SCENARIO_OUTPUT_ROOT=.tools/reference-scenario-runtime/ci-evidence \
		scripts/reference-scenario-runtime.sh

scenario-proof:
	@python3 tooling/scenario_security_tranche/artifact_migration.py --check
	@python3 tooling/scenario_proof/generate.py --check
	@python3 -m unittest tooling/scenario_proof/test_generate.py
	@python3 -m unittest tooling/scenario_proof/test_atomic_publish.py
	@python3 -m unittest tooling/scenario_security_tranche/test_report.py
	@python3 -m unittest tooling/scenario_security_tranche/test_failure_record.py
	@python3 -m unittest tooling/scenario_security_tranche/test_artifact_migration.py
	@python3 -m unittest tooling/scenario_build_android/test_report.py
	@python3 -m unittest tooling/scenario_build_web/test_report.py

validate: sdk-binding-check ci-supply-chain-check atlas-validate atlas-audit overlay-validate definitive-audit non-regression-audit

formal-local:
	@mkdir -p .tools/xdg-config
	@$(FORMAL_ENV) $(FORMAL_DART) run tooling/evidence_capture/bin/capture.dart --sdk "$(FORMAL_SDK)" --output .tools/formal-local-latest.json

format:
	@$(FORMAL_DART) format --output=none --set-exit-if-changed labs tooling/evidence_capture reference-systems/operations-workspace/lib reference-systems/operations-workspace/test reference-systems/operations-workspace/integration_test reference-systems/operations-workspace/test_driver reference-systems/operations-workspace/packages/atlas_runtime_probe/lib reference-systems/operations-workspace/packages/atlas_runtime_probe/test
	@gofmt -w tooling/atlascheck

analyze:
	@cd reference-systems/operations-workspace && $(FORMAL_ENV) $(FORMAL_FLUTTER) analyze
	@cd reference-systems/operations-workspace/packages/atlas_runtime_probe && $(FORMAL_ENV) $(FORMAL_FLUTTER) analyze
	@$(FORMAL_DART) analyze labs/platform-integration

dart-test:
	@$(FORMAL_DART) run labs/offline-conflict-resolution/bin/verify.dart
	@$(FORMAL_DART) run labs/operations-drill/bin/verify.dart
	@$(FORMAL_DART) run labs/security-boundary/bin/verify.dart
	@$(FORMAL_DART) run labs/platform-integration/bin/verify.dart
	@$(FORMAL_DART) run labs/platform-integration/test/source_contract_verifier_test.dart
	@$(FORMAL_DART) run labs/platform-integration/bin/verify_ffi_runtime.dart
	@python3 -m unittest tooling/surface_inventory/test_generate.py
	@python3 -m unittest tooling/definitive_inventory/test_generate.py
	@python3 -m unittest tooling/definitive_web/test_report.py
	@python3 tooling/surface_inventory/generate.py --sdk-root "$(FORMAL_SDK)" --output baseline/public-surface-inventory.json --check
	@python3 tooling/definitive_inventory/generate.py --sdk-root "$(FORMAL_SDK)" --check
	@GOCACHE="$(ATLAS_GO_CACHE)" go test ./tooling/atlascheck

flutter-test:
	@cd reference-systems/operations-workspace/packages/atlas_runtime_probe && $(FORMAL_ENV) $(FORMAL_FLUTTER) test
	@cd labs/framework-element-reconciliation && $(FORMAL_ENV) $(FORMAL_FLUTTER) test
	@cd labs/framework-rendering-pipeline && $(FORMAL_ENV) $(FORMAL_FLUTTER) test
	@cd labs/widget-lifecycle && $(FORMAL_ENV) $(FORMAL_FLUTTER) test
	@cd reference-systems/operations-workspace && $(FORMAL_ENV) $(FORMAL_FLUTTER) test

test: dart-test flutter-test

skill-eval:
	@python3 evals/evaluate.py --output evidence/artifacts/router-eval-report.json --skill-eval-output evals/flutter-router.skill-eval.json
	@python3 evals/evaluate_definitive.py
	@python3 evals/evaluate_mastery.py
	@python3 -m unittest evals/test_mastery_eval.py

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

check: formal-local validate test analyze skill-eval definitive-web-runtime reference-scenario-runtime runbooks legal
