# 判断境界

- Production Productはimmutable state、`ChangeNotifier`、Repository境界を基準にする。RiverpodやBlocは比較Labへ隔離する。
- 単純CRUDへDomain層を強制しない。競合、権限、状態遷移、再試行など独立Policyがある場合に追加する。
- FFI、Shader、Add-to-App、Web JS/Wasm、複数状態管理の比較を製品へ不自然に混在させない。
- Widget Testは実Simulatorまたは実機Evidenceの代替ではない。
- `infeasible`は同等な代替証拠を意味しない。環境導入後に再評価する。
- 3.47.1以外のSDKへ更新する場合は既存Epochを書き換えず、新Epochを作る。
