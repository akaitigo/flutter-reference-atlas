# 公開Surface Inventory Generator

Flutter SDKの実体を固定Baselineと照合し、Framework、Engine、Dart SDK、Flutter CLIの有限な入口集合を決定論的JSONへ変換します。

```sh
python3 tooling/surface_inventory/generate.py \
  --sdk-root .tools/flutter-3.47.1/flutter \
  --output baseline/public-surface-inventory.json

python3 tooling/surface_inventory/generate.py \
  --sdk-root .tools/flutter-3.47.1/flutter \
  --output baseline/public-surface-inventory.json \
  --check
```

Inventoryの粒度は公開Library entrypointとその直接export/part edgeです。private APIとCommunity packageは含みません。CLIは利用可能なCommand名を断定せず、固定SDK内のCommand source fileを分類対象として列挙します。Symbol単位のSource/ABI互換性は別Gateであり、このInventoryだけでは証明しません。

対象SDKがBaselineと一項目でも違う場合は生成しません。JSONには絶対Pathや生成時刻を入れないため、同じSDKからbyte-for-byteで再生成できます。
