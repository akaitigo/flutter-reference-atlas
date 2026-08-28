# Flutter 技術実証アトラス

`flutter-reference-atlas`は、Flutterを使う際の判断、実装、検証、運用を、一次資料と再実行可能な証拠へ接続する独立コミュニティプロジェクトです。単なるWidget一覧や巨大なサンプルアプリではありません。

## 現在の状態

**INCOMPLETE** — 固定Coverage Epochの全Gateを通過していません。

- 正式Baseline: Flutter 3.47.1 / Dart 3.13.1 / DevTools 2.60.0
- Coverage Epoch: 2026-08-28
- ローカル互換性確認環境: Flutter 3.38.5
- 未完了の主要Gate: 3.47.1実行証拠、SDK公開Surface Inventory、iOS/Android Simulator、6Platform Build、SBOM/第三者来歴のClosure、Publication Certificate

3.38.5で得た結果を3.47.1のRelease Evidenceとして扱いません。全Gate通過前に`complete`、production-ready、完全網羅とは表現しません。

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

Core CLIは指定commitからローカルBuildします。GitHub公開前のため、固定Release Artifactへ移行するGateは未達です。

```bash
make atlas-bootstrap
make validate
make atlas-audit
make test
make skill-eval
make check
```

Flutter CLIがHomebrew配下のCacheへ書き込む環境では、Sandbox外の許可またはWorkspace内の専用SDKが必要です。

## 完成の意味

完成は固定したAtlas ID、Release、Coverage Epoch、Authority Lock、Core Policy、Mastery Contract、Environment Profile、Evidence Setに対する証明です。`coverage.yaml`の必須Targetが閉じ、8 Outcomeと14 Surface、Claim/Evidence Graph、Execution、Operations、Skill、Publicationの全Gateが通過した場合のみ、生成されたCompletion Certificateを伴って`status: complete`へ変更できます。

## 商標

Flutterおよび関連する名称・ロゴはGoogle LLCの商標です。本プロジェクトは独立したコミュニティプロジェクトであり、Googleによる承認、提携、公式性を示すものではありません。ロゴは同梱しません。
