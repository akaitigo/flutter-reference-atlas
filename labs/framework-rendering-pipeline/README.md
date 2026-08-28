# Rendering Pipeline Lab

独自`RenderBox`のTraceをOracleにし、Flutterの「Constraintは親から子へ、Sizeは子から親へ」とlayout/paint invalidationの境界を確認します。

```sh
cd labs/framework-rendering-pipeline
../../.tools/flutter-3.47.1/flutter/bin/flutter test --reporter expanded
```

このWidget TestはBuild/Layout/Paint schedulingのFramework契約を対象にします。GPU raster、Impeller backend、Shader warm-up、実端末のframe budgetは証明しません。それらはSimulatorまたは実機Profileの別Evidenceが必要です。
