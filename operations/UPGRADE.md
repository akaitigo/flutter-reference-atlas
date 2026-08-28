# Upgrade Runbook

1. 既存EpochとCertificateを変更しない。
2. 新Flutter stableの公式Release Manifest、配布物Digest、Framework、Engine、Dart、DevTools revisionを固定する。
3. 公開Surface Inventoryを両Epochで生成して追加、変更、Deprecated、削除を分類する。
4. 全Labと製品Flowを新SDKで再実行し、新Evidence Setを生成する。
5. Migration Guide、既知不具合、回避策、Platform Toolchain差分を記録する。
6. 新Epochの全Gate通過後だけ新ReleaseとCertificateを発行する。
