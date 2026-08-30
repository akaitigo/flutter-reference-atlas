# Flutter 技術実証アトラス

`flutter-reference-atlas`は、Flutterを使う際の判断、実装、検証、運用を、一次資料と再実行可能な証拠へ接続する独立コミュニティプロジェクトです。単なるWidget一覧や巨大なサンプルアプリではありません。

## 現在の状態

**INCOMPLETE（Definitive Gate v2移行中）** — Core v1の履歴Releaseは保持しますが、Subject Definitiveを示す現行Gateは未通過です。

- 正式Baseline: Flutter 3.47.1 / Dart 3.13.1 / DevTools 2.60.0
- Coverage Epoch: 2026-08-28
- Core Contract: `reference-atlas-core` v1.0.0 commit `cf9e6e2d981305c83f970c1f21a1ddc9c1109263`
- Formal Local: 16/16 command pass（Framework、Product、FFI、Security、Recovery、Web release buildを含む）
- Container: 固定Dart 3.13.1 OCI Digest、network無効、Cleanup確認済み
- Android Emulator: `execution.android-emulator-integration.2026-08-28` pass（`medium_phone`、Android 16 / API 36 / arm64-v8a）
- Router Skill Eval: 64/64 pass、独立Forward Eval pass
- Historical Completion Certificate: `evidence/completion-certificate.json`（Core v1、source commit `766ee4226d23b55dd7ef1b0451f8162b6365bd0e`だけを証明）

Core v1 Certificateは[`evidence/history/core-v1-completion.record.yaml`](evidence/history/core-v1-completion.record.yaml)で境界付けた不変の履歴証明です。現在のManifestへ再適用せず、Definitive完成の根拠にも使いません。

Flutter 3.38.5の初期互換記録は`evidence/history/`へ隔離し、3.47.1のRelease Evidenceとして扱いません。Android Emulatorのpassは、iOS Simulator、Android / iOS実機、6PlatformすべてのBuild、Platform Channel / Plugin / Add-to-App / FFI / Platform View / GPU / Impellerの各Runtimeを証明しません。Source Contract、Widget Test、他Platformも代替証拠とは扱いません。未解決項目はDefinitive Gap Ledgerで追跡し、全必須RuntimeとScenarioが閉じるまで`complete`へ戻しません。

## 構成

- `atlas.yaml`、`mastery.yaml`、`sources.lock.yaml`、`coverage.yaml`、`skill.package.yaml`: Core v1共通Manifest
- `reference-systems/operations-workspace`: 実務品質を目指すFlutter製品参照実装
- `labs/`: 本番アプリへ不自然に混ぜない決定論的Lab
- `atlas/`: Capability、Claim、Proof Obligation、判断、除外
- `atlas/definitive/`: SDK Sourceから導出したBehavior/Capability Surface InventoryとGap Ledger
- `environments/`: local、container、simulator Profile
- `.agents/skills/flutter-reference-router`: 一つのRouter Skill
- `evals/`: Routing、Coverage Gap、Authority、権限境界の評価
- `evidence/`: Digestへ束縛された実行証拠

## ローカル検証

Core CLIは指定commitからローカルBuildします。正式SDKは`.tools/flutter-3.47.1/flutter`へ配置し、配布ZIPのSHA-256を`sources.lock.yaml`と照合します。

```bash
make atlas-bootstrap
make check
```

`make check`は正式Local Evidence再検証、Core Schema/Audit、Definitive Overlay、Dart/Flutter Test、Analyze、Skill Eval、Runbook、SBOM/第三者Manifest/Provenanceを検査します。Flutter Testはlocalhost一時socketを使うため、制限Sandboxでは許可が必要です。

公開済みmainは非後退Baselineです。`make non-regression-audit`は既存のTest/Lab/Target/Claim/Proof/Evidence/Source/Skill Eval/CIを固定commitと比較し、削除、格下げ、実Runtime Evidenceの置換、Test・Assertion・CI Matrixの縮小を拒否します。詳細は[公開main非後退Baseline](docs/NON_REGRESSION_BASELINE.md)を参照してください。

FE Depth Referenceの18軸は`make depth-reference-audit`で固定commitと照合し、`atlas/definitive/flutter-depth-parity.json`へFlutter固有の母集団とGapを出力します。FE側のTarget・Test等の絶対件数はFlutterの閾値にしません。

`make skill-eval`は既存64 Router Caseと14 Definitive Caseに加え、8 Outcome×14 Surfaceの112 cell、5 fail-closed境界、全27 Target stateを評価します。Matrix passはTarget completeを意味しません。独立Agent Forward Evalの実施状態は`evals/flutter-router.agent-forward-eval.json`へ別に記録します。

`scripts/reference-scenario-runtime.sh`はReference AppをChrome JavaScript・Wasmで実行し、10 Scenarioの専用Traceを生成します。`evidence/scenarios/index.json`は54 Surface×10 Scenarioの専用Proofと明示gapを列挙します。統合TraceをSurface固有Proofへ流用せず、Authority atomic bindingがないrowはCompletion対象外です。詳細は`docs/REFERENCE_SYSTEM.md`を参照してください。

`evidence/dependency-graph.json`はCore main/CI成功commit `072d7ca77981f51754e824d70c6d4ecd55ea67e5`の契約で、Flutter固有Source/Harness/Runtime/Profileから既存Evidenceへの依存と実runを固定します。入力変更後は影響outputを推移的にstale化し、first-attemptの実再実行、現在digest binding、Runtime identity、全output再生成までClosureを拒否します。詳細は[Evidence Dependency Graph](docs/EVIDENCE_DEPENDENCY_GRAPH.md)を参照してください。

`authority/extraction.snapshot.json`と`authority/surfaces-draft/`は既存reference edgeを、`authority/body-inventory.snapshot.json`と`authority/body-inventory-draft/`はunique document内の固定selector raw anchorを記録します。`authority/review-queue.snapshot.json`と`authority/review-queue-draft/`はstable anchor IDを保持した人手Review用batchです。第三者本文は保存しません。Networkを使う再取得は`make authority-extract`で明示的に行い、通常Gateは保存済みArtifact、decision ledger、専用非後退baselineを`make authority-verify`でoffline検証します。priority、cluster、batchは作業順序の提案だけであり、Queue件数をSemantic SurfaceやDepth達成へ算入しません。手順は`docs/AUTHORITY_REVIEW_WORKFLOW.md`を参照してください。

Container ProfileはDocker daemon起動後に実行します。

```bash
scripts/labs-container.sh
```

Simulator ProfileではAndroid Emulator Integration Testを実行済みです。iOS Simulator、実機、6Platform buildは別の実行Surfaceであり、Android Emulator、Container、Source Contractのいずれも相互の代替証拠とは扱いません。

## 完成の意味

完成は固定したAtlas ID、Release、Coverage Epoch、Authority Lock、Core Policy、Mastery Contract、Environment Profile、Evidence Setに対する証明です。`coverage.yaml`だけでなくDefinitive Surface Inventoryの全適用項目について、正常・境界・拒否・障害・回復、意味のある比較Variant、要求された実Runtime Profile、Artifact付きEvidence、Reference App統合、Skill Evalが閉じた場合のみ、新しいCompletion Certificateを生成して`status: complete`へ変更できます。`infeasible`は履歴説明には使えてもDefinitive完成の代替にはしません。

## 商標

Flutterおよび関連する名称・ロゴはGoogle LLCの商標です。本プロジェクトは独立したコミュニティプロジェクトであり、Googleによる承認、提携、公式性を示すものではありません。ロゴは同梱しません。
