# Element Reconciliation Lab

FlutterのStateはWidget objectそのものではなくElementへ保持されます。同じ`runtimeType`の兄弟をKeyなしで並べ替えると位置基準でStateが再利用され、`ValueKey`を与えると同じ論理項目へStateが再結合されることを、表示された`currentLabel:mountedFor`で観測します。

```sh
cd labs/framework-element-reconciliation
../../.tools/flutter-3.47.1/flutter/bin/flutter test --reporter expanded
```

このLabが証明するのはFrameworkのWidget/Element/State reconciliationです。GlobalKeyのreparenting cost、Route間State restoration、Platform View lifecycleは別のProof Obligationです。
