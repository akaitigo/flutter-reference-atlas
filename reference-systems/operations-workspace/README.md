# Operations Workspace

Flutter 技術実証アトラスのProduction Reference Productです。特定の状態管理Packageへ依存せず、Flutterの公開APIで次の小さな契約を観測できます。

- immutableな`WorkspaceState`と`ChangeNotifier`による状態所有、遅延した古い読込結果の拒否
- 名前付き`Navigator` RouteによるWorkspaceと診断画面の往復
- `CustomPainter`による状態別件数描画と、同じ内容を提供するSemantics
- Repositoryの読込・保存失敗、入力を保持した冪等な再試行、利用者向け成功通知
- 見出し、選択状態、live region、Keyboard focus、進捗Semantics
- 空白正規化、文字数上限、制御文字・双方向表示制御の拒否、生のRepository例外を秘匿する入力境界
- 公開`FrameTiming` callbackを用いた上限付きFrame sample、slow frame、p95、worstの観測

```bash
flutter analyze
flutter test
flutter test integration_test -d <simulator-device-id>
flutter run -d chrome
```

Unit/Widget Testは入力Policy、状態競合、描画Semantics、Failure/Recovery、Navigation、Performance集約を決定論的に検証します。Integration Testは実際のSimulator / Emulator Deviceを指定した時だけSimulator Evidenceになります。host上の`flutter test integration_test`をSimulator Evidenceとして扱いません。

正式Baseline 3.47.1ではUnit / Widget Testに加え、`execution.android-emulator-integration.2026-08-28`が`medium_phone` AVD（Android 16 / API 36 / arm64-v8a）上のIntegration Testを記録します。このpassはiOS Simulator、Android / iOS実機、6Platform build、Platform APIやProfile別Performance traceの証拠ではありません。一時的なDevice IDはEvidence Artifactだけに記録します。

ローカルSDK 3.38.5の結果は互換性確認であり、正式Baseline 3.47.1のEvidenceではありません。永続化、同期、認証、Deep Link、Platform API、正式なProfile別Performance測定、ReleaseはCoverage上未完了です。
