# 運用判断

| 項目 | 適用 | 現在の判断 |
|---|---:|---|
| Observability | 適用 | Test Artifact、Flutter Error、状態遷移を構造化してEvidenceへ保存する。 |
| Backup | 適用 | 将来のローカルDB FixtureをExportする。現製品はMemory RepositoryのみでDrill未実装。 |
| Restore | 適用 | Export Fixtureから状態を再構築する。現時点は未実装。 |
| Upgrade | 適用 | Flutter 3.47.1を不変に保ち、新SDKは新Epochで差分Inventoryを作る。 |
| Incident | 適用 | Lab失敗、Evidence陳腐化、依存脆弱性を別Runbookで扱う。 |
| Capacity | 適用 | Item数、Frame時間、Memory、Binary Sizeの予算を将来Targetへ固定する。 |

現時点では文書化のみであり、運用Closureを満たしたとは扱いません。
