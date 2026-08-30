# 統合Reference AppとScenario Proof

`reference-systems/operations-workspace`は、複数のFlutter behaviorをApplication境界で組み合わせて観測するためのbounded Reference Appです。個別Surfaceの実Platform ProofやAuthority由来Atomic behaviorの完成を代替しません。

## 10 Scenario統合Trace

次のCommandは固定Flutter 3.47.1でChrome JavaScript・Wasmをそれぞれ実行します。

```bash
scripts/reference-scenario-runtime.sh
```

normal、boundary、refusal、failure、recovery、migration、operations、security、performance、compatibilityを専用Testとして実行し、`evidence/scenarios/integrated/`へScenarioごとのTrace JSONを保存します。各TraceはBrowser version、OS、Architecture、Flutter・Dart version、Source digest、Harness digest、Compiler Variantごとの結果を保持します。

CIでは`make reference-scenario-runtime`を使い、結果を`.tools/`へ生成して追跡済みEvidenceを書き換えません。

Reporterは10 TraceとIndexを空のstaging directoryへ生成し、同一`run_id`、Scenario集合、Artifact digestを検証した後、full-run passの場合だけdirectory renameで公開します。失敗runと不完全なstagingは直前の成功Evidenceへ触れません。既存directoryをbackupへ退避した後のswapに失敗した場合は、部分的な新directoryを除去してbackupを復元します。これにより個別fileの部分上書き、新旧runの混在、失敗runによる成功Evidence消去を許可しません。

## Surface固有Proof

```bash
python3 tooling/scenario_proof/generate.py --check
python3 -m unittest tooling/scenario_proof/test_generate.py
```

`evidence/scenarios/index.json`は54 provisional Flutter Surface × 10 Scenarioの540 rowを列挙します。各rowは`evidence/scenarios/surfaces/`に専用Artifactを持ち、次を別々に記録します。

- 固定SDK Source pathとdigest。
- Surfaceへ明示Mappingされた既存Runtime Observation。これはClosure判定には使わない。
- Evidence record、Harness、Artifactと実Platform runtime identity。
- `evidence/scenarios/runtime/<surface>/<scenario>/results.json`に置く専用実行Reportの有無と検証結果。
- 対応する統合Reference App Traceと直接Surface mappingの有無。
- Surface固有Proofが成立しない理由。

統合Traceは全540 rowへ参照として接続しますが、`surface_specific_evidence`へ算入しません。既存の集約ReportやCapture metadataもClosureへ算入しません。

Gapを閉じる専用Reportは、SurfaceとScenarioを固定し、Baseline Variantを落とさない2件以上の全Variantを実Platform Runtimeでそれぞれ1回だけ駆動します。実行retryは0で、各Variantにfirst-attempt pass、専用Oracle、相互に再利用しないTrace・Artifact・画面、action/network/resource stream、実fileと一致するSource／Harness digestを要求します。Runtime identityはProfile、runner kind、OS、ArchitectureとPlatform固有識別子を保持します。network非使用のSurfaceは、空配列で済ませず非適用理由をTraceへ記録します。統合Trace配下や別Surface／ScenarioのArtifact pathは拒否します。

`scripts/scenario-method-channel-runtime.sh`は固定Android API 36 Emulator上で`platform.method-channel`のrefusal、failure、recovery、boundaryを、`json`と`standard` codecごとに独立実行します。8実行すべてがfirst-attemptで成功した場合だけ、専用Trace、構造化Result、実行中のAndroid画面をstagingから原子的に公開します。失敗runのlogは`.tools/scenario-method-channel/runs/`へrun単位で残り、追跡済み成功Evidenceを消去しません。

`scripts/scenario-security-tranche-runtime.sh`はClosure Planの`security-001`を固定Android API 36 Emulatorで実行します。Focus/Text Scale、Semantics Tree、App Lifecycle、Isolate Workを各2 Variantで独立実行し、実画面に加えてAndroid Accessibility tree、HOMEからのbackground/resume、実Isolateの要約結果を専用Oracleへ接続します。全8実行がfirst-attemptで成功した場合だけ、既存MethodChannel Evidenceを含むruntime root全体をstagingから原子的に置換します。

`scripts/scenario-build-web-security-runtime.sh`は`build.web.security`を固定Flutter SDKと実Chromeで実行します。debug JavaScript、release JavaScript、release Wasmを別build・別Browser profileで駆動し、artifact種別、source-map境界、release CSP、Flutter first frame、実画面を専用Oracleへ接続します。Chrome Accessibility treeも制約観測として保存しますが、headless CanvasKitでSemantics labelを確認できなかったためAccessibility証明へは算入しません。

現時点で専用Runtime契約を満たすrowは10/540、Runtime gapは530/540です。既存Android MethodChannel集約Reportはbounded Evidenceとして別に維持し、専用Reportへ流用していません。`build.android.security`はdebug/releaseのABI分割APKを実build・署名検証・install・launchしており、iOS/Linux/macOS buildの代替にはしません。`build.web.security`はWeb buildとChrome実行だけを閉じ、Windows buildおよびDevToolsのInspector/Performance/Memory/Network証明を代替しません。

## 完了境界

54 SurfaceはAuthority Human Review前のprovisional inventoryです。`authority/review-queue.snapshot.json`のHuman Reviewが0件である間、専用Runtimeが成立した10 rowを含む全rowは`authority_atomic_binding: false`、`completion_eligible: false`を維持します。10/10の統合Trace成功、既存Capture、row件数、Source bindingだけではRepositoryをcompleteにしません。
