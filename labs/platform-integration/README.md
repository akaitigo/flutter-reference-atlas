# Platform Integration Source Contract Lab

Platform Channel / Plugin、Dart FFI、Add-to-App、Web / Desktop / Mobile境界を検査するLabです。証拠を次の二層へ分離します。

1. Source Contract verifierは、同梱した契約ManifestとSource fixtureの対応だけを決定論的に検査します。Native runtimeでのBuild、Plugin登録、Method呼出、Flutter Engine埋め込み、各Platformでの起動成功は証明しません。
2. macOS arm64 FFI runtime verifierは、一時dylibを実際にBuildしてloadし、symbolを解決して呼び出します。この結果はmacOS arm64だけのRuntime Evidenceであり、他ABIやFlutter Runnerの証拠ではありません。

Android Emulator上の製品Integration Testは`reference-systems/operations-workspace`が生成する別の証拠です。このLabのSource ContractやmacOS FFI runtimeを、Android Emulator実行の代替にも、その逆にも使いません。

## 検証対象

- Platform Channel: Dart、Kotlin、SwiftでChannel名とMethod名が一致すること。
- Plugin: `pubspec.yaml`のPlatform登録とNative plugin class / lifecycle宣言が一致すること。
- Dart FFI: C headerとDart `@Native` bindingでsymbol名と32-bit整数ABI宣言が一致すること。
- Add-to-App: AndroidとiOSで明示的にEngineを起動し、共有Engine IDを使うこと。
- Web: conditional exportのWeb実装だけが`dart:js_interop`へ依存し、`dart:io`へ依存しないこと。
- Desktop / Mobile: IO実装内で対象Platformを分岐し、Web APIへ依存しないこと。
- Evidence境界: Source ContractでNative未実行の`runtime_evidence.status`を`pass`にしないこと。

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
- Source Contract出力では、Contractごとの`evidence.runtime_evidence`が`not_collected`または`blocked`であり、`pass`ではない。
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
- Android Emulatorでの製品Integration Testは`execution.android-emulator-integration.2026-08-28`として実行済みです。ただし、Platform Channel / Plugin、Add-to-App、Android ABI向けFFIのRuntime Evidenceには、各fixtureを組み込んだNative host、Gradle、必要に応じてNDK/C compilerが別途必要です。
- full Xcode、CocoaPods、iOS Simulator。実機・配布検証では署名Team/Profileも必要です。
- Add-to-App用のNative host projectと生成済みFlutter module artifact。
- 対応Web Browser、およびmacOS / Windows / Linux各対象OSのDesktop toolchain。
- Android / iOS実機での確認には、個別のDevice、署名、接続条件が必要です。Simulator / Emulatorのpassを実機Evidenceとして扱いません。

macOS arm64のDart FFIだけは、正式Dart 3.13.1とApple clang 17でruntime verifierを再実行できます。Android/iOS/Add-to-App、Web/Desktop/Mobileのruntimeは、各条件を導入して対象Runnerで再実行するまで`not_collected`または`blocked`のままです。Source ContractやmacOS FFIのpassをSimulator、実機、署名、Store公開の代替証拠にはしません。

## Coverage状態

このLabはCanonical chainへ接続済みです。

- Source Contract: `platform.channel-plugin-contract`、`platform.add-to-app-contract`、`platform.desktop`、`platform.mobile`から、対応Claim、`lab.platform-integration-source-contract`、`test.platform-source-contract`、`execution.formal-local-closure.2026-08-28`へ接続します。
- FFI runtime: `platform.ffi-macos`から`platform.ffi-runtime-call`、`lab.platform-ffi-runtime`、`test.platform-ffi-runtime`、同じFormal Local Evidenceへ接続します。
- Web release build: `platform.web`はSource Contractだけでなく、製品のWeb release artifactを含むFormal Local Evidenceへ接続します。

`execution.android-emulator-integration.2026-08-28`は`lab.simulator-integration`による製品Integration Testの証拠で、このLabのPlatform Channel / Plugin、Add-to-App、FFI fixtureのRuntime Evidenceではありません。Canonical接続が存在しても、iOS Simulator、Android / iOS実機、残るNative Runner、他ABIの実行を証明したことにはなりません。
