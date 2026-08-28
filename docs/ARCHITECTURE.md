# Architecture

## 境界

本アトラスは`product`と`language-platform`の二つのArchetypeを持ちます。Flutter製品を一つ実装しつつ、製品へ不自然に混在させるべきでないSDK能力を独立Labで実証します。

```text
Authority Lock
  -> Coverage Target
  -> Capability
  -> Claim
  -> Proof Obligation
  -> Reference System / Lab
  -> Test Oracle
  -> Evidence
  -> Router Eval
  -> Completion Certificate
```

Core Schemaに存在しないFlutter固有Nodeは`atlas/`のOverlayとして保持し、共通Schemaを変更しません。他Subject AtlasのSource Tree、Default Branch、Git submoduleには依存しません。

## Production Reference Product

`reference-systems/operations-workspace`は、インシデントの一覧、選択、作成、状態遷移を扱うAdaptive UIです。Feature-firstで配置し、単純なCRUDへ不要なUse Case層を追加しません。状態管理はimmutable stateと`ChangeNotifier`を基準にし、Community状態管理Packageの比較は将来のLabへ隔離します。

## Labs

- `offline-conflict-resolution`: lost updateを検出するPure Dartの決定論的競合解決
- `widget-lifecycle`: Controller lifecycleとWidget再構築の契約
- `local`: Dart LabとFlutter TestをHostで実行
- `container`: Network無効の固定Dart ImageでPure Dart Labを実行
- `simulator`: iOS SimulatorまたはAndroid Emulator上のIntegration Test

各Profileの結果は互換ではありません。特にWidget Testは実端末またはSimulatorでのPlugin、Lifecycle、Renderingを証明しません。

## 完成境界

Flutter 3.47.1公開Surfaceの機械Inventoryが存在しない現時点では、有限性はVersionとAuthority Corpusまで固定され、Surface分類Gateは未完了です。API Inventory Generatorが全公開SymbolとCLI Surfaceを抽出し、未分類0を証明するまで完成しません。
