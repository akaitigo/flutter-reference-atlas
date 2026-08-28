# コントリビューション

変更はClaimまたはCoverage Target単位で小さくし、実装、Test、Evidence、一次資料、第三者権利、移行影響を同じ変更へ含めてください。生成ReferenceやCertificateだけを手編集してはいけません。

すべてのCommitにDeveloper Certificate of Originへの同意を示す`Signed-off-by`行を付けてください。第三者成果物を追加する場合は、出典、Version、License、再配布可否、対象File、Digestを`third_party/manifest.yaml`とSBOMへ記録します。

完成状態の変更にはCore `atlas validate`、Overlay Validator、全Profile Evidence、Skill Eval、Publication Gateの成功が必要です。
