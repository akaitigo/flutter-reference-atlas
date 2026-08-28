# Security Boundary Lab

外部URL、相対Path、Log内Secret、Platform Channel相当の動的応答を、利用前に検証する境界を実証する。

```bash
dart run labs/security-boundary/bin/verify.dart
```

このLabはApplication内部の防御契約を扱う。第三者環境への攻撃、OS Sandboxの突破、Store審査を対象にしない。
