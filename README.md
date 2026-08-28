# Flutter 技術実証アトラス

`flutter-reference-atlas`は、Flutterを使う際の判断、実装、検証、運用を、一次資料と再実行可能な証拠へ接続する独立コミュニティプロジェクトです。単なるWidget一覧や巨大なサンプルアプリではありません。

## 現在の状態

**INCOMPLETE** — 固定Coverage Epochの全Gateを通過していません。

- 正式Baseline: Flutter 3.47.1 / Dart 3.13.1 / DevTools 2.60.0
- Coverage Epoch: 2026-08-28
- Core Contract: `reference-atlas-core` v1.0.0 commit `cf9e6e2d981305c83f970c1f21a1ddc9c1109263`
- Formal Local: 16/16 command pass（Framework、Product、FFI、Security、Recovery、Web release buildを含む）
- Container: 固定Dart 3.13.1 OCI Digest、network無効、Cleanup確認済み
- Router Skill Eval: 62/62 pass、独立Forward Eval pass
- 未完了の主要Gate: iOS/Android Simulator、Android/iOS/Windows/Linux Native Runner、Completion Certificate

Flutter 3.38.5の初期互換記録は`evidence/history/`へ隔離し、3.47.1のRelease Evidenceとして扱いません。全Gate通過前に`complete`、production-ready、6Platform実行済みとは表現しません。

## 構成

- `atlas.yaml`、`mastery.yaml`、`sources.lock.yaml`、`coverage.yaml`、`skill.package.yaml`: Core v1共通Manifest
- `reference-systems/operations-workspace`: 実務品質を目指すFlutter製品参照実装
- `labs/`: 本番アプリへ不自然に混ぜない決定論的Lab
- `atlas/`: Capability、Claim、Proof Obligation、判断、除外
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

`make check`は正式Local Evidence再検証、Core Schema/Audit、Claim/Evidence Overlay、Dart/Flutter Test、Analyze、62件のSkill Eval、Runbook、SBOM/第三者Manifest/Provenanceを検査します。Flutter Testはlocalhost一時socketを使うため、制限Sandboxでは許可が必要です。

Container ProfileはDocker daemon起動後に実行します。

```bash
scripts/labs-container.sh
```

Simulator ProfileはToolchain不足を`infeasible`として記録しており、ContainerやSource Contractを同等の代替証拠とは扱いません。

## 完成の意味

完成は固定したAtlas ID、Release、Coverage Epoch、Authority Lock、Core Policy、Mastery Contract、Environment Profile、Evidence Setに対する証明です。`coverage.yaml`の必須Targetが閉じ、8 Outcomeと14 Surface、Claim/Evidence Graph、Execution、Operations、Skill、Publicationの全Gateが通過した場合のみ、生成されたCompletion Certificateを伴って`status: complete`へ変更できます。

## 商標

Flutterおよび関連する名称・ロゴはGoogle LLCの商標です。本プロジェクトは独立したコミュニティプロジェクトであり、Googleによる承認、提携、公式性を示すものではありません。ロゴは同梱しません。
