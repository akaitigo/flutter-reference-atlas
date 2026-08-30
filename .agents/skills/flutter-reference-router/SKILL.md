---
name: flutter-reference-router
description: FlutterまたはDartの設計、実装、診断、復旧、移行、Reviewを、Flutter 技術実証アトラスのCoverage、一次資料、Lab、Evidenceへ案内する。React Native、Kotlin単体、一般Webだけの依頼には使わない。
---

# Flutter Reference Router

Flutter 技術実証アトラスを検索し、主張を一次資料と再実行可能な証拠へ戻しながら作業する。

## Route

1. 依頼を`design`、`implement`、`diagnose`、`recover`、`migrate`、`review`のいずれかへ分類する。
2. Repository Rootから`python3 .agents/skills/flutter-reference-router/scripts/route.py --mode <mode> --capability <query>`でCore v1 Coverage、Capability、Claim、Labを検索する。複合依頼では`matched_capabilities`と全Commandを確認する。
3. 実Runtime、Platform、GPU、Plugin、Build、DevToolsなどDefinitive完成に関わる依頼では、続けて`python3 .agents/skills/flutter-reference-router/scripts/route_definitive.py --query <query>`を実行し、Surface単位の`state`、`required_runtime_profiles`、`gaps`、`observed_evidence_ids`を確認する。
4. `closed`でないDefinitive Surface、`covered`でないCore対象、未収録Package・Version・Platform・Runtime、公開要求は完成済みとして扱わず、Gapを明示する。Android EmulatorのpassをiOS Simulator、実機、hardware-in-the-loopへ拡張しない。
5. Evidenceを根拠にRouteする前に`evidence/dependency-graph.json`の該当outputとrunを確認する。Graphまたは到達outputが`stale`、現在input digestへのbindingがない、retry、Runtime identity欠落、required output漏れの場合はCompletion Routeを停止し、実再実行を要求する。
5. 実行が必要なら、返されたLabのSetup、Execute、Verify、CleanupとEnvironment Profileを使う。`source_contract`と`runtime_evidence`を同一視しない。
6. 推奨を出すときは`references/decision-boundaries.md`を読む。Baselineや実行環境を扱うときは`references/baseline.md`を読む。
7. OutcomeまたはMastery Surfaceをまたぐ依頼では`references/mastery-contract.json`を読み、`evals/flutter-router.definitive-mastery-eval.json`の同じOutcome×Surface cell、Target state、Variant、Authority、Platform Runtime Evidence、routing gapを確認する。
8. ScenarioまたはReference Appを根拠にするときは`evidence/scenarios/index.json`からSurface×Scenarioの専用rowを選ぶ。`evidence/scenarios/integrated/`の10 Traceと既存Capture metadataはCross-behaviorまたはbounded観測であり、全Variantをretry 0で駆動した専用Oracle／Trace／Artifact、実Platform identity、Authority atomic bindingの不足を代替しない。

## Boundaries

- Flutter 3.47.1を正式Baselineとし、3.38.5の互換確認をRelease Evidenceへ流用しない。
- Core v1の`covered`や履歴CertificateをDefinitive完成へ昇格しない。現行の正本は`atlas/definitive/surface-inventory.json`と`atlas/definitive/gap-ledger.json`であり、全Surfaceがopenの間はAtlas全体を`incomplete`として扱う。
- Simulator EvidenceはRunner別に扱う。Android Emulator MethodChannel Runtimeはbounded集約Evidenceとして保持するが、Scenario専用Closureには算入しない。iOS Simulator、実機、hardware-in-the-loop、公式6-Platform Matrixは未取得のままとする。
- Framework内部、描画、状態、Navigation、Platform統合、Test、Quality、OperationsはRouterの返すCapabilityとCoverage Stateで区別する。単語が近い別Surfaceへ置き換えない。
- 一次資料Lockを外部記事より優先する。Lock外の情報は補助情報と明示する。
- Coverage外のAPI、Package、Platform対応を存在する証拠として捏造しない。一般Capabilityの一致を、特定Package、別SDK Version、未実行Platform、実機Runtimeの証明へ拡張しない。
- 実装、公開、Store送信、外部環境変更は依頼された権限の範囲だけで行う。
- `write_authorized`と`publish_authorized`は利用者の明示権限、`write_allowed`と`publish_allowed`はRouteが実行を支援できる範囲として区別する。権限だけで未収録Capabilityを実行可能にしない。
- Authority semantic decisionは人が一次資料を確認しdecision ledgerへ記録する。通常の変更権限やAgent判断で代替しない。stale Source relockも別手順として停止する。
- 曖昧または未知のQueryは単一Capabilityへ推測せず、追加のSurface・Platform・Runtime条件を求める。
- 8 Outcome×14 SurfaceのMatrix passはRouter契約の評価であり、Target完成や独立Agent Forward Evalの代替ではない。`evals/flutter-router.agent-forward-eval.json`が未実施ならCompletionを主張しない。
- Reference Appの10/10 passや540専用rowの存在だけでSurface完成を主張しない。`authority_atomic_binding`がfalseのrowはCompletion対象外である。
- Evidence Dependency GraphのpassはEvidence保存と再実行bindingのGateであり、Surface、Scenario、Authority、Device Completionの代替ではない。Graphのdigestだけを再固定してstaleを解消しない。
- Security依頼は防御、検証、教育に限定し、実在する第三者環境を標的にしない。
- Skill内へFlutter百科事典を複製せず、Canonical AtlasへRouteする。

## Completion

回答または変更には、選択したCapability、Target state、Variant、使用したAuthority、Platform Runtime Evidence、実行Command、routing gapまたは未証明Gapを含める。文言一致やMatrix passではなくObservable Outcomeで確認する。
