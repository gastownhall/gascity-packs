GC ?= gc
PYTHON ?= python3
REGISTRY ?= registry.toml
REGISTRY_REF ?= main
REGISTRY_COMMIT ?= HEAD
REGISTRY_SOURCE_BASE ?= https://github.com/gastownhall/gascity-packs/tree/main

PACK_PATH ?= $(PACK)
SOURCE ?= .
CATALOG_SOURCE ?= $(REGISTRY_SOURCE_BASE)/$(PACK_PATH)

STAMP_PACK_DESCRIPTION :=
ifneq ($(strip $(PACK_DESCRIPTION)),)
STAMP_PACK_DESCRIPTION := --pack-description "$(PACK_DESCRIPTION)"
endif

# The pytest suites CI runs (.github/workflows/ci.yml). `test` uses the
# interpreter's own pytest when pytest, PyYAML and jsonschema import, else
# `uv run --with ...` (a Homebrew python3 has no pytest). GC_TEMPLATE is unset
# because a gc worker session exports it and one claim-command test would
# otherwise inherit it as its expected route.
PYTEST_DIRS ?= tests contributing/tests gascity/tests discord/tests github/tests slack-full/tests slack-channel/tests pr-pipeline/tests profiler/tests
PYTEST_ARGS ?= -q
PYTEST_RUNNER = if $(PYTHON) -c 'import pytest, yaml, jsonschema' >/dev/null 2>&1; then echo '$(PYTHON) -m pytest'; else echo 'uv run --with pytest --with pyyaml --with jsonschema $(PYTHON) -m pytest'; fi

.PHONY: test test-gascity registry-help registry-format-validate registry-validate registry-validate-all registry-publish registry-withdraw

test:
	env -u GC_TEMPLATE $$($(PYTEST_RUNNER)) $(PYTEST_DIRS) $(PYTEST_ARGS)

test-gascity:
	env -u GC_TEMPLATE $$($(PYTEST_RUNNER)) tests gascity/tests $(PYTEST_ARGS)

registry-help:
	@printf '%s\n' 'Registry targets:'
	@printf '%s\n' '  make registry-format-validate'
	@printf '%s\n' '  make registry-validate GC=/path/to/gc'
	@printf '%s\n' '  make registry-validate-all GC=/path/to/gc'
	@printf '%s\n' '  make registry-publish GC=/path/to/gc PACK=<name> VERSION=<semver> DESCRIPTION="..." [PACK_PATH=<path>] [PACK_DESCRIPTION="..."]'
	@printf '%s\n' '  make registry-withdraw PACK=<name> VERSION=<semver> REASON="..."'

registry-format-validate:
	$(PYTHON) validate_registry.py $(REGISTRY)

registry-validate:
	$(GC) pack release validate $(REGISTRY)

registry-validate-all:
	$(GC) pack release validate $(REGISTRY) --include-withdrawn

registry-publish:
	@test -n "$(PACK)" || { echo "PACK is required"; exit 2; }
	@test -n "$(PACK_PATH)" || { echo "PACK_PATH is required"; exit 2; }
	@test -n "$(VERSION)" || { echo "VERSION is required"; exit 2; }
	@test -n "$(DESCRIPTION)" || { echo "DESCRIPTION is required"; exit 2; }
	$(GC) pack release stamp $(REGISTRY) "$(PACK)" \
		--version "$(VERSION)" \
		--ref "$(REGISTRY_REF)" \
		--commit "$(REGISTRY_COMMIT)" \
		--description "$(DESCRIPTION)" \
		--source "$(SOURCE)" \
		--path "$(PACK_PATH)" \
		$(STAMP_PACK_DESCRIPTION)
	$(PYTHON) scripts/registry_release.py set-source \
		--registry "$(REGISTRY)" \
		--pack "$(PACK)" \
		--source "$(CATALOG_SOURCE)"

registry-withdraw:
	@test -n "$(PACK)" || { echo "PACK is required"; exit 2; }
	@test -n "$(VERSION)" || { echo "VERSION is required"; exit 2; }
	@test -n "$(REASON)" || { echo "REASON is required"; exit 2; }
	$(PYTHON) scripts/registry_release.py withdraw \
		--registry "$(REGISTRY)" \
		--pack "$(PACK)" \
		--version "$(VERSION)" \
		--reason "$(REASON)"
