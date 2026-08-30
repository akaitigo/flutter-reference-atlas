# Repository instructions

このRepositoryは`reference-atlas-core` v1のSubject Atlasであり、Flutter 3.47.1に固定した製品・言語Platform実証を所有する。

## Canonical sources

- 共通契約は`reference-atlas-core` main commit `cf9e6e2d981305c83f970c1f21a1ddc9c1109263`を正本とする。
- Definitive v2 Evidence Dependency Graph契約は`reference-atlas-core` main/CI成功commit `072d7ca77981f51754e824d70c6d4ecd55ea67e5`を正本とする。
- `atlas.yaml`、`mastery.yaml`、`sources.lock.yaml`、`coverage.yaml`、`skill.package.yaml`を共通Manifestの正本とする。
- Flutter固有のCapability、Claim、Proof Obligation、Lab対応は`atlas/**/*.json`と`labs/index.json`を正本とする。
- 生成ReferenceやEvidenceを先に手編集せず、正本とGeneratorまたはHarnessを変更する。

## Language and scope

- 利用者向け文書、Skill、CLIメッセージは日本語を正本とする。
- Schema Key、ID、Path、API名、Repository名、上流正式名称は英語を維持する。
- Flutter 3.38.5のEvidenceを3.47.1のRelease Evidenceへ流用しない。
- 公開Package全件、private API、Store実公開をCoverageへ暗黙に含めない。

## Evidence discipline

- Canonical chain `Authority -> Target -> Capability -> Claim -> Proof -> Lab -> Test -> Evidence -> Skill Eval`を切断しない。
- `covered`へ変更する前にpass EvidenceとArtifact Digestを接続する。
- local、container、simulatorを別Profileとして扱い、ContainerをSimulatorの代替にしない。
- Setup、Execute、Verify、Cleanupを再実行可能にし、失敗注入を第三者環境へ作用させない。
- 上流不具合や環境不足をskipで隠さず、`infeasible`または明示的Gapとして記録する。

## Status and publication

- 全Gate通過前は`atlas.yaml`の`status: incomplete`を維持する。
- Completion CertificateはGeneratorだけが作成し、手編集しない。
- GitHub公開、Release、Store送信、外部Registry登録は利用者の明示許可なしに行わない。
- 独自コードと文書はApache-2.0。第三者コード、文書、Asset、商標、生成物は別々に出典と条件を記録する。
