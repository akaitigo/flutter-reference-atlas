# 完成Gate

`status: complete`へ変更する前に、次をすべて満たします。

1. Authority: Flutter 3.47.1配布物と全revision、一次資料、Runtime InventoryのDigestが一致する。
2. Coverage: 必須Targetが`covered`、理由付き`excluded`、理由付き`infeasible`のいずれかで、未分類Surfaceが0である。
3. Mastery: 固定8 Outcomeと14 Surfaceが既存Target Setへ接続され、必須成果物が閉じている。
4. Claim: Capability、Claim、Proof、Lab、Test、Evidenceの孤立Nodeが0である。
5. Execution: local、container、simulatorで適用LabのSetup、Execute、Verify、Cleanupが再実行できる。
6. Operations: Observability、Backup、Restore、Upgrade、Incident、Capacityの適用判断とDrill Evidenceがある。
7. Skill: Router Evalが最低合格率を満たし、Coverage Gapと権限境界を守る。
8. Publication: Apache-2.0、NOTICE、Root SBOM、第三者Manifest、Provenance、Secret、Trademark Gateが通る。

Core CLIの`atlas validate`は5 ManifestのSchema形状を検証し、`atlas audit .`はID、Epoch、Target Set、Routerを横断監査します。Overlay ValidatorはManifest間Digest、Claim/Evidence Graph、Artifact、Skill Eval、Legal Path、Status整合を補います。すべての成功が必要であり、現在は全体Gate未達です。
