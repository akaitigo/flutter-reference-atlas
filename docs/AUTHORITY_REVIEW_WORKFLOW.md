# Authority anchor review workflow

`authority/review-queue.snapshot.json`は、固定済みAuthority bodyから列挙したraw anchorを、人が一次資料を確認できる単位へ分割した作業queueです。Surface分類の結論ではありません。各anchorは人が判断を記録するまで`pending-human`です。

## 入力と境界

- `anchor_id`は`baseline/authority-body-inventory-v1.json`で固定したIDをそのまま使います。
- 各itemはdocument URL、locked source digest、body inventory tool digest、review queue tool digest、locator、固定本文内のcontext範囲とdigestを持ちます。第三者本文、見出し、定義文は保存しません。
- `candidate_cluster_id`は同じsemantic kindとlabel digestを持つ重複候補です。意味が同じ、またはmergeすべきという判定ではありません。
- 優先度0は既存Domain reference locatorとの一致、1は見出しまたは定義、2は構造またはdocument anchorです。優先度はレビュー順の提案だけを表します。
- batchは`priority × semantic kind × anchor ID hash bucket`で決定論的に分割します。batch変更や機械clusterがsemantic decisionを変更することはありません。
- stale documentは`stale_holds`に隔離します。Sourceを更新してdigestを再固定し、body inventoryを再生成するまでレビュー対象へ入れません。

Queue item数、batch数、priority、clusterはSemantic Surface数、Atomic behavior数、Depth達成へ算入しません。

## 人手レビュー

Reviewerはbatch itemの`document_url`と`locator`を一次資料で開き、必要なら固定offset周辺を同一digestの取得bodyで確認します。include、exclude、merge、splitのいずれかを`authority/reviews/decisions.json`へ記録します。自動処理、Agent、cluster結果だけをreviewerにすることはできません。

各decisionには次の情報が必要です。

- 一意な`decision_id`と対象`anchor_ids`
- queue itemと完全一致する`source_bindings`。anchor ID、document ID/URL、locked source digest、inventory/review queue tool digest、locator、context digestを含む
- 40文字以上の具体的な理由
- 人のreviewer識別子、timezone付きISO date-time、`review_method: manual-primary-source`
- 全旧anchorを覆う`mapping`。includeは1件以上の新ID、excludeは空配列、mergeは複数旧IDから同じ新ID集合、splitは1旧IDから2件以上の新IDへ対応させる
- mapping先と同じID集合を持つ`result_items`。各新IDが`surface`または`atomic-behavior`のどちらかを明示する

同じanchorへ複数decisionは作れません。mergeを除き、新IDの共有もできません。decision追加後はqueueを再生成・検証します。未処理anchorまたはstale holdがある間は`status: incomplete-human-review-required`と`authority_semantics_exhaustive: false`を維持します。

## 実行

```sh
python3 tooling/authority_extraction/review_queue.py
python3 tooling/authority_extraction/verify_review_queue.py
python3 -m unittest tooling/authority_extraction/test_review_queue.py
```

通常の`make authority-verify`もqueueをoffline検証します。Source lock、inventory、抽出tool、queue toolが変わった場合、古いbindingを採用せず検証を失敗させます。
