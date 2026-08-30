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

Core CLIの`atlas validate`は5 Manifest、Claim実体、Evidence、第三者Manifest、ProvenanceのSchema形状を検証し、`atlas audit .`はID、Epoch、Target Set、Routerを横断監査します。Overlay ValidatorはManifest間Digest、Claim/Evidence Graph、Artifact、Skill Eval、Legal Path、Status整合を補います。

現在、Authority、有限Coverage分類、Mastery、Claim実体、Formal Local、Container、Android Emulator、Operations Drill、Skill、SBOM/第三者Manifest/Provenanceは閉じています。local、container、simulatorの必須Profileはpass Evidenceを持ち、Core GeneratorがDCO付きsource commitをCompletion Certificateへ束縛します。iOS Simulator、Android / iOS実機、6PlatformすべてのNative Runner、未組込みのPlatform Channel / Plugin / Add-to-App / FFI runtimeは別のEvidence境界であり、理由付き`infeasible`または明示的Gapをpassへ読み替えません。

Evidence Dependency Graph GateはSource、Harness、Runtime、Profileの変更後に影響Evidenceが実再実行されたことを検査する独立Gateです。Graphがcurrentでも上記Runtime GapやAuthority Gapは閉じません。Subject Definitive Certificate生成時はGraph digestを`evidence_dependency_digest`へ固定し、stale、retry、再実行対象漏れ、構造縮小が1件でもあれば発行しません。
