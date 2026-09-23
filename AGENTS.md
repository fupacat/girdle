# girdle

Agent-readiness scanner. `src/girdle/schema.py` is the single source of truth
for scan output — CLI JSON and the HTML dashboard both render `ScanResult`,
never a second representation. Keep it that way.

New ecosystem support = new file in `src/girdle/detectors/` implementing the
`Detector` protocol (`detectors/base.py`), registered in `detectors/registry.py`.
Design rationale and the full detection matrix: see the vault note
`Agent-Ready Repository Design` (not duplicated here — read it before adding
scoring behavior, not this file).

Run checks: `pytest` / `ruff check .`.

<!-- girdle:index:start -->
```
src/girdle/__init__.py | python | 2L | 
src/girdle/cli.py | python | 135L | main, scan, dashboard, index, _print_human
src/girdle/dashboard.py | python | 25L | render_dashboard
src/girdle/detectors/__init__.py | python | 4L | 
src/girdle/detectors/_util.py | python | 32L | read_json, read_toml, read_text
src/girdle/detectors/base.py | python | 45L | Fingerprint, Detector
src/girdle/detectors/dotnet.py | python | 119L | DotNetDetector
src/girdle/detectors/go_mod.py | python | 78L | GoModDetector
src/girdle/detectors/java_gradle.py | python | 100L | JavaGradleDetector
src/girdle/detectors/java_maven.py | python | 98L | JavaMavenDetector
src/girdle/detectors/js_bun.py | python | 48L | JsBunDetector
src/girdle/detectors/js_common.py | python | 93L | detect_variants, scan_tests, scan_lint, scan_ci, is_lockfile_gitignored, run_commands
src/girdle/detectors/js_npm.py | python | 53L | JsNpmDetector
src/girdle/detectors/js_pnpm.py | python | 47L | JsPnpmDetector
src/girdle/detectors/js_yarn.py | python | 48L | JsYarnDetector
src/girdle/detectors/python_common.py | python | 83L | scan_tests, scan_lint, scan_ci, is_lockfile_gitignored, lint_command, test_command
src/girdle/detectors/python_conda.py | python | 58L | PythonCondaDetector
src/girdle/detectors/python_pip.py | python | 95L | PythonPipDetector
src/girdle/detectors/python_pipenv.py | python | 43L | PythonPipenvDetector
src/girdle/detectors/python_uv.py | python | 43L | PythonUvDetector
src/girdle/detectors/registry.py | python | 34L | 
src/girdle/detectors/rust.py | python | 102L | RustDetector
src/girdle/indexer.py | python | 254L | IndexEntry, RepoIndex, _iter_source_files, _walk, _extract_symbols, build_index, _estimate_tokens, _render_entry, render_manifest, render_block, inject_into, is_stale
src/girdle/runner.py | python | 53L | RunOutcome, run_check
src/girdle/scan.py | python | 73L | run_scan, _verify
src/girdle/schema.py | python | 145L | Tier, CategoryResult, EcosystemResult, ScanResult
tests/test_dotnet.py | python | 62L | test_detect_none_without_project_files, test_pinned_packagereference_configured, test_floating_version_without_lockfile_is_absent, test_packages_lock_json_configured_even_with_ranges, test_test_sdk_reference_detected
tests/test_go_mod.py | python | 28L | test_detect_none_without_go_mod, test_missing_go_sum_is_absent, test_test_files_detected
tests/test_indexer.py | python | 97L | test_python_symbols_extracted, test_excluded_dirs_are_skipped, test_go_and_rust_symbols, test_budget_truncates_and_flags, test_manifest_render_is_deterministic, test_inject_creates_markers_in_empty_file, test_inject_replaces_existing_block, test_is_stale_true_when_missing, test_is_stale_false_when_matching, test_is_stale_true_when_drifted
tests/test_java.py | python | 77L | test_maven_detect_none_without_pom, test_maven_pinned_versions_configured, test_maven_version_range_is_absent, test_gradle_detect_none_without_build_file, test_gradle_lockfile_configured, test_gradle_no_lock_mechanism_is_absent, test_gradle_kotlin_dsl_variant
tests/test_js_npm.py | python | 46L | test_detect_none_without_package_json, test_detect_yields_to_yarn, test_full_configured_repo, test_gitignored_lockfile_scores_absent
tests/test_js_variants.py | python | 57L | test_npm_yields_to_yarn, test_npm_yields_to_pnpm, test_npm_yields_to_bun, test_yarn_gitignored_lockfile_is_absent, test_bun_binary_lockfile_presence_only, test_pnpm_workspace_variant_detected
tests/test_python_pip.py | python | 53L | test_detect_none_without_markers, test_detect_poetry, test_pinned_requirements_configured, test_unpinned_requirements_absent, test_pep621_unpinned_gets_specific_reason, test_poetry_lock_gitignored
tests/test_python_variants.py | python | 70L | test_pip_yields_to_uv, test_pip_yields_to_pipenv, test_pip_yields_to_conda, test_uv_lock_configured, test_conda_env_without_lock_is_absent, test_conda_with_lock_is_configured, test_pipenv_without_lock_is_absent, test_pipenv_with_lock_is_configured
tests/test_runner.py | python | 33L | test_missing_binary_is_not_ran, test_successful_command, test_failing_command, test_timeout
tests/test_rust.py | python | 47L | test_detect_none_without_cargo_toml, test_bin_crate_missing_lock_is_absent_and_applicable, test_lib_crate_missing_lock_is_excluded_from_applicable, test_lib_crate_with_committed_lock_is_applicable_and_configured, test_inline_test_detected
tests/test_scan_verify.py | python | 52L | _FakeDetector, _fp, test_verify_upgrades_to_verified_on_success, test_verify_keeps_configured_on_failure, test_verify_skips_absent_categories, test_verify_noop_without_run_commands
tests/test_scoring.py | python | 33L | _eco, test_category_min_is_gated_by_weakest, test_inapplicable_categories_excluded_from_min, test_scan_result_overall_min_is_weakest_ecosystem
```
<!-- girdle:index:end -->
