# FE Depth ReferenceとDefinitive Gate v2参照契約

## 目的

`FE_DEPTH_REFERENCE.json`は、Frontendの件数を他分野へコピーするためのQuotaではありません。別分野が「この分野ならここを見ればよい」と主張するとき、何をAuthorityから導き、どの粒度で実行し、どのEvidenceで反証可能にし、将来の後退をどう防ぐかを比較するための深度契約です。

Frontend固有の85 Target、170 Variant、299 E2E Testは、このRepositoryの非後退floorです。他分野は自身の一次資料または権威ある固定ArtifactからSurfaceを抽出し、Atomic behavior／capabilityの母集団を決めなければなりません。文書数、Demo数、Test数をFrontendへ合わせても、Authority由来の未分類が残る、実Runtimeで動かない、Scenario専用Evidenceがない、または非後退Gateがない場合は同等深度ではありません。

## 機械判定

Matrixの各Axisは次を持ちます。

- `portableCriterion`: 分野に依存しない合格意味論。
- `denominator`: 件数ではなく、何から検証母集団を導くか。
- `checks`: 現在のFrontendで満たした事実とEvidence URI、または未達。
- `status`: 全Checkが通った` satisfied`、一部だけ通った`partial`、実証がない`missing`。
- `gaps`: 次に必要な実装・Review・Evidence。

他分野のDepth parityは、自身のAuthority由来denominatorに対して全必須Axisを満たす場合だけ成立します。FrontendのRatioを閾値として流用しません。一方、Frontend自身は`baselines/definitive-gate-v2.json`に現在のID集合、Assertion fingerprint、Budget、Runtime Profile、Browser version、Evidence、CIを固定し、今後の縮小を拒否します。

## 現在の正直な境界

現行Frontendは、全PatternのAuthority接続、実Response body digest、全Variantの実行Lab、Local／固定Dockerの同一299 Test、3 Browser Engine、Capture、Benchmark、Accessibility Contract、Router Eval、SBOMを持ちます。ただし、これはまだ`subject-definitive`ではありません。

- 既存235 reference edgeは`authority/surfaces-draft/`へ損失なく候補投影したが、Authority本文全体から導いたSurface Inventoryではない。
- 固定84 bodyの再取得は81件がexact digest一致、3件がstaleで、該当4 edgeのlocator評価は保留。Digest一致本文のfragmentは29件を検出し、未発見は0件。
- fragmentを除いた73 documentのうち70件について、固定selector内のsemantic anchorを15,963件列挙した。全件が未分類・未Reviewで、3 stale documentはanchor抽出を行っていない。
- 候補分類はDomain contractからの自動推定で、Human reviewは0件、Core v2適格Surfaceは0件。
- 現行Patternにはcompound/systemic unitがあり、Authority Surface由来Atomic behaviorと同一ではない。
- normal、boundary、refusal、failure、recovery、migration、operations、security、performance、compatibilityを、全Atomic behaviorの専用rowと一意Evidenceへ分割していない。
- Playwright Trace、Network/Console Timeline等をRequired Scenario ArtifactとしてManifest化していない。
- Cloud live、Hardware-in-the-loop、実Device、手動支援技術、複数OS Profileを証明していない。
- 複数BehaviorをApplication境界で統合した専用Reference System ManifestとCross-behavior Proofがない。
- Skill Evalは8 Outcome × 14 Surfaceの112セル、曖昧・未知Query、未許可変更、人手Authority判断、stale relockの5境界Caseを実行する。112セルの契約評価はpassするが、`operate`／`troubleshoot`と`foundations-mechanics`の2セルはMastery target set交差がなくCoverage Gapであり、実Project変更結果の独立Agent Forward Evalも未実施である。
- Human visual/similarity、Trademark、第三者License義務Reviewが未完了。

したがって`atlas.yaml`とMatrixは`incomplete`を維持し、Completion Certificateを発行しません。

## Authority抽出境界

`authority/extraction.snapshot.json`と`authority/surfaces-draft/*.json`は、既存reference edgeを再検査するためのDomain Overlayです。`pnpm authority:extract`は公開URLを再取得し、固定body SHA-256と一致した場合だけdocument rootまたはfragment locatorを評価します。Repositoryへ第三者本文、抜粋、見出し文字列を保存せず、URL、exact body digest、context digest、位置、見出しdigestだけを保存します。`pnpm authority:verify`はNetworkへ接続せず、84 Artifactの集合、入力digest、Artifact hash、fetch/locator状態、候補edge metadata、index集計を相互照合します。

`reference_edges_classified: 235`と`unclassified_reference_edges: 0`は、既にDomain正本が参照していたedgeだけの性質です。`authority_text_surfaces_exhaustive: false`を同時に固定し、Authority本文全体の未分類0とは解釈しません。stale bodyを自動でSource lockへ取り込まず、候補をHuman-reviewedまたはCore v2 eligibleへ自動昇格させません。

`authority/body-inventory.snapshot.json`と`authority/body-inventory-draft/*.json`は、`document-root`、`h1`〜`h6`、`dfn`、`section`、`article`、`main`、`nav`、`aside`、`table`、`figure`という固定selector契約の列挙結果です。本文・見出し・定義文字列は保存せず、fragmentまたは固定本文offset、階層、context/label digestのみを保存します。`selector_exhaustive_for_locked_body: true`はそのselector内での列挙を意味し、Authorityが持つ意味的Surfaceの網羅を意味しません。全anchorは`classification_status: pending-human`、`surface_ids: []`で、Core v2のreview済みAuthority Artifactへは接続しません。

`authority/review-queue.snapshot.json`と`authority/review-queue-draft/*.json`は、そのstable anchor IDを失わずに人が確認できる固定batchへ分割します。機械処理は既存Domain locatorとの一致による優先度、同一label digestの重複候補cluster、hash bucket分割だけです。include／exclude／merge／splitは自動決定せず、`authority/reviews/decisions.json`へsource/tool digest、locator、理由、reviewer、時刻、旧→新mappingを備えた人手decisionがある場合だけ集計します。staleな3 documentは更新・再固定されるまでholdです。

Priority 0は`authority/review-packets/priority-0/*.json`へ一anchor一packetで出力し、一次資料deep-link、230件の既存Domain候補投影、機械提案clusterを比較できます。`authority/portal/review-export.v1.json`はこのpacketを共通UIへ渡すread-only契約で、decision書き込みとHuman review昇格を明示的に禁止します。`authority/stale-relock-candidates.json`はstale 3件のsame URL差分とcommit固定候補を本文なしで示しますが、locked digest更新数と人の選択数はいずれも0です。

抽出ArtifactはSource lockだけでなく抽出tool source digestへ束縛します。parser、selector、取得処理の変更後は再取得しなければoffline verifierを通りません。`baselines/authority-body-inventory-v1.json`は初回15,963 anchor IDと73 documentを固定し、今後の削除を拒否します。置換が必要な場合は`migrations/authority-body-inventory-v1.json`へ非共有の旧ID→新ID、実行Proof、Migration Evidence、理由を記録し、元のSource/Lab/Evidenceを削除しません。

## Definitive Skill Eval境界

`.agents/skills/fe-behavior-advisor/scripts/advisor-router.mjs`は、OutcomeとSurfaceを実在Pattern、Coverage Target、Variant Source、Authority body digest、Capture、Benchmark、3 Engine Compatibility、Local／Container E2Eへ接続します。`partial` Targetは全セルでCoverage Gapとして返し、実装・移行・委任は明示的な変更許可なしに進めません。人手Authority decisionとstale source relockは、利用者が通常の変更を許可していても別の停止条件です。

`evals/fe-behavior-advisor.definitive-skill-eval.json`は112セルすべての実行結果と5境界Caseを保持します。ここでの`pass`はRouter契約、Digest接続、権限境界が期待通り動いた意味であり、Target完成や独立Agentによる実装品質を証明しません。2 Mastery routing gapと全Target `partial`を残し、Skill Eval Axisは`partial`を維持します。

## 参照Fixture

`fixtures/definitive-gate-v2/`はCore Schemaの代替でも、v2 Completion Evidenceでもありません。Coreの確定Commitへ移行する前に、他分野が再利用すべき粒度と「代替してはいけないProfile／Evidence」を具体化するDomain Overlayです。

- `authority-surface-inventory.fixture.json`: Authority LocatorからAtomic behaviorへ降ろす構造と、未Reviewを明示します。
- `variant-comparison.fixture.json`: 同じObservable Contractを共有する方式だけを比較し、Entry、Capability、Fallback、Trade-offを保持します。
- `profile-incompatibility.fixture.json`: Container、実Device、支援技術、Cloud live、static fallbackが相互代替ではないことを固定します。
- `evidence-granularity.fixture.json`: 現行Bundle Evidenceを履歴として維持しつつ、Definitive Gateで必要なBehavior × Scenario × Profile × Proof × Artifact単位を示します。

Core v2 Schemaは`reference-atlas-core`の確定Commitを正本とします。このRepositoryはCore draftを複製・改変せず、確定前のFixtureをCompletion Manifestとして扱いません。
