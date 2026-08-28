---
name: flutter-reference-router
description: FlutterまたはDartの設計、実装、診断、復旧、移行、Reviewを、Flutter 技術実証アトラスのCoverage、一次資料、Lab、Evidenceへ案内する。React Native、Kotlin単体、一般Webだけの依頼には使わない。
---

# Flutter Reference Router

Flutter 技術実証アトラスを検索し、主張を一次資料と再実行可能な証拠へ戻しながら作業する。

## Route

1. 依頼を`design`、`implement`、`diagnose`、`recover`、`migrate`、`review`のいずれかへ分類する。
2. Repository Rootから`python3 .agents/skills/flutter-reference-router/scripts/route.py --mode <mode> --capability <query>`でCoverage、Capability、Claim、Labを検索する。複合依頼では`matched_capabilities`と全Commandを確認する。
3. `covered`でない対象、未収録Package・Version・Platform・Runtime、公開要求は完成済みとして扱わず、`gap_reasons`を明示する。Android EmulatorのpassをiOS Simulator、実機、hardware-in-the-loopへ拡張しない。
4. 実行が必要なら、返されたLabのSetup、Execute、Verify、CleanupとEnvironment Profileを使う。`source_contract`と`runtime_evidence`を同一視しない。
5. 推奨を出すときは`references/decision-boundaries.md`を読む。Baselineや実行環境を扱うときは`references/baseline.md`を読む。

## Boundaries

- Flutter 3.47.1を正式Baselineとし、3.38.5の互換確認をRelease Evidenceへ流用しない。
- Simulator EvidenceはRunner別に扱う。Android Emulator Integration Testはcoveredだが、iOS Simulator、実機、hardware-in-the-loop、公式6-Platform Matrixは未取得または`infeasible`のままとする。
- Framework内部、描画、状態、Navigation、Platform統合、Test、Quality、OperationsはRouterの返すCapabilityとCoverage Stateで区別する。単語が近い別Surfaceへ置き換えない。
- 一次資料Lockを外部記事より優先する。Lock外の情報は補助情報と明示する。
- Coverage外のAPI、Package、Platform対応を存在する証拠として捏造しない。一般Capabilityの一致を、特定Package、別SDK Version、未実行Platform、実機Runtimeの証明へ拡張しない。
- 実装、公開、Store送信、外部環境変更は依頼された権限の範囲だけで行う。
- `write_authorized`と`publish_authorized`は利用者の明示権限、`write_allowed`と`publish_allowed`はRouteが実行を支援できる範囲として区別する。権限だけで未収録Capabilityを実行可能にしない。
- Security依頼は防御、検証、教育に限定し、実在する第三者環境を標的にしない。
- Skill内へFlutter百科事典を複製せず、Canonical AtlasへRouteする。

## Completion

回答または変更には、選択したCapability、Coverage State、使用したAuthority、実行Command、Evidenceまたは未証明Gapを含める。文言一致ではなくObservable Outcomeで確認する。
