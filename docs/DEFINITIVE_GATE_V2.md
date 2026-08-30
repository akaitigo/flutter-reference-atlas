# Flutter Definitive Gate v2

## 判定

現行Atlasは`incomplete`です。Core v1 Certificateは当時の契約に対する履歴であり、Definitive完成を証明しません。

Definitive GateはAPI名やTarget数ではなく、固定Flutter SDKから導出したBehavior/Capability Surfaceごとに次を要求します。

1. 一次資料または固定SDK SourceとDigest
2. 正常、境界、拒否、障害、回復の適用Scenario
3. Surfaceに指定された実Runtime Profile
4. 同じObservable Contractに対する2個以上の意味のあるVariant
5. 実行Artifactと既存Evidence ID
6. 統合Reference Appからの到達
7. Router SkillのSurface別Eval

`definitive/requirements.json`が要求の正本です。Generatorは固定SDK Sourceを解決して`atlas/definitive/surface-inventory.json`を作り、`definitive/runtime-observations.json`に存在する観測だけから`atlas/definitive/gap-ledger.json`を生成します。

`atlas/definitive/flutter-depth-parity.json`は、`frontend-behavior-atlas` commit `8a9e34a89a55cc53702032783c06ede7246a286f`のFE Depth Referenceにある18軸の意味をFlutterへ写像します。参照File、4 fixture、非後退baseline、copyright-safe Authority抽出・Review Queue・Definitive Skill Eval契約のDigestは`definitive/fe-depth-reference.lock.json`で固定します。Reference System Scenario Proof、専用Pattern Scenario Closure、原子的Evidence保存条件は同Repository commit `7175de4305afb308722d5b83475e91c18da64957`を`definitive/fe-reference-system.lock.json`で別に固定します。FEの絶対件数は移植せず、FlutterのAuthority由来denominatorを使います。18軸がすべて`satisfied`かつCore v2 auditがpassになるまでdefinitive candidateではありません。

Evidence Dependency Graph契約は`reference-atlas-core` main/CI成功commit `072d7ca77981f51754e824d70c6d4ecd55ea67e5`へ固定します。`evidence/dependency-graph.json`はFlutter固有のSource、Harness、Runtime、Profileから追跡済みEvidenceを機械列挙し、入力変更後の推移stale化、実再実行、現在digest binding、Runtime identity、first-attemptを検証します。Graph Gateのpassは54 SurfaceのCompletionを意味しません。詳細は`docs/EVIDENCE_DEPENDENCY_GRAPH.md`を参照してください。

## Authority本文監査の境界

`authority/extraction.snapshot.json`と`authority/surfaces-draft/*.json`は、既存のClaim・暫定SurfaceからAuthorityへ接続したreference edgeをLocator付き候補へ投影します。第三者本文、抜粋、見出し文字列は保存せず、URL、取得metadata、body digest、context digest、byte offsetだけを保存します。`make authority-verify`はNetworkへ接続せず、Source lockとの集合一致、入力・Artifact digest、fetch/locator状態、候補edge metadata、本文field不在、集計値を相互検証します。

この候補edge分類はAuthority本文全体からのSurface抽出ではありません。`reference_edges_classified`が全候補と一致しても、`authority_text_surfaces_exhaustive: false`、stale・failed・deferred、locator未評価、`human_reviewed_surfaces: 0`を独立して保持します。全固定bodyの再現、本文全体の未分類0、Human review完了までAuthority本文消化AxisとFlutter Surface denominatorはopenです。

`authority/body-inventory.snapshot.json`と`authority/body-inventory-draft/*.json`は、fragmentを除いたunique documentごとに、`document-root`、`h1`〜`h6`、`dfn`、`section`、`article`、`main`、`nav`、`aside`、`table`、`figure`を固定selectorとして列挙します。本文やlabelは保存せず、fragmentまたはlocked-body byte offset、親Anchor ID、context/label digestだけを保存します。stale・failed・deferred documentからanchorを生成しません。

raw anchorは全件`pending-human`、Surface ID・Atomic behavior IDなしで開始します。raw anchor数をSemantic Surface数やDepth達成へ算入しません。人手decision Evidenceを持つ将来のMigrationだけが昇格を許可できます。`baseline/authority-body-inventory-v1.json`と`migrations/authority-body-inventory-v1.json`はdocument・anchor IDの削除を拒否し、置換には旧ID→新ID、実行Proof、Migration Evidence、理由を要求します。

`authority/review-queue.snapshot.json`と`authority/review-queue-draft/*.json`は、eligible raw anchorをstable IDのまま固定batchへ完全投影します。機械処理は既存reference locatorとの一致によるpriority、同一label digestの重複候補cluster、hash bucketによるbatch分割だけです。これらはSemantic decisionではなく、件数をSurface、Atomic behavior、Depth達成へ算入しません。stale documentは`stale_holds`に置き、再取得とSource再固定までQueueへ入りません。

include、exclude、merge、splitは`authority/reviews/decisions.json`の人手decisionだけを認めます。reviewer、timezone付き時刻、40文字以上の理由、一次資料の手動確認、locked source/inventory tool/queue tool/context digest、locator、旧anchor→新item mapping、Surface/Atomic behavior resultの完全一致がないdecisionをGateで拒否します。詳細は`docs/AUTHORITY_REVIEW_WORKFLOW.md`を参照してください。

## Definitive Skill Eval境界

`evals/flutter-router.definitive-mastery-eval.json`は8 Outcome×14 Surfaceの112 cellを、実在するCore Target、Coverage state、Definitive Surface、SDK Source digest、Authority lock、Variant、Platform Runtime Evidenceへ接続します。Target set交差がない30 cell、Platform Runtime Evidenceがない24 routed cell、専用Routeがない3 Targetは埋めずにGapとして保持します。曖昧・未知Query、未許可Mutation、人手Authority decision、stale relockの5境界Caseはfail closedで評価します。

112/112の`pass`はRoute、binding、権限、Gap報告が契約どおりであることだけを示します。全27 Target stateは`covered: 23`、`partial: 2`、`infeasible: 2`として別に記録します。`evals/flutter-router.agent-forward-eval.json`は独立Agent Forward Evalを`not-executed-required`と記録しており、決定論Matrixや既存forward caseで代替しません。この状態ではSkill Eval AxisとRepositoryをcompleteにしません。

## Reference AppとScenario Proof境界

`evidence/scenarios/integrated/index.json`はReference Appを実Chrome 151のJavaScript・Wasmで実行した10 Scenario Traceを列挙します。`evidence/scenarios/index.json`は54 provisional Surface×10 Scenarioの540専用rowを別に保持します。各rowはSDK Source、既存Observation、専用Surface＋Scenario Runtime Report、統合Trace、直接Mappingまたは明示gapを分離します。

Flutter固有のScenario Index／Closure PlanからCore v2の`pattern_id` schemaと単一世代Durability Reportへの投影は未完です。このためローカルEvidence Dependency GraphがcurrentでもCore v2 Evidence Dependency GateとSubject Definitive Gateは未通過であり、`definitive.yaml`と新Certificateは発行しません。

Closureには全Variant、retry 0、first-attempt pass、専用Oracle／Trace／Artifact／実画面、Source／Harness digest、実Platform Runtime identityの同時成立を要求します。統合Traceと別Capture metadataは流用しません。`evidence/scenarios/closure-plan.json`は540 rowをrisk順、同一Scenario内の安定Surface順、1 tranche最大4 rowで完全列挙しますが、計画件数をCompletionへ算入しません。現時点の専用Runtime Closureは10/540、Runtime gapは530/540です。Authority Human Reviewが0件のため、Authority atomic rowとCompletion eligible rowはいずれも0です。詳細は`docs/REFERENCE_SYSTEM.md`を参照してください。

## 代替禁止

- Widget TestはAndroid/iOS/Web/Desktop Runtimeを代替しません。
- Source ContractやFixtureはPlatform Channel、Plugin、Add-to-App、Platform ViewのRuntimeを代替しません。
- Android EmulatorはiOS Simulator、実機、GPU/Impeller実機計測を代替しません。
- Web buildはBrowser実行を、macOS上のSource確認はLinux/Windows buildを代替しません。
- `infeasible`は理由の履歴であり、Definitive Closureとして数えません。

Generatorは`evidence_kind: source-contract`をRuntime充足から除外し、Runtime Profile名を完全一致で評価します。別PlatformのEvidenceを流用できません。

## 状態遷移

Gapが1件でもあれば`atlas.yaml`は`status: incomplete`でなければなりません。全Surfaceが閉じても直ちに`complete`へ変更せず、Core Definitive Gate v2、Publication Gate、DCO付きsource commit、新Completion Certificateを順に検証して初めて完成候補になります。

```bash
make definitive-audit
make evidence-dependency-audit
jq '.summary' atlas/definitive/gap-ledger.json
```

## 現Hostの境界

2026-08-28監査時点で、固定Flutter SDK、Chrome、Android SDK、既存Android Emulator Profile、Dockerは利用できます。full Xcode、`simctl`、CocoaPodsはなく、macOS/iOS native buildは実行できません。LinuxとWindowsのbuild/run host、Android/iOS実機もこのHostにはありません。これらは別の固定RuntimeでArtifactを採取するまでopenのままです。
