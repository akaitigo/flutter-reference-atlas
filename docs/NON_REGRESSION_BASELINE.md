# 公開main非後退Baseline

公開済みmainのcommit `0b5ff9311f88ee5bcb76f224ee71668c668ea14b` は、Definitive Gate v2で追加する作業の最低線です。`baseline/public-main-non-regression-v1.json`は、そのcommitのGit objectから生成した機械可読snapshotです。作業ツリーからbaselineを採取してはいけません。

`make non-regression-audit`は、公開済みのTest/Lab/Target/Claim/Proof/Evidence/Artifact/Source/Skill Eval/CI Job・Step、固定SDKとCoverage Epochを検査します。追加は許可します。既存IDの削除、requiredやcoveredの弱体化、接続の削除、受入条件・oracle・Evidence record・Artifact digest・Source lock・Skill期待値・CI runner/stepの変更、Test名の削除、Test/Assertion数の減少は失敗です。Definitive未達項目は`partial`または未完のまま保持し、公開baselineを未実行扱いへ戻して帳尻を合わせません。

置換が避けられない場合は`migrations/non-regression-mappings.json`へ旧ID、新ID、理由、Migration Evidence ID、同等以上のProof IDを記録します。新ID、Evidence、Proofが現行Graphに実在しないMappingは無効です。Mappingは移行を自動承認するものではなく、差分Reviewの入力です。

Evidence Dependency Graph導入後の加法baselineは`baseline/evidence-dependency-v1.json`です。既存公開main snapshotを置換せず、Graph input、実run、機械列挙output、unit/widget/integration/golden/performance/platform/device等のEvidence family、Profile、first-attempt、10 Scenario・540 row・4 row tranche上限、Proof/Closure Plan構造を追加固定します。Goldenは0件の明示Gapを維持し、別種別Evidenceへの置換でpresentへ変更しません。`make non-regression-audit`は両baselineを検証します。

Baselineの再生成は、公開mainを変更する正当なRelease判断とReviewを経た場合だけ、固定commitを明示して行います。

```console
python3 tooling/non_regression/audit.py --baseline-ref <approved-commit> --write
python3 tooling/non_regression/audit.py --check-snapshot
```
