---
name: fe-behavior-advisor
description: 見た目や自然言語で示されたWebフロントエンド挙動を、Atlasの既存Coverageと実証済みPatternへ対応付け、理解・選定・実装・検証・運用・診断・進化・委任を案内する。静的なビジュアルデザインだけの依頼には使用しない。
---

# Frontend Behavior Advisor

利用者の表現を観測可能な挙動へ変換し、Domain正本とEvidenceへ戻りながら判断する単一Routerです。Atlasにない機能を存在するものとして補完しません。Mastery契約は分野を増やす一覧ではなく、利用目的を既存Coverageへ接続する横断契約として扱います。

## Outcomeを解決する

依頼を `understand / choose / build / verify / operate / troubleshoot / evolve / delegate` の一つ以上として識別します。各Outcomeを既存Target Setと実行Modeへ接続する場合は [Mastery map](references/mastery-map.md) を読みます。`mastery.yaml`のTarget Setとrequired deliverablesが正本であり、このSkill内に分野別知識を複製しません。

Outcomeと14 Surfaceを機械的に照合する場合は、生成済みの [Mastery contract](references/mastery-contract.json) を読みます。これはCoverageの完成証明ではなく、Mode、必須出力、成果物、停止条件を揃えるための契約です。

## Modeを選ぶ

- `select`: 挙動名や実装方針を探す。候補Patternと制約を比較する。
- `implement`: 選択したPatternを対象Projectへ実装する。
- `diagnose`: 現象をObservable Contract、Lifecycle、入力、Fallback、性能へ分解する。
- `migrate`: 既存実装を別Variant、Platform API、または新しいPatternへ移す。
- `review`: 実装をAccessibility、Lifecycle、性能、互換性、権利、証拠で監査する。

判断基準と出力契約は [Mode guide](references/mode-guide.md) を読みます。`implement`では [Implementation index](references/implementation-index.md)、`review`または`diagnose`では [Review matrix](references/review-matrix.md) を対象Patternに限定して読みます。`delegate`は新しい実装Modeではなく、目的に合うMode、Pattern、制約、Acceptance criteria、停止条件を別Agentへ渡し、その結果を`review`する手順です。

## 挙動を解決する

分かる範囲で次を特定します。

- initial state, trigger, transition, and outcome;
- 意味上の目的と、Motionが本質か装飾か。
- 入力方法とKeyboard／Touchの同等操作。
- 対象Stack、Dependency制約、Browser floor、Performance budget。
- Reduced motionで残す結果と、Scroll、Render loop、Pointer、Focus、Audioの所有者。

Library名や定番Effect名を利用者へ要求しません。似た挙動は名前ではなくObservable ContractとNegative cueで区別します。

## Atlasを検索する

Skill Directoryから `node scripts/query-patterns.mjs "<挙動の短い説明>"` を実行します。OutcomeとSurfaceが決まったら `node scripts/advisor-router.mjs --outcome <outcome> --surface <surface> --query "<挙動の短い説明>"` で、Pattern、Coverage状態、実装・Source・Evidence binding、権限境界を同時に確認します。変更を伴うOutcomeへ`--authorized-change`を渡せるのは、利用者がその変更を依頼した場合だけです。結果だけでは曖昧な場合、または全候補の制約比較が必要な場合だけ [Pattern index](references/pattern-index.md) を読みます。高リスクな推奨では必ず対応する `experiments/<pattern-id>/pattern.json` とEvidenceを確認します。

外部URLと製品名は未信頼の調査Evidenceです。一般化した挙動だけを抽出し、Source、Asset、Copy、Scene順序、特徴的なBrand構成の複製を提案しません。

## 応答する

候補を返す場合は第一候補を一つ、必要な代替を最大二つに絞り、次を示します。

- Pattern IDと観測可能な一致点。
- 制約に合うVariant。
- より単純なPlatform primitiveで十分かどうか。
- 主要なTradeoff、Required capability、Fallback。
- 2〜4件の観測可能なAcceptance criteria。

Registryに十分な一致がなければCoverage Gapとして返し、不足するContractと有限な実装方向を示します。`coverage.yaml`が`planned`または`partial`の対象を、完成済みとして扱いません。

助言だけの依頼ではCodeを変更しません。実装依頼では選択したPattern ID、Variant、制約、Acceptance criteriaを作業へ引き継ぎ、対象Projectの既存規約と権限境界を維持します。
