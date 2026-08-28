# 既存Flutter調査の移管

以前の設計調査で得た「Flutter全部入りアプリではなく、機械的に追跡可能な実行リファレンスにする」という結論をCore v1へ移管しました。

## 継承した内容

- Flutter stableを固定した一度限りのCoverage Epoch
- 上流SDKから生成する公開Surface Inventory
- Operations WorkspaceというProduction Reference Product
- FFI、Pigeon、Shader、Add-to-App、Web/Wasm、Desktop、状態管理比較を独立Scenarioに置く方針
- E0〜E4の証跡思想をClaim、Proof Obligation、Evidenceへ変換する方針
- 問題コードと修正版を測定可能に比較するAnti-pattern Lab
- 実行・評価可能なAgent Skill
- 性能、Accessibility、Security、配布を完成条件に含める方針

## Core v1での変換

| 旧概念 | Core v1の配置 |
|---|---|
| Baseline Inventory | `sources.lock.yaml`、`baseline/` |
| Capability Catalog | `coverage.yaml`、`atlas/capabilities/` |
| Production Product | `reference-systems/operations-workspace/` |
| Executable Scenarios | `labs/` |
| Evidence Level | ClaimごとのProof ObligationとEvidence |
| Practical Skills | 一つの`flutter-reference-router`とMode |
| Release Gate | 7 ClosureとOverlay Validator |

## 変更した内容

- 2026年8月28日時点の最新stableは3.47.2ですが、既存調査の正式Baselineである3.47.1を不変Epochとして保持します。
- Local SDKは3.38.5のため、互換確認結果を3.47.1 Evidenceとして認定しません。
- 「全公開Package」は有限性を損なうため除外し、公式SDK Surfaceと選定済みapp-facing SurfaceのInventoryへ限定します。
- 多数のMicro Skillは作らず、設計、実装、診断、復旧、移行、Reviewを一つのRouter Modeにします。
