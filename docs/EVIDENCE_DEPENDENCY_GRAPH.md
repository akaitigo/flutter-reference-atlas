# Flutter Evidence Dependency Graph

`evidence/dependency-graph.json`は、Flutter固有のSource、Harness、Runtime、Profileから追跡済みEvidenceへの推移依存を固定します。共通契約は`reference-atlas-core` main/CI成功commit `072d7ca77981f51754e824d70c6d4ecd55ea67e5`です。

## Flutter固有denominator

Generatorは件数を別Repositoryから転用せず、Repository実体から次を列挙します。

- 8個のEvidence manifestと、そのArtifact・sanitized log
- formal local内のunit、widget、性能、Security、FFI、web build結果
- container conflict、Android Emulator integration、Android MethodChannel/Plugin Runtime
- Chrome JavaScript/Wasm RuntimeとReference App 10 Scenario Trace
- Android MethodChannelの4専用Scenario×2 codecに対するTrace、Result、実画面
- Android security-001の4 Surface×2 Variantに対するTrace、Result、実画面、Accessibility tree
- Web build securityのdebug JavaScript、release JavaScript、release Wasmに対するbuild Artifact、Chrome Trace、実画面
- 54 Surface×10 Scenarioの540 ProofとClosure Plan
- Router Skill Eval、Authority抽出・Body Inventory・Review Queue、Depth Parity、Gap Ledger、Provenance

Core v1 Certificate、旧互換記録、失敗したCore v2 audit記録は再生成対象へ入れず、`source.atlas-contract`の不変履歴memberとしてdigest固定します。現在Evidenceへ昇格させたり、再実行で上書きしたりしません。

Golden Evidenceは現時点で存在しません。`baseline/evidence-dependency-v1.json`へ`not-present-gap`として固定し、Widget screenshotや別PlatformのArtifactで補完しません。Android Emulator Evidenceも物理Device Evidenceへ昇格しません。

## 変更とstale遷移

inputは`source`、`harness`、`runtime`、`profile`に分け、member集合のCanonical digestを保持します。入力変更を観測したら次を実行します。

```bash
python3 tooling/evidence_dependency/graph.py \
  --refresh-stale \
  --observed-at 2026-08-29T12:00:00+09:00
```

到達可能なoutputが推移的に`stale`になります。Graph、input binding、output digestだけの更新ではClosureできません。各runの`command`をretryなしで実行し、first attemptが成功した後だけ、開始・完了時刻を記録します。

```bash
python3 tooling/evidence_dependency/graph.py \
  --record-rerun run.reference-scenarios.2026-08-28 \
  --started-at 2026-08-29T12:01:00+09:00 \
  --completed-at 2026-08-29T12:03:00+09:00
```

上流outputがstaleのままの派生run、変更観測前に開始したrun、retry、現在input digestに一致しないbinding、Runtime identityのない実行を拒否します。影響runをすべて再実行するまでGraph全体は`stale`です。

## 構造と非後退

`evidence/scenarios/closure-plan.json`は全540 rowをrisk順、同一Scenario内のSurface安定順、1 tranche最大4 rowで列挙します。専用Runtime完了状態を別に記録しますが、Authority bindingなしではCompletion creditにしません。Scenario Proofのrow、Surface、Scenario、Source path、Variant、およびClosure Planの順序・tranche membershipを構造digestへ固定し、openからruntime-completedへの状態遷移ではdenominator digestを変えません。

`baseline/evidence-dependency-v1.json`はinput、run、必要output、Evidence family、profile、first-attempt、Scenario数、540 row、4 row上限、2構造digestを加法baselineとして保持します。削除、対象退避、Goldenの偽装、profile縮小、retry許容、tranche肥大化、Proof/Plan構造縮小には旧ID→新ID mapping、同等以上の実行Proof、Migration Evidence、理由が必要です。

負例fixtureは次を機械拒否します。

- input変更後のdigest-only closure
- 必要outputの漏れとrequired集合からの退避
- Proof rowとClosure row/trancheの構造縮小
- first-attemptからretryへの変更
- 実Platform runのRuntime identity削除
- Scenario/tranche閾値の弱化

## GateとCertificate

```bash
make evidence-dependency-local
make evidence-dependency-audit
make non-regression-audit
```

`evidence-dependency-local`は現在passします。固定Core CLIを使う`evidence-dependency-audit`は、Flutter固有のScenario Index／Closure PlanをCore v2の`pattern_id`投影と単一世代Durability Reportへまだ移行していないため未通過です。ローカルGraphのpassをCore Gate通過として扱いません。現状はScenario専用Runtime closureが10/540、Authority atomic bindingが0件、Completion eligibleが0/540で、Atlasは`incomplete`です。

将来の`definitive.yaml`は`evidence_dependency_graph: evidence/dependency-graph.json`を参照し、Subject Definitive Certificateは同Graphのdigestを`evidence_dependency_digest`へ固定します。全Definitive Gate通過前は`evidence/definitive-certificate.json`を発行しません。Core v1 Certificateは履歴のまま変更しません。
