// SPDX-License-Identifier: Apache-2.0
package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDigestFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fixture")
	if err := os.WriteFile(path, []byte("atlas\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	got, err := digestFile(path)
	if err != nil {
		t.Fatal(err)
	}
	const want = "sha256:e7764dedc66e4378732a0f96ef9df5235dd40c8c2348dc07acb92008564c3761"
	if got != want {
		t.Fatalf("digest: got %s want %s", got, want)
	}
}
