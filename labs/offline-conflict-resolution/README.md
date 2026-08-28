# Offline Conflict Resolution Lab

同じBase Versionから生じた複数Revisionを、Logical ClockとActor IDで決定論的に解決し、payload差分をlost updateとして検出します。

```bash
dart run bin/verify.dart
```

決定論の範囲は同じ入力集合、同じ比較規則、同じDart言語Semanticsです。実Network順序、Clock同期、永続化TransactionはこのLabでは証明しません。
