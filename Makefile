CORE_COMMIT := d5c0a6ce757fd5f43af837edd26f55c7325b811e
CORE_DIR ?= ../reference-atlas-core
ATLAS_BIN ?= .tools/bin/atlas
ATLAS_GO_CACHE ?= $(CURDIR)/.tools/go-build
CORE_SNAPSHOT ?= $(CURDIR)/.tools/reference-atlas-core-d5c0a6c

.PHONY: atlas-bootstrap atlas-validate atlas-audit overlay-validate validate format analyze dart-test flutter-test test skill-eval runbooks legal check

atlas-bootstrap:
	@git -C "$(CORE_DIR)" cat-file -e "$(CORE_COMMIT)^{commit}" || { echo "エラー: Core commit $(CORE_COMMIT)を参照できません。"; exit 1; }
	@mkdir -p .tools/bin
	@mkdir -p "$(CORE_SNAPSHOT)"
	@git -C "$(CORE_DIR)" archive "$(CORE_COMMIT)" | tar -x -C "$(CORE_SNAPSHOT)"
	@cd "$(CORE_SNAPSHOT)" && GOCACHE="$(ATLAS_GO_CACHE)" go build -o "$(CURDIR)/$(ATLAS_BIN)" ./cmd/atlas

atlas-validate:
	@$(ATLAS_BIN) validate atlas.yaml mastery.yaml sources.lock.yaml coverage.yaml skill.package.yaml evidence/container-conflict.evidence.yaml evidence/local-compatibility.evidence.yaml evidence/router-eval.evidence.yaml

atlas-audit:
	@$(ATLAS_BIN) audit .

overlay-validate:
	@GOCACHE="$(ATLAS_GO_CACHE)" go run ./tooling/atlascheck

validate: atlas-validate atlas-audit overlay-validate

format:
	@dart format --output=none --set-exit-if-changed labs reference-systems/operations-workspace/lib reference-systems/operations-workspace/test
	@gofmt -w tooling/atlascheck

analyze:
	@cd reference-systems/operations-workspace && flutter analyze

dart-test:
	@dart run labs/offline-conflict-resolution/bin/verify.dart
	@GOCACHE="$(ATLAS_GO_CACHE)" go test ./tooling/atlascheck

flutter-test:
	@cd labs/widget-lifecycle && flutter test
	@cd reference-systems/operations-workspace && flutter test

test: dart-test flutter-test

skill-eval:
	@python3 evals/evaluate.py

runbooks:
	@scripts/validate-runbooks.sh

legal:
	@test -s LICENSE
	@test -s NOTICE
	@test -s third_party/manifest.yaml
	@test -s sbom.spdx.json

check: validate test analyze skill-eval runbooks legal
