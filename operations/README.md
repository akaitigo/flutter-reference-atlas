# 運用判断

| 項目 | 適用 | 現在の判断 |
|---|---:|---|
| Observability | 適用 | Test Artifact、Flutter Error、状態遷移を構造化してEvidenceへ保存する。 |
| Backup | 適用 | `labs/operations-drill`でschema v1 FixtureをExportし、Digest付きBackup round-tripを検証する。 |
| Restore | 適用 | schema v1を非破壊でv2へ移行してRestoreし、破損と未知Versionを拒否する。 |
| Upgrade | 適用 | Flutter 3.47.1を不変に保ち、新SDKは新Epochで差分Inventoryを作る。 |
| Incident | 適用 | Lab失敗、Evidence陳腐化、依存脆弱性を別Runbookで扱う。 |
| Capacity | 適用 | `FramePerformanceMonitor`を120 sampleへ制限し、slow count、p95、worstを診断画面へ公開する。Binary Sizeと実機MemoryはRunner Matrix再評価時に追加する。 |

Backup、Migration、Restore、破損拒否、Cleanupは正式Local Evidenceで実行済みです。製品Integration TestはAndroid Emulatorで`execution.android-emulator-integration.2026-08-28`としてpassしていますが、iOS Simulator、Android / iOS実機、全Native Runnerを要する運用証拠は別Surfaceとして未Closureのまま分離します。
