package main

import (
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadConfigFromEnv(t *testing.T) {
	base := map[string]string{
		"SLACK_BOT_TOKEN":      "xoxb-1",
		"SLACK_SIGNING_SECRET": "secret",
		"SLACK_WORKSPACE_ID":   "T123",
		"GC_CITY_NAME":         "mycity",
		"GC_CITY_PATH":         "/srv/mycity",
	}
	clone := func(extra map[string]string) func(string) string {
		m := map[string]string{}
		for k, v := range base {
			m[k] = v
		}
		for k, v := range extra {
			if v == "" {
				delete(m, k)
			} else {
				m[k] = v
			}
		}
		return func(k string) string { return m[k] }
	}

	t.Run("defaults", func(t *testing.T) {
		cfg, err := loadConfigFromEnv(clone(nil))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.publicListen != defaultPublicListen {
			t.Errorf("publicListen = %q, want default", cfg.publicListen)
		}
		if cfg.inboundTarget != defaultInboundTarget {
			t.Errorf("inboundTarget = %q, want %q", cfg.inboundTarget, defaultInboundTarget)
		}
		if !cfg.registerOnStart {
			t.Error("registerOnStart should default true")
		}
		want := filepath.Join("/srv/mycity", ".gc", "slack-channel")
		if cfg.registryDir != want {
			t.Errorf("registryDir = %q, want %q", cfg.registryDir, want)
		}
		if cfg.channelMappingsPath() != filepath.Join(want, "channel_mappings.json") {
			t.Errorf("channelMappingsPath = %q", cfg.channelMappingsPath())
		}
		if cfg.identitiesPath() != filepath.Join(want, "identities.json") {
			t.Errorf("identitiesPath = %q", cfg.identitiesPath())
		}
		if cfg.handleAliasesPath() != filepath.Join(want, "handle_aliases.json") {
			t.Errorf("handleAliasesPath = %q", cfg.handleAliasesPath())
		}
	})

	t.Run("registry dir override wins over city path", func(t *testing.T) {
		cfg, err := loadConfigFromEnv(clone(map[string]string{"SLACK_CHANNEL_REGISTRY_DIR": "/var/state/sc"}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.registryDir != "/var/state/sc" {
			t.Errorf("registryDir = %q, want override", cfg.registryDir)
		}
	})

	t.Run("registry dir from override without city path", func(t *testing.T) {
		cfg, err := loadConfigFromEnv(clone(map[string]string{
			"GC_CITY_PATH":               "",
			"SLACK_CHANNEL_REGISTRY_DIR": "/var/state/sc",
		}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.registryDir != "/var/state/sc" {
			t.Errorf("registryDir = %q", cfg.registryDir)
		}
	})

	t.Run("missing registry dir errors", func(t *testing.T) {
		_, err := loadConfigFromEnv(clone(map[string]string{"GC_CITY_PATH": ""}))
		if err == nil || !strings.Contains(err.Error(), "registry directory") {
			t.Fatalf("expected registry-dir error, got %v", err)
		}
	})

	t.Run("missing required", func(t *testing.T) {
		_, err := loadConfigFromEnv(clone(map[string]string{"GC_CITY_NAME": ""}))
		if err == nil || !strings.Contains(err.Error(), "GC_CITY_NAME") {
			t.Fatalf("expected missing GC_CITY_NAME error, got %v", err)
		}
	})

	t.Run("city name with slash rejected", func(t *testing.T) {
		_, err := loadConfigFromEnv(clone(map[string]string{"GC_CITY_NAME": "a/b"}))
		if err == nil || !strings.Contains(err.Error(), "must not contain") {
			t.Fatalf("expected city-name rejection, got %v", err)
		}
	})

	t.Run("proxy_process requires url prefix", func(t *testing.T) {
		_, err := loadConfigFromEnv(clone(map[string]string{"GC_SERVICE_SOCKET": "/tmp/s.sock"}))
		if err == nil || !strings.Contains(err.Error(), "GC_SERVICE_URL_PREFIX") {
			t.Fatalf("expected url-prefix error, got %v", err)
		}
	})

	t.Run("proxy_process callback url", func(t *testing.T) {
		cfg, err := loadConfigFromEnv(clone(map[string]string{
			"GC_SERVICE_SOCKET":     "/tmp/s.sock",
			"GC_SERVICE_URL_PREFIX": "/v0/city/mycity/svc/slack-channel/",
			"GC_API_BASE_URL":       "http://127.0.0.1:8372",
		}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		want := "http://127.0.0.1:8372/v0/city/mycity/svc/slack-channel"
		if cfg.internalCallbackURL != want {
			t.Errorf("internalCallbackURL = %q, want %q", cfg.internalCallbackURL, want)
		}
	})

	t.Run("slack api base trimmed", func(t *testing.T) {
		cfg, err := loadConfigFromEnv(clone(map[string]string{"SLACK_API_BASE": "https://relay.example/api/"}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.slackAPIBase != "https://relay.example/api" {
			t.Errorf("slackAPIBase = %q, want trimmed", cfg.slackAPIBase)
		}
	})
}
