# Platform Integration Source Contract Lab

Platform Channel / Plugin、Dart FFI、Add-to-App、Web / Desktop / Mobile境界を、実機、署名、Native toolchainなしで決定論的に検査するLabです。

このLabが証明するのは、同梱した契約ManifestとSource fixtureの対応だけです。Native runtimeでのBuild、Plugin登録、Method呼出、FFI symbol解決、Flutter Engine埋め込み、各Platformでの起動成功は証明しません。

## 検証対象

- Platform Channel: Dart、Kotlin、SwiftでChannel名とMethod名が一致すること。
- Plugin: `pubspec.yaml`のPlatform登録とNative plugin class / lifecycle宣言が一致すること。
- Dart FFI: C headerとDart `@Native` bindingでsymbol名と32-bit整数ABI宣言が一致すること。
- Add-to-App: AndroidとiOSで明示的にEngineを起動し、共有Engine IDを使うこと。
- Web: conditional exportのWeb実装だけが`dart:js_interop`へ依存し、`dart:io`へ依存しないこと。
- Desktop / Mobile: IO実装内で対象Platformを分岐し、Web APIへ依存しないこと。
- Evidence境界: Native未実行の`runtime_evidence.status`を`pass`にしないこと。

Fixtureは製品へコピーするTemplateではありません。公開Package全般、private API、各OSの全Plugin lifecycleを代表しません。

## Setup / Execute / Verify / Cleanup

Repository Rootから実行します。

```bash
.tools/flutter-3.47.1/flutter/bin/dart run labs/platform-integration/bin/verify.dart
.tools/flutter-3.47.1/flutter/bin/dart run labs/platform-integration/test/source_contract_verifier_test.dart
.tools/flutter-3.47.1/flutter/bin/dart run labs/platform-integration/bin/verify_ffi_runtime.dart
```

VerifierはJSONを1行出力し、次をObservable Outcomeとします。

- `verdict`が`pass`。
- `contracts_checked`が`7`。
- `evidence.source_contract`が`pass`。
- Contractごとの`evidence.runtime_evidence`が`not_collected`または`blocked`であり、`pass`ではない。
- Test出力の`tests`に`baseline-source-contract`、`path-boundary`、`mutation-detection`が含まれる。
- FFI runtime出力で`evidence_layer`が`runtime_evidence`、`target`が`macos-arm64`、`operation`が`atlas_add(19, 23)`、`actual`が`42`、`cleanup`と`verdict`が`pass`。

Source verifierに生成物はありません。TestとFFI runtime verifierは一時Directoryだけを使い、`finally`でdylibごと削除します。FFI verifierはShellを介さず、固定した`/usr/bin/clang`へ引数Arrayを渡します。

## Source ContractとRuntime Evidenceの分離

| Integration | Source Contractで確認すること | Runtime Evidenceに残すこと |
|---|---|---|
| Platform Channel / Plugin | Channel、Method、Plugin class、attach / detach宣言 | Flutter Engine上の登録とAndroid/iOSでの応答 |
| Dart FFI | C header、実装、Dart bindingのsymbol / ABI宣言 | macOS arm64では一時dylibのload、symbol解決、実呼出。他ABIは未収集 |
| Add-to-App | Engine生成、entrypoint実行、Engine ID共有 | Native host build、画面表示、lifecycle、artifact組込み |
| Web | conditional exportとWeb専用import | Web buildと対応Browserでの起動 |
| Desktop | IO分岐とDesktop OS判定 | macOS / Windows / Linux別のbuildと起動 |
| Mobile | IO分岐とAndroid / iOS判定 | Emulator / Simulator / 実機でのbuildと起動 |

## 外部Blocker

- Source verifierとmacOS arm64 FFI runtime verifierは、導入済みの正式Dart 3.13.1を使います。Flutter 3.38.5の結果は3.47.1 Release Evidenceへ流用しません。
- Android SDK、Gradle、Android ABI向けNDK/C compiler、Emulatorまたは実機。
- full Xcode、CocoaPods、iOS Simulator。実機・配布検証では署名Team/Profileも必要です。
- Add-to-App用のNative host projectと生成済みFlutter module artifact。
- Web Browser、およびmacOS / Windows / Linux各対象OSのDesktop toolchain。

macOS arm64のDart FFIだけは、正式Dart 3.13.1とApple clang 17でruntime verifierを再実行できます。Android/iOS/Add-to-App、Web/Desktop/Mobileのruntimeは、各条件を導入して対象Runnerで再実行するまで`not_collected`または`blocked`のままです。Source ContractやmacOS FFIのpassをSimulator、実機、署名、Store公開の代替証拠にはしません。

## Coverage状態

このLabは`exploratory`です。この変更では`coverage.yaml`、`labs/index.json`、共通Index、Evidenceを更新しないため、Canonical chainへは未接続です。対応Capability / Claim / Proof / Test / Evidenceを正本へ接続し、Flutter 3.47.1でEvidenceを再生成するまでCoverage gapは残ります。
