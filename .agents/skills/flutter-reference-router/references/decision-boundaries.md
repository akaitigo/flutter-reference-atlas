# 判断境界

- Production Productはimmutable state、`ChangeNotifier`、Repository境界を基準にする。RiverpodやBlocは比較Labへ隔離する。
- 単純CRUDへDomain層を強制しない。競合、権限、状態遷移、再試行など独立Policyがある場合に追加する。
- FFI、Shader、Add-to-App、Web JS/Wasm、複数状態管理の比較を製品へ不自然に混在させない。
- Widget Testは実Simulatorまたは実機Evidenceの代替ではない。
- `infeasible`は同等な代替証拠を意味しない。環境導入後に再評価する。
- 3.47.1以外のSDKへ更新する場合は既存Epochを書き換えず、新Epochを作る。
- `authority/reviews/decisions.json`へのinclude、exclude、merge、splitは人が一次資料を確認する。Agentはpriority、cluster、batchを判断結果として扱わない。
- `authority/review-queue.snapshot.json`のstale holdはSource lockを自動更新せず、明示的relock手順まで停止する。
- 曖昧Query、未知Query、未許可Mutationはfail closedで返し、近いTargetへ推測でRouteしない。
- 統合Reference App TraceはCross-behavior境界の証拠であり、直接Mapping・実Platform identity・専用Harness/Artifactを持たないSurface固有Proofへ昇格させない。
- Scenario gapはSurface＋Scenario＋全Variantの専用実Platform Reportがretry 0、first-attempt pass、Oracle、Trace、Artifact、Source／Harness digest、Runtime identityを満たす場合だけ閉じる。既存Capture metadataは流用しない。
- 実行Evidenceはfull-run pass後に原子的directory swapで公開されたbundleだけを使う。staging、失敗run、部分更新、新旧`run_id`混在をRoute根拠にしない。
