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
src/girdle/align.py | python | 309L | AlignPlan, _python_formatter, _js_formatter, _js_formatter_skip_note, _prettier_settings, _rust_formatter, detect_formatters, _parse_editorconfig_sections, _render_section, plan_editorconfig, plan_gitattributes, plan_gitignore, build_align_plans, apply_plan
src/girdle/cli.py | python | 226L | main, scan, dashboard, index, align, _print_human, _print_hygiene, _print_platform
src/girdle/coverage_parse.py | python | 46L | _first_match, parse_percentage
src/girdle/dashboard.py | python | 25L | render_dashboard
src/girdle/detectors/__init__.py | python | 4L | 
src/girdle/detectors/_util.py | python | 32L | read_json, read_toml, read_text
src/girdle/detectors/base.py | python | 45L | Fingerprint, Detector
src/girdle/detectors/dotnet.py | python | 169L | DotNetDetector
src/girdle/detectors/go_mod.py | python | 115L | GoModDetector
src/girdle/detectors/java_gradle.py | python | 132L | JavaGradleDetector
src/girdle/detectors/java_maven.py | python | 128L | JavaMavenDetector
src/girdle/detectors/js_bun.py | python | 52L | JsBunDetector
src/girdle/detectors/js_common.py | python | 146L | detect_variants, scan_tests, scan_lint, scan_coverage, scan_ci, is_lockfile_gitignored, run_commands
src/girdle/detectors/js_npm.py | python | 58L | JsNpmDetector
src/girdle/detectors/js_pnpm.py | python | 51L | JsPnpmDetector
src/girdle/detectors/js_yarn.py | python | 52L | JsYarnDetector
src/girdle/detectors/python_common.py | python | 123L | scan_tests, scan_lint, scan_coverage, coverage_command, scan_ci, is_lockfile_gitignored, lint_command, test_command
src/girdle/detectors/python_conda.py | python | 66L | PythonCondaDetector
src/girdle/detectors/python_pip.py | python | 120L | PythonPipDetector
src/girdle/detectors/python_pipenv.py | python | 51L | PythonPipenvDetector
src/girdle/detectors/python_uv.py | python | 48L | PythonUvDetector
src/girdle/detectors/registry.py | python | 34L | 
src/girdle/detectors/rust.py | python | 143L | RustDetector
src/girdle/fsutil.py | python | 35L | walk_excluding, rglob_excluding
src/girdle/hygiene.py | python | 172L | _read_text, HygieneResult, _first_existing, check_editorconfig, check_gitattributes, check_gitignore, check_codeowners, check_readme, check_contributing, build_hygiene
src/girdle/indexer.py | python | 355L | _parser, _text, _name_of, _defs_python, _defs_js_ts, _defs_go, _defs_rust, _defs_java, _defs_csharp_from, IndexEntry, RepoIndex, _iter_source_files, _extract_symbols, build_index, _estimate_tokens, _render_entry, render_manifest, render_block, inject_into, is_stale
src/girdle/platform.py | python | 168L | PlatformResult, compute_recommendations, _run, extract_protection_facts, check_platform
src/girdle/runner.py | python | 58L | RunOutcome, run_check
src/girdle/scan.py | python | 101L | run_scan, _verify
src/girdle/schema.py | python | 120L | EcosystemResult, ScanResult
src/girdle/tiers.py | python | 46L | Tier, CategoryResult
tests/test_align.py | python | 164L | test_editorconfig_derives_from_black, test_editorconfig_derives_from_ruff_format, test_editorconfig_no_formatter_no_plan, test_editorconfig_appends_without_touching_existing_content, test_editorconfig_skips_glob_already_present, test_editorconfig_js_prettier_json, test_editorconfig_js_unparseable_config_is_skipped, test_editorconfig_rust_from_rustfmt_toml, test_gitattributes_no_eol_signal_no_plan, test_gitattributes_propagates_prettier_eol, test_gitattributes_conflict_when_formatters_disagree, test_gitattributes_existing_text_auto_left_alone, test_gitattributes_appends_to_existing_file, test_gitignore_adds_missing_patterns, test_gitignore_already_covered_no_plan, test_gitignore_multi_language_union, test_apply_plan_writes_file, test_apply_plan_noop_when_no_content, test_build_align_plans_returns_three_plans
tests/test_coverage.py | python | 171L | test_python_coverage_absent_by_default, test_python_coverage_configured_via_coveragerc, test_python_coverage_configured_via_pyproject, test_python_coverage_run_command_declared, test_js_npm_coverage_via_dependency, test_js_npm_coverage_absent, test_js_npm_coverage_run_command_only_if_script_declared, test_go_coverage_absent_without_ci_evidence, test_go_coverage_configured_via_ci, test_go_coverage_run_command_always_declared, test_rust_coverage_absent, test_rust_coverage_configured_via_tarpaulin_toml, test_java_maven_coverage_via_jacoco, test_java_gradle_coverage_via_jacoco, test_dotnet_coverage_via_coverlet, test_dotnet_coverage_absent
tests/test_coverage_parse.py | python | 48L | test_parses_python_total_line, test_parses_go_coverage_line, test_parses_rust_tarpaulin_line, test_parses_js_all_files_row, test_unknown_language_returns_none, test_unparseable_output_returns_none, test_empty_output_returns_none
tests/test_dotnet.py | python | 62L | test_detect_none_without_project_files, test_pinned_packagereference_configured, test_floating_version_without_lockfile_is_absent, test_packages_lock_json_configured_even_with_ranges, test_test_sdk_reference_detected
tests/test_go_mod.py | python | 28L | test_detect_none_without_go_mod, test_missing_go_sum_is_absent, test_test_files_detected
tests/test_hygiene.py | python | 101L | test_all_absent_on_empty_repo, test_editorconfig_present, test_gitattributes_present, test_gitignore_missing_is_absent, test_gitignore_present_but_missing_stack_patterns, test_gitignore_covers_stack_is_configured, test_gitignore_multi_language_checks_all_stacks, test_codeowners_found_in_github_dir, test_readme_empty_stub_is_absent, test_readme_with_real_content_is_configured, test_contributing_absent, test_contributing_present_in_docs, test_to_dict_shape
tests/test_indexer.py | python | 97L | test_python_symbols_extracted, test_excluded_dirs_are_skipped, test_go_and_rust_symbols, test_budget_truncates_and_flags, test_manifest_render_is_deterministic, test_inject_creates_markers_in_empty_file, test_inject_replaces_existing_block, test_is_stale_true_when_missing, test_is_stale_false_when_matching, test_is_stale_true_when_drifted
tests/test_indexer_treesitter.py | python | 86L | _symbols_for, test_python_decorated_and_multiline_signature, test_python_async_def, test_js_export_const_arrow, test_js_non_function_const_not_captured, test_ts_interface_and_type_alias, test_tsx_extension_parses, test_java_multiple_top_level_types, test_csharp_namespace_unwrapped, test_rust_impl_for_trait, test_go_multiple_types_in_one_type_declaration_group
tests/test_java.py | python | 77L | test_maven_detect_none_without_pom, test_maven_pinned_versions_configured, test_maven_version_range_is_absent, test_gradle_detect_none_without_build_file, test_gradle_lockfile_configured, test_gradle_no_lock_mechanism_is_absent, test_gradle_kotlin_dsl_variant
tests/test_js_npm.py | python | 46L | test_detect_none_without_package_json, test_detect_yields_to_yarn, test_full_configured_repo, test_gitignored_lockfile_scores_absent
tests/test_js_variants.py | python | 57L | test_npm_yields_to_yarn, test_npm_yields_to_pnpm, test_npm_yields_to_bun, test_yarn_gitignored_lockfile_is_absent, test_bun_binary_lockfile_presence_only, test_pnpm_workspace_variant_detected
tests/test_platform.py | python | 160L | test_extract_protection_facts_full, test_extract_protection_facts_empty_response, test_check_platform_gh_not_found, test_check_platform_not_authenticated, test_check_platform_no_remote, test_check_platform_unprotected_branch, test_check_platform_protected_branch, test_to_dict_unavailable, test_compute_recommendations_unavailable_is_empty, test_compute_recommendations_unprotected, test_compute_recommendations_protected_but_weak, test_compute_recommendations_fully_hardened_is_empty, test_to_dict_available_and_protected
tests/test_python_pip.py | python | 53L | test_detect_none_without_markers, test_detect_poetry, test_pinned_requirements_configured, test_unpinned_requirements_absent, test_pep621_unpinned_gets_specific_reason, test_poetry_lock_gitignored
tests/test_python_variants.py | python | 70L | test_pip_yields_to_uv, test_pip_yields_to_pipenv, test_pip_yields_to_conda, test_uv_lock_configured, test_conda_env_without_lock_is_absent, test_conda_with_lock_is_configured, test_pipenv_without_lock_is_absent, test_pipenv_with_lock_is_configured
tests/test_recommendations.py | python | 87L | test_python_pip_recommendation_names_pip_compile, test_js_npm_recommendation_is_toolchain_specific, test_js_yarn_recommendation_names_yarn_not_npm, test_go_recommendation_names_go_mod_tidy, test_rust_bin_recommendation_names_cargo_build, test_dotnet_recommendation_mentions_lockfile_or_pinning, test_verified_category_has_no_recommendation
tests/test_runner.py | python | 33L | test_missing_binary_is_not_ran, test_successful_command, test_failing_command, test_timeout
tests/test_rust.py | python | 47L | test_detect_none_without_cargo_toml, test_bin_crate_missing_lock_is_absent_and_applicable, test_lib_crate_missing_lock_is_excluded_from_applicable, test_lib_crate_with_committed_lock_is_applicable_and_configured, test_inline_test_detected
tests/test_scan_verify.py | python | 61L | _FakeDetector, _fp, test_verify_upgrades_to_verified_on_success, test_verify_keeps_configured_on_failure, test_verify_skips_absent_categories, test_verify_noop_without_run_commands, test_verify_static_mode_adds_generic_hint_not_execution
tests/test_scoring.py | python | 33L | _eco, test_category_min_is_gated_by_weakest, test_inapplicable_categories_excluded_from_min, test_scan_result_overall_min_is_weakest_ecosystem
tests/test_vendor_exclusion.py | python | 50L | test_python_ignores_test_files_inside_venv, test_python_still_finds_real_top_level_tests, test_go_ignores_test_files_inside_vendor, test_rust_ignores_rs_files_inside_target
```
<!-- girdle:index:end -->
