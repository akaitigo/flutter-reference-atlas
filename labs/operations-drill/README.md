# Operations Drill

状態SnapshotのBackup、schema v1からv2への非破壊Migration、Restore、破損入力と未知Versionの拒否、Cleanupを一回の決定論的Labで検証する。

```bash
dart run labs/operations-drill/bin/verify.dart
```

このLabは端末内Dataの手順を実証する。Store配布、Cloud Backup、実利用者DataのRecoveryを証明しない。
