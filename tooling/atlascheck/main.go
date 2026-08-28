// SPDX-License-Identifier: Apache-2.0
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

type atlasManifest struct {
	ID       string `yaml:"id"`
	Status   string `yaml:"status"`
	Coverage struct {
		Epoch string `yaml:"epoch"`
	} `yaml:"coverage"`
	Skills struct {
		Router struct {
			Path string `yaml:"path"`
		} `yaml:"router"`
		Evals string `yaml:"evals"`
	} `yaml:"skills"`
	Completion struct {
		RequiredProfiles []string `yaml:"required_profiles"`
		Certificate      string   `yaml:"certificate"`
	} `yaml:"completion"`
}

type masteryManifest struct {
	AtlasID  string `yaml:"atlas_id"`
	Epoch    string `yaml:"epoch"`
	Outcomes []struct {
		ID         string   `yaml:"id"`
		TargetSets []string `yaml:"target_sets"`
	} `yaml:"outcomes"`
	Surfaces []struct {
		ID            string   `yaml:"id"`
		Applicability string   `yaml:"applicability"`
		TargetSets    []string `yaml:"target_sets"`
	} `yaml:"surfaces"`
}

type sourceLock struct {
	AtlasID string `yaml:"atlas_id"`
	Epoch   string `yaml:"epoch"`
	Sources []struct {
		ID     string `yaml:"id"`
		URL    string `yaml:"url"`
		Digest string `yaml:"digest"`
	} `yaml:"sources"`
}

type coverageManifest struct {
	AtlasID             string `yaml:"atlas_id"`
	Epoch               string `yaml:"epoch"`
	AuthorityLockDigest string `yaml:"authority_lock_digest"`
	TargetSets          []struct {
		ID       string `yaml:"id"`
		Sequence int    `yaml:"sequence"`
	} `yaml:"target_sets"`
	Targets []struct {
		ID          string   `yaml:"id"`
		TargetSet   string   `yaml:"target_set"`
		Requirement string   `yaml:"requirement"`
		State       string   `yaml:"state"`
		ClaimIDs    []string `yaml:"claim_ids"`
		EvidenceIDs []string `yaml:"evidence_ids"`
	} `yaml:"targets"`
}

type claimsDocument struct {
	Claims []struct {
		ID                string   `json:"id"`
		CapabilityID      string   `json:"capability_id"`
		ProofObligationID string   `json:"proof_obligation_id"`
		AuthorityIDs      []string `json:"authority_ids"`
		Acceptance        string   `json:"acceptance"`
		LabID             string   `json:"lab_id"`
		TestID            string   `json:"test_id"`
	} `json:"claims"`
}

type capabilitiesDocument struct {
	Capabilities []struct {
		ID string `json:"id"`
	} `json:"capabilities"`
}

type proofsDocument struct {
	Proofs []struct {
		ID string `json:"id"`
	} `json:"proof_obligations"`
}

type labsDocument struct {
	Labs []struct {
		ID   string `json:"id"`
		Path string `json:"path"`
	} `json:"labs"`
	Tests []struct {
		ID   string `json:"id"`
		Path string `json:"path"`
	} `json:"tests"`
}

type routesDocument struct {
	Routes []struct {
		CapabilityID string   `json:"capability_id"`
		TargetID     string   `json:"target_id"`
		State        string   `json:"state"`
		AuthorityIDs []string `json:"authority_ids"`
	} `json:"routes"`
}

type evidenceRecord struct {
	ID          string   `yaml:"id"`
	AtlasID     string   `yaml:"atlas_id"`
	ClaimIDs    []string `yaml:"claim_ids"`
	Environment struct {
		Profile        string `yaml:"profile"`
		ManifestDigest string `yaml:"manifest_digest"`
	} `yaml:"environment"`
	SourceDigest  string `yaml:"source_digest"`
	HarnessDigest string `yaml:"harness_digest"`
	Artifact      struct {
		URI       string `yaml:"uri"`
		Digest    string `yaml:"digest"`
		SizeBytes *int64 `yaml:"size_bytes"`
	} `yaml:"artifact"`
	Verdict string `yaml:"verdict"`
}

func main() {
	if err := validate("."); err != nil {
		fmt.Fprintf(os.Stderr, "エラー: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Overlay検証済み: Manifest、Digest、Claim/Evidence Graph、Skill、Legal構造")
}

func validate(root string) error {
	var atlas atlasManifest
	if err := readYAML(filepath.Join(root, "atlas.yaml"), &atlas); err != nil {
		return err
	}
	var sources sourceLock
	if err := readYAML(filepath.Join(root, "sources.lock.yaml"), &sources); err != nil {
		return err
	}
	var coverage coverageManifest
	if err := readYAML(filepath.Join(root, "coverage.yaml"), &coverage); err != nil {
		return err
	}
	var mastery masteryManifest
	if err := readYAML(filepath.Join(root, "mastery.yaml"), &mastery); err != nil {
		return err
	}
	if atlas.ID != sources.AtlasID || atlas.ID != coverage.AtlasID || atlas.ID != mastery.AtlasID {
		return errors.New("共通Manifestのatlas_idが一致しません")
	}
	if atlas.Coverage.Epoch != sources.Epoch || atlas.Coverage.Epoch != coverage.Epoch || atlas.Coverage.Epoch != mastery.Epoch {
		return errors.New("共通ManifestのCoverage Epochが一致しません")
	}
	lockDigest, err := digestFile(filepath.Join(root, "sources.lock.yaml"))
	if err != nil {
		return err
	}
	if coverage.AuthorityLockDigest != lockDigest {
		return fmt.Errorf("authority_lock_digestが不一致です: want %s got %s", lockDigest, coverage.AuthorityLockDigest)
	}

	sourceIDs := map[string]bool{}
	for _, source := range sources.Sources {
		if sourceIDs[source.ID] {
			return fmt.Errorf("Source IDが重複しています: %s", source.ID)
		}
		sourceIDs[source.ID] = true
		if source.ID == "local-runtime-inventory" {
			digest, err := digestFile(filepath.Join(root, "environments/local/runtime-inventory.json"))
			if err != nil {
				return err
			}
			if source.Digest != digest {
				return fmt.Errorf("Local Runtime Inventory Digestが不一致です: want %s got %s", digest, source.Digest)
			}
		}
	}

	setIDs := map[string]bool{}
	sequences := map[int]bool{}
	for _, set := range coverage.TargetSets {
		if setIDs[set.ID] {
			return fmt.Errorf("Target Set IDが重複しています: %s", set.ID)
		}
		if sequences[set.Sequence] {
			return fmt.Errorf("Target Set sequenceが重複しています: %d", set.Sequence)
		}
		setIDs[set.ID], sequences[set.Sequence] = true, true
	}
	for _, outcome := range mastery.Outcomes {
		for _, setID := range outcome.TargetSets {
			if !setIDs[setID] {
				return fmt.Errorf("Mastery Outcome %sが未定義Set %sを参照しています", outcome.ID, setID)
			}
		}
	}
	for _, surface := range mastery.Surfaces {
		for _, setID := range surface.TargetSets {
			if !setIDs[setID] {
				return fmt.Errorf("Mastery Surface %sが未定義Set %sを参照しています", surface.ID, setID)
			}
		}
	}

	var capabilities capabilitiesDocument
	if err := readJSON(filepath.Join(root, "atlas/capabilities/index.json"), &capabilities); err != nil {
		return err
	}
	var claims claimsDocument
	if err := readJSON(filepath.Join(root, "atlas/claims/index.json"), &claims); err != nil {
		return err
	}
	var proofs proofsDocument
	if err := readJSON(filepath.Join(root, "atlas/proof-obligations/index.json"), &proofs); err != nil {
		return err
	}
	var labs labsDocument
	if err := readJSON(filepath.Join(root, "labs/index.json"), &labs); err != nil {
		return err
	}
	capabilityIDs := collectIDs(capabilities.Capabilities, func(value struct {
		ID string `json:"id"`
	}) string {
		return value.ID
	})
	proofIDs := collectIDs(proofs.Proofs, func(value struct {
		ID string `json:"id"`
	}) string {
		return value.ID
	})
	labIDs := map[string]bool{}
	testIDs := map[string]bool{}
	for _, lab := range labs.Labs {
		labIDs[lab.ID] = true
		if _, err := os.Stat(filepath.Join(root, lab.Path)); err != nil {
			return fmt.Errorf("Lab Pathが存在しません: %s", lab.Path)
		}
	}
	for _, test := range labs.Tests {
		testIDs[test.ID] = true
		if _, err := os.Stat(filepath.Join(root, test.Path)); err != nil {
			return fmt.Errorf("Test Pathが存在しません: %s", test.Path)
		}
	}
	claimIDs := map[string]bool{}
	for _, claim := range claims.Claims {
		if claimIDs[claim.ID] {
			return fmt.Errorf("Claim IDが重複しています: %s", claim.ID)
		}
		claimIDs[claim.ID] = true
		if !capabilityIDs[claim.CapabilityID] || !proofIDs[claim.ProofObligationID] || !labIDs[claim.LabID] || !testIDs[claim.TestID] {
			return fmt.Errorf("Claim %sのGraph参照が未定義です", claim.ID)
		}
		if strings.TrimSpace(claim.Acceptance) == "" {
			return fmt.Errorf("Claim %sにAcceptanceがありません", claim.ID)
		}
		for _, authorityID := range claim.AuthorityIDs {
			if !sourceIDs[authorityID] {
				return fmt.Errorf("Claim %sが未定義Authority %sを参照しています", claim.ID, authorityID)
			}
		}
	}

	evidenceByID, err := readEvidence(root, atlas.ID, claimIDs, lockDigest)
	if err != nil {
		return err
	}
	targetIDs := map[string]bool{}
	targetStates := map[string]string{}
	openRequired := 0
	for _, target := range coverage.Targets {
		if targetIDs[target.ID] {
			return fmt.Errorf("Coverage Target IDが重複しています: %s", target.ID)
		}
		targetIDs[target.ID] = true
		targetStates[target.ID] = target.State
		if !setIDs[target.TargetSet] {
			return fmt.Errorf("Target %sが未定義Set %sを参照しています", target.ID, target.TargetSet)
		}
		for _, claimID := range target.ClaimIDs {
			if !claimIDs[claimID] {
				return fmt.Errorf("Target %sが未定義Claim %sを参照しています", target.ID, claimID)
			}
		}
		for _, evidenceID := range target.EvidenceIDs {
			evidence, ok := evidenceByID[evidenceID]
			if !ok {
				return fmt.Errorf("Target %sが未定義Evidence %sを参照しています", target.ID, evidenceID)
			}
			if target.State == "covered" && evidence.Verdict != "pass" {
				return fmt.Errorf("covered Target %sのEvidenceがpassではありません", target.ID)
			}
		}
		if target.Requirement == "required" && target.State != "covered" && target.State != "excluded" && target.State != "infeasible" {
			openRequired++
		}
	}
	var routes routesDocument
	if err := readJSON(filepath.Join(root, "evals/routes.json"), &routes); err != nil {
		return err
	}
	for _, route := range routes.Routes {
		if !capabilityIDs[route.CapabilityID] {
			return fmt.Errorf("Skill Routeが未定義Capability %sを参照しています", route.CapabilityID)
		}
		state, ok := targetStates[route.TargetID]
		if !ok {
			return fmt.Errorf("Skill Routeが未定義Target %sを参照しています", route.TargetID)
		}
		if route.State != state {
			return fmt.Errorf("Skill Route %sのStateがCoverageと不一致です: %s != %s", route.CapabilityID, route.State, state)
		}
		for _, authorityID := range route.AuthorityIDs {
			if !sourceIDs[authorityID] {
				return fmt.Errorf("Skill Route %sが未定義Authority %sを参照しています", route.CapabilityID, authorityID)
			}
		}
	}
	if atlas.Status == "complete" {
		if openRequired > 0 {
			return fmt.Errorf("completeですが未閉包の必須Targetが%d件あります", openRequired)
		}
		if _, err := os.Stat(filepath.Join(root, atlas.Completion.Certificate)); err != nil {
			return errors.New("completeですがCompletion Certificateがありません")
		}
	}

	for _, profile := range atlas.Completion.RequiredProfiles {
		path := filepath.Join(root, "environments", profile)
		if _, err := os.Stat(path); err != nil {
			return fmt.Errorf("Required Profileがありません: %s", profile)
		}
	}
	paths := []string{atlas.Skills.Router.Path, atlas.Skills.Evals, "LICENSE", "NOTICE", "SECURITY.md", "CONTRIBUTING.md", "third_party/manifest.yaml", "sbom.spdx.json"}
	for _, path := range paths {
		if _, err := os.Stat(filepath.Join(root, path)); err != nil {
			return fmt.Errorf("必須Pathがありません: %s", path)
		}
	}
	fmt.Printf("Completion状況: status=%s open_required_targets=%d evidence=%d\n", atlas.Status, openRequired, len(evidenceByID))
	return nil
}

func readEvidence(root, atlasID string, claimIDs map[string]bool, sourceDigest string) (map[string]evidenceRecord, error) {
	result := map[string]evidenceRecord{}
	err := filepath.WalkDir(filepath.Join(root, "evidence"), func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() || !strings.Contains(entry.Name(), ".evidence.") {
			return nil
		}
		var evidence evidenceRecord
		if err := readYAML(path, &evidence); err != nil {
			return err
		}
		if evidence.AtlasID != atlasID {
			return fmt.Errorf("Evidence %sのatlas_idが不一致です", evidence.ID)
		}
		if result[evidence.ID].ID != "" {
			return fmt.Errorf("Evidence IDが重複しています: %s", evidence.ID)
		}
		for _, claimID := range evidence.ClaimIDs {
			if !claimIDs[claimID] {
				return fmt.Errorf("Evidence %sが未定義Claim %sを参照しています", evidence.ID, claimID)
			}
		}
		if evidence.SourceDigest != sourceDigest {
			return fmt.Errorf("Evidence %sのSource DigestがAuthority Lockと不一致です", evidence.ID)
		}
		if evidence.HarnessDigest == "" {
			return fmt.Errorf("Evidence %sにHarness Digestがありません", evidence.ID)
		}
		environmentPath := filepath.Join(root, "environments", evidence.Environment.Profile, "manifest.yaml")
		if evidence.Environment.Profile == "local" {
			environmentPath = filepath.Join(root, "environments/local/runtime-inventory.json")
		}
		environmentDigest, err := digestFile(environmentPath)
		if err != nil {
			return fmt.Errorf("Evidence %s Environment: %w", evidence.ID, err)
		}
		if environmentDigest != evidence.Environment.ManifestDigest {
			return fmt.Errorf("Evidence %s Environment Digestが不一致です", evidence.ID)
		}
		artifactPath := filepath.Join(root, evidence.Artifact.URI)
		digest, err := digestFile(artifactPath)
		if err != nil {
			return fmt.Errorf("Evidence %s Artifact: %w", evidence.ID, err)
		}
		if digest != evidence.Artifact.Digest {
			return fmt.Errorf("Evidence %s Artifact Digestが不一致です", evidence.ID)
		}
		if evidence.Artifact.SizeBytes != nil {
			info, err := os.Stat(artifactPath)
			if err != nil {
				return err
			}
			if info.Size() != *evidence.Artifact.SizeBytes {
				return fmt.Errorf("Evidence %s Artifact Sizeが不一致です", evidence.ID)
			}
		}
		result[evidence.ID] = evidence
		return nil
	})
	return result, err
}

func collectIDs[T any](values []T, id func(T) string) map[string]bool {
	result := map[string]bool{}
	for _, value := range values {
		result[id(value)] = true
	}
	return result
}

func readYAML(path string, target any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("%sを読めません: %w", path, err)
	}
	if err := yaml.Unmarshal(data, target); err != nil {
		return fmt.Errorf("%sは有効なYAMLではありません: %w", path, err)
	}
	return nil
}

func readJSON(path string, target any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("%sを読めません: %w", path, err)
	}
	if err := json.Unmarshal(data, target); err != nil {
		return fmt.Errorf("%sは有効なJSONではありません: %w", path, err)
	}
	return nil
}

func digestFile(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func sortedKeys(values map[string]bool) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
