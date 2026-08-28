# Framework内部と描画Pipelineの実証設計

## Widget、Element、RenderObject

Widgetはimmutableな構成記述です。ElementはWidgetをTree上の位置へ結び付け、StatefulWidgetのStateを保持します。RenderObjectはlayout、paint、hit testなどの描画責務を持ちます。この三者を同一物として説明すると、Key、State lifetime、再構築cost、描画無効化の判断を誤ります。

`framework-element-reconciliation` Labは同じ`runtimeType`の兄弟を並べ替えます。Keyなしでは位置に残ったElementがStateを保持し、`ValueKey`ありでは論理項目とStateが一緒に移動することを、画面文字列で観測します。

## Constraint、Size、Position

Box layoutでは親がConstraintを子へ渡し、子がConstraint内のSizeを親へ返し、親が子のPositionを決めます。`framework-rendering-pipeline` Labは独自`RenderBox`を固定`SizedBox`配下へ置き、要求した100x100が50x40へconstrainされることを検証します。

## Invalidation

Property変更をすべてlayoutへ昇格させる必要はありません。

- geometryへ影響する変更は`markNeedsLayout`を呼び、layout後にpaintされる。
- pixelsだけへ影響する変更は`markNeedsPaint`を呼び、既存Sizeを維持したままpaintされる。
- Widget rebuildは必ずRenderObject layoutを意味しない。

LabはTraceをTest Oracleにし、初回`layout -> paint`、paint-only変更では`paint`だけ、extent変更では`layout -> paint`となることを検証します。

## Evidence境界

この二つのLabに接続するID候補は以下です。共通Indexへの追加は所有Agentが行います。

| Node | Element Lab | Rendering Lab |
|---|---|---|
| Capability | `framework.element-reconciliation` | `framework.rendering-invalidation` |
| Claim | `framework.key-controls-state-identity` | `framework.layout-and-paint-are-separate` |
| Proof | `proof.keyed-reconciliation` | `proof.rendering-invalidation` |
| Lab | `lab.framework-element-reconciliation` | `lab.framework-rendering-pipeline` |
| Test | `test.framework-element-reconciliation` | `test.framework-rendering-pipeline` |

Widget TestはFramework contractを実証しますが、実GPU raster、Impeller backend、Shader compilation、Platform View composition、実端末frame timingは証明しません。描画性能のRelease EvidenceにはSimulatorまたは実機Profileのframe timingとtrace artifactが別途必要です。
