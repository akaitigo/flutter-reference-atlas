# Baselineと公開Surface Inventory

## 固定対象

Coverage Epoch `2026-08-28`の対象はFlutter stable 3.47.1です。配布Bundle、Framework、Engine、Dart、DevToolsを別々の識別子として扱い、一つでも不一致ならInventoryを生成しません。

| Component | Version / revision |
|---|---|
| Flutter | `3.47.1` |
| Framework | `6655482ec06e547f90abf8ae7590466f4415978d` |
| Engine | `5d531788691ec3404cac0cee66ead4007b177363` |
| Engine content | `11d79658c444477b06513d32b52c8c4ccb7276b0` |
| Dart | `3.13.1` / `852b3e3608906afbe6102573cfd4407aeedd1b78` |
| DevTools | `2.60.0` / `12d595649f189f1896722623f72599077f476848` |
| Skia | `8df24be66531469e576a806749a0202ae26b8d08` |

macOS arm64 Bundleは2,259,049,326 byteです。`sources.lock.yaml`のSHA-256と照合後に展開し、Bundle自体はRepositoryへ収録しません。再検証時は同じ公式URLから取得し、展開前にDigestを照合します。

## Inventoryの有限性

`tooling/surface_inventory/generate.py`は対象SDK実体から次を生成します。

- `package:flutter`の公開top-level Library entrypointと直接export edge
- Engineのnative/web `dart:ui`実装入口と`dart:ui_web`
- Dart SDK `libraries.json`にある公開LibraryとPlatform section
- Flutter CLIの分類対象Command source file

`dart:html_common`、`dart:nativewrappers`、`dart:vmservice_io`は名前がunderscoreで始まりませんが実装内部Libraryなので、理由付き除外としてJSONに残します。private Framework source、Community package、全pub.dev package、内部CLI classは公開APIへ昇格させません。

```sh
python3 tooling/surface_inventory/generate.py \
  --sdk-root .tools/flutter-3.47.1/flutter \
  --output baseline/public-surface-inventory.json

python3 tooling/surface_inventory/generate.py \
  --sdk-root .tools/flutter-3.47.1/flutter \
  --output baseline/public-surface-inventory.json \
  --check
```

生成JSONは絶対Pathと生成時刻を持たないため決定論的です。現在の粒度はLibrary entrypoint/export edgeです。全公開SymbolのSource/API/ABI差分、deprecated member、conditional exportごとの到達可能性は別の分類Gateであり、このInventoryの`complete`をAtlas全体の完成と解釈してはいけません。

## 取得と実行の境界

- Target SDKは`.tools/flutter-3.47.1/flutter`に配置し、Git管理しません。
- `FLUTTER_SUPPRESS_ANALYTICS=true`で自動送信を抑止します。
- `flutter pub get --offline`でLock済みCacheだけを使い、テストは`flutter test --no-pub`で依存解決と実行を分離します。
- Codex sandbox内ではFlutter Testがloopback socketを開くため、承認済みのlocal実行が必要です。
- 3.38.5の結果はCompatibility観測であり、3.47.1 Release Evidenceには接続しません。
