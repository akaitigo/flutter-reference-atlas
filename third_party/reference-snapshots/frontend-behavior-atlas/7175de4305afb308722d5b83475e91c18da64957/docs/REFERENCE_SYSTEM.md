# 統合Reference System

`apps/reference-system`は、個別Labの一覧では観測しにくいCross-behavior境界を一つのApplicationで実行するためのbounded Reference Systemです。対象は現行Frontend Domainだけで、Authority由来Atomic behaviorの完成や外部Profileの証明には使いません。

## 実行契約

```bash
pnpm reference:test
pnpm reference:verify
pnpm pattern-scenario:test
pnpm pattern-scenario:verify
pnpm scenario:plan:verify
pnpm scenario:generate
pnpm scenario:verify
pnpm scenario:test
```

`reference:test`はproduction buildをCSP／Permissions Policy付きpreview serverで配信し、Chromiumを1 worker、retry 0、Trace常時有効で起動します。console errorとpage errorも失敗条件です。normal、boundary、refusal、failure、recovery、migration、operations、security、performance、compatibilityを個別Testとして実行し、次を保存します。

- `artifacts/reference-system/results.json`: Source／Harness digest、Node／OS／Architecture、Playwright／Browser version、Attempt、結果。
- `artifacts/reference-system/traces/*.trace.zip`: ScenarioごとのAction／Network／Resource stream。
- `artifacts/reference-system/screenshots/*.png`: 最終Observable state。

Manifestは`integrations/reference-system/manifest.json`です。各Scenarioは2件以上の既存Pattern、Runtime boundary、反証可能なAssertionへ接続します。

## Runtime boundary

- module Worker: 正常処理、強制失敗、新generationでの復旧、sample上限。
- bounded queue: offline中の上限、超過時のquality degradation、replay once。
- localStorage schema: v1からv2への明示Mappingと選択状態の連続性。
- CSP／Permissions Policy: Capabilityを要求せずrefusalを表示し、実Response headerを検証。
- DOM text sink: 未信頼入力をmarkupとして解釈しない。
- Resource ownership: Worker、timer、event listenerの所有数を観測し、operationsで0へ戻す。

## Pattern × Scenario Artifact

`scenario:generate`は現行85 Pattern × 10 Scenarioの850 JSONを`evidence/scenarios/patterns/`へ生成し、`evidence/scenarios/index.json`へdigest付きで列挙します。各rowは次の証拠を混同せずに保持します。

1. Variant Source pathとdigest。
2. Pattern固有のCapture、Benchmark、Compatibility record。
3. Pattern／Variantを対象Scenarioへ実操作した専用Runtime Oracle、Trace、Screenshot。
4. 同じScenarioの統合Reference System TraceとScreenshot。
5. Browser identity、Pattern mapping、Authority Human reviewの未達。

CaptureはSource／Harness／Image digestと固定Browser identityを持ち、明示Stateへ接続できるrowのbounded runtime proofになります。PerformanceとCompatibilityは環境identityを持つ既存実Browser recordを接続します。State分類だけでは閉じないgapは、`pattern-scenario:test`が全Variantを対象Scenarioへ実操作し、first-attempt pass、専用Oracle、Action／Network／Resource Trace、Screenshot、Source／Harness digestを保存した場合だけ閉じます。現在の専用証跡は2 queue Patternのboundary 2行とsecurity 6行、計8行／16 Variantです。securityはcombobox／command paletteのuntrusted text sink、drag reorderの外部transferとrecord集合の拘束、inertial dragの有限なtrack内軌道、accordionの排他的開示、mask revealの視覚・semantic分離を、それぞれ別Oracleで照合します。統合TraceはCross-behaviorの境界証明で、Pattern固有proofへ昇格しません。

`evidence/scenarios/closure-plan.json`は残413行を指定risk順に並べ、1トランシェ最大4 Pattern行へ分割します。完了した`security-001`のstable IDと4行／8 Variant／4 Oracle kindを履歴として保持し、次を`security-002`とします。共通Harnessは許容しますが、各行はPattern＋Scenario＋全Variantを実際に駆動した別Trace／Screenshotと専用Oracleを必要とし、metadata補完、Capture再利用、統合Trace再利用、mock/static置換を禁止します。

Pattern Scenario ReporterはEvidence一式をstaging directoryへ構築し、全run成功時だけdirectory renameで公開します。失敗runは直前の成功Evidenceを保持し、置換失敗時はbackupから復元します。

## 完了境界

850は現行Domainの非後退分母であり、Authority-derived denominatorではありません。全rowは`authority_atomic_behavior: false`と`completion_eligible: false`を維持します。Authority review、残るPattern固有Scenario gap、実Device／支援技術／Cloud／Hardware profileが未完了であるため、Reference Systemが10/10を通ってもRepository全体は`incomplete`です。
