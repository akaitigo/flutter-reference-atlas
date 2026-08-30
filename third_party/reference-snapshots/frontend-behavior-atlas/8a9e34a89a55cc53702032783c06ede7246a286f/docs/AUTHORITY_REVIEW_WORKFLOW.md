# Authority anchor review workflow

`authority/review-queue.snapshot.json`は、固定済みAuthority bodyから列挙した15,963 anchorを、人が一次資料を確認できる単位へ分割した作業queueです。これはSurface分類の結論ではありません。全anchorは、人が判断を記録するまで`pending-human`です。

## 入力と境界

- `anchor_id`は`baselines/authority-body-inventory-v1.json`で固定したIDをそのまま使います。
- 各itemはdocument URL、locked source digest、body inventory tool digest、review queue tool digest、locator、固定本文内のcontext範囲とdigestを持ちます。第三者本文、見出し、定義文は保存しません。
- `candidate_cluster_id`は同じsemantic kindとlabel digestを持つ重複候補です。意味が同じ、またはmergeすべきという判定ではありません。
- 優先度0は既存Domain reference locatorとの一致、1は見出しまたは定義、2は構造／document anchorです。優先度はレビュー順だけを表します。
- batchは`priority × semantic kind × anchor ID hash bucket`で決定論的に分割します。batch変更や機械クラスタがsemantic decisionを変更することはありません。
- 3件のstale documentは`stale_holds`に隔離しています。Sourceを更新してdigestを再固定し、body inventoryを再生成するまでレビュー対象へ入れません。

## 人手レビュー

Reviewerはbatch itemの`document_url`と`locator`を一次資料で開き、必要なら固定offset周辺を同一digestの取得bodyで確認します。include、exclude、merge、splitのいずれかを`authority/reviews/decisions.json`へ記録します。自動処理、Agent、cluster結果だけをreviewerにすることはできません。

各decisionには次の情報が必須です。

- 一意な`decision_id`と対象`anchor_ids`
- queue itemと完全一致する`source_bindings`。anchor ID、document ID/URL、locked source digest、inventory/review queue tool digest、locator、context digestを含む
- 40文字以上の具体的な決定理由
- 人のreviewer識別子、ISO date-time、`review_method: manual-primary-source`
- 全旧anchorを覆う`mapping`。includeは1件以上の新ID、excludeは空配列、mergeは複数旧IDから同じ新ID集合、splitは1旧IDから2件以上の新IDへ対応させる
- mapping先と同じID集合を持つ`result_items`。各新IDが`surface`または`atomic-behavior`のどちらかを明示する

同じanchorへ複数decisionは作れません。mergeを除き、新IDの共有もできません。decisionの追加後は`pnpm authority:review:generate`でsummaryを更新し、`pnpm authority:review:verify`を通します。review済み件数が増えても、未処理anchorまたはstale holdがある間は`status: incomplete-human-review-required`と`authority_semantics_exhaustive: false`を維持します。

## Priority 0 review packet

`authority/review-packets/priority-0/`は、既存Domain reference locatorと一致したpriority 0 anchorを一件ずつ確認するpacketです。各packetは一次資料deep-link、固定source/context binding、既存Domain候補投影、確認質問をまとめます。複数のDomain edgeが同じanchorを参照する場合と、同じPatternが複数anchorを参照する場合は`proposed_cluster_ids`を付けます。

Clusterはレビュー順と比較対象を提示するだけです。`semantic_decision: none-machine-proposal-only`と`human_reviewed: false`を固定し、同一Surface、merge対象、include対象とは判定しません。

`authority/portal/review-export.v1.json`は共通Portalへ渡すread-only exportです。Schema、queue、packet index、producer toolのdigestを持ち、deep-link表示とdecision状態表示だけを許可します。`write_decisions: false`、`promote_human_review: false`であり、Portalから`decisions.json`を自動更新しません。

## Stale document候補

`pnpm authority:stale:inspect`は明示的なNetwork操作で、3 stale documentについてsame URLの観測差分と公式Repositoryのcommit固定候補を`authority/stale-relock-candidates.json`へ記録します。本文や抜粋は保存せず、URL、digest、byte数、Content-Type、commit、pathだけを保存します。この操作は`authority/sources.snapshot.json`、Pattern reference、既存anchorを変更しません。

Relockには、人による候補選択、Pattern reference変更、sourceとsource-referenceの全旧→新Mapping、実行Proof、専用Migration Evidence、Authority再取得／再抽出、anchorの単調追加、全Gateが必要です。候補reportだけを根拠にlocked digestを更新してはいけません。

## 実行

```sh
pnpm authority:review:generate
pnpm authority:review:verify
pnpm authority:review:test
pnpm authority:portal:generate
pnpm authority:portal:verify
pnpm authority:portal:test
pnpm authority:stale:verify
```

通常の`pnpm check`と`pnpm build`もqueueを再生成・検証します。Source lockや抽出toolが変わった場合、古いbindingを黙って採用せず検証を失敗させます。
