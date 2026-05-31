package cmd

import (
	"os"
	"path/filepath"
	"testing"
)

// newTestCity creates a minimal city directory (with city.toml marker)
// rooted at t.TempDir() and returns its absolute path. Shared across
// every cmd/<verb>_test.go file in this package.
func newTestCity(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	cityRoot := filepath.Join(dir, "testcity")
	if err := os.MkdirAll(cityRoot, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(cityRoot, "city.toml"),
		[]byte("[workspace]\nname = \"test\"\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	return cityRoot
}

func TestResolveCityPathFromCwd(t *testing.T) {
	t.Setenv(cityPathEnv, "")
	cityRoot := newTestCity(t)
	t.Chdir(cityRoot)

	got, err := ResolveCityPath()
	if err != nil {
		t.Fatalf("ResolveCityPath: %v", err)
	}
	wantAbs, _ := filepath.Abs(cityRoot)
	gotAbs, _ := filepath.Abs(got)
	if gotAbs != wantAbs {
		t.Errorf("ResolveCityPath() = %q, want %q", gotAbs, wantAbs)
	}
}

func TestResolveCityPathFromNestedSubdir(t *testing.T) {
	t.Setenv(cityPathEnv, "")
	cityRoot := newTestCity(t)
	nested := filepath.Join(cityRoot, "deep", "nested", "subdir")
	if err := os.MkdirAll(nested, 0o755); err != nil {
		t.Fatal(err)
	}
	t.Chdir(nested)

	got, err := ResolveCityPath()
	if err != nil {
		t.Fatalf("ResolveCityPath from nested cwd: %v", err)
	}
	wantAbs, _ := filepath.Abs(cityRoot)
	gotAbs, _ := filepath.Abs(got)
	if gotAbs != wantAbs {
		t.Errorf("ResolveCityPath() from nested = %q, want %q", gotAbs, wantAbs)
	}
}

func TestResolveCityPathHonorsEnvOverride(t *testing.T) {
	envCity := newTestCity(t)
	cwdCity := newTestCity(t) // distinct city the cwd resolves to
	t.Chdir(cwdCity)
	t.Setenv(cityPathEnv, envCity)

	got, err := ResolveCityPath()
	if err != nil {
		t.Fatalf("ResolveCityPath with env override: %v", err)
	}
	wantAbs, _ := filepath.Abs(envCity)
	gotAbs, _ := filepath.Abs(got)
	if gotAbs != wantAbs {
		t.Errorf("env override: ResolveCityPath() = %q, want %q (env override beats cwd)", gotAbs, wantAbs)
	}
}

func TestResolveCityPathRejectsBadEnv(t *testing.T) {
	notACity := t.TempDir() // no city.toml, no .gc/
	t.Setenv(cityPathEnv, notACity)

	_, err := ResolveCityPath()
	if err == nil {
		t.Fatal("ResolveCityPath with non-city env: want error, got nil")
	}
}

func TestResolveCityPathFailsOutsideAnyCity(t *testing.T) {
	stranger := t.TempDir() // no markers anywhere up the tree
	t.Chdir(stranger)
	t.Setenv(cityPathEnv, "")

	_, err := ResolveCityPath()
	if err == nil {
		t.Fatal("ResolveCityPath outside any city: want error, got nil")
	}
}

func TestCityHasMarkerRecognizesGCRuntimeRoot(t *testing.T) {
	dir := t.TempDir()
	if err := os.Mkdir(filepath.Join(dir, ".gc"), 0o755); err != nil {
		t.Fatal(err)
	}
	if !cityHasMarker(dir) {
		t.Errorf("cityHasMarker() = false on dir with .gc/, want true")
	}
}
