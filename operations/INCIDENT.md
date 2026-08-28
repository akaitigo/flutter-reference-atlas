# Incident Runbook

1. 失敗したClaim、Environment Profile、Harness、Source Digestを特定する。
2. Evidence Artifactを保持し、再試行で上書きしない。
3. Product defect、Harness defect、Environment drift、Upstream defectを分離する。
4. Upstream defectは最小再現、対象Version、影響Platform、回避策、再検証条件を記録する。
5. 原因不明のretry、無期限skip、Evidenceの手編集を禁止する。
