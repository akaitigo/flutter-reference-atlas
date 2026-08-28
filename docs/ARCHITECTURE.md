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
- `platform-integration`: Platform Channel / Plugin、Add-to-App、Web / Desktop / MobileのSource ContractとmacOS arm64 FFI runtimeを分離して検証
- `local`: Dart LabとFlutter TestをHostで実行
- `container`: Network無効の固定Dart ImageでPure Dart Labを実行
- `simulator`: iOS SimulatorまたはAndroid Emulator上のIntegration Test

各Profileの結果は互換ではありません。特にWidget Testは実端末またはSimulatorでのPlugin、Lifecycle、Renderingを証明しません。

## 実行Surfaceの分離

実行環境は一つの`runtime`へまとめず、次の証拠を別々に扱います。

| Surface | 証明する範囲 | 証明しない範囲 |
|---|---|---|
| Local Flutter Test | Unit / Widget契約とHost上で実行可能なLab | Simulator、実機、対象OS Runner |
| Container | 固定Image、network無効のPure Dart Lab | Flutter Engine、GPU、Device API |
| Android Emulator | 指定AVD / Android runtime上の製品Integration Test | iOS Simulator、実機、6Platform build、未組込みPlugin / FFI fixture |
| iOS Simulator | iOS Simulator上の対象Integration Test | Android、実機、配布署名 |
| Android / iOS実機 | 指定DeviceとOSでの対象Runtime | 他Device class、他OS、Store配布 |
| Platform build matrix | Android、iOS、Web、macOS、Windows、LinuxごとのBuild / Runner | 未実行Platformと実機挙動 |

Android Emulatorの現在のpassは`execution.android-emulator-integration.2026-08-28`で識別します。これはAndroid 16 / API 36 / arm64-v8aの`medium_phone` AVD上の製品Integration Testであり、iOS Simulator、Android / iOS実機、または6PlatformすべてのBuildを閉じません。接続時に変わる一時的なDevice IDは実行Artifactへ限定します。

## 公開Surface Inventory

`baseline/public-surface-inventory.json`が、固定したFlutter 3.47.1の公開Library entrypointとCLI sourceを有限な分類単位として列挙します。`tooling/surface_inventory/generate.py`による再生成結果とのbyte-for-byte一致と未分類0を検査し、Coverage Epoch内の宣言済み粒度でInventoryを閉じます。

このInventoryは全公開SymbolのAPI互換性表ではなく、Runtime挙動、Plugin ecosystem全体、対象OSでのBuild成功も代替しません。新SDKでは新しいCoverage Epochと差分Inventoryが必要です。

## 完成境界

公開Surface Inventoryは、上記の宣言済み粒度では存在し、未分類0を機械検査できます。ただしInventory GateとRuntime Gateは独立です。Android Emulatorの単一passはiOS Simulator、実機、6Platform build、Platform Channel / Plugin / Add-to-AppのNative runtimeを証明しません。固定Epochでは必須Targetを`covered`または理由付き`infeasible`へ閉じ、必須Profile、Evidence Set、Publication GateとCompletion Certificateを満たした状態だけを`status: complete`とします。
