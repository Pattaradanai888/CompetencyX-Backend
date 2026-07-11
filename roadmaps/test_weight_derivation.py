"""Guards for the mapping -> generated-weights derivation pipeline."""

from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS
from roadmaps.seeds import load_curated_catalog
from roadmaps.weight_derivation import (
    GENERATED_MODULE_PATH,
    derive_role_profile_weights,
    load_relevance_mapping,
    render_from_mapping,
    validate_relevance_mapping,
)


def test_generated_module_is_not_stale():
    """The committed module must match a fresh render (same as --check)."""
    assert GENERATED_MODULE_PATH.read_text(encoding='utf-8') == render_from_mapping()


def test_runtime_weights_equal_mapping_derivation():
    mapping = load_relevance_mapping()
    assert derive_role_profile_weights(mapping) == ROLE_PROFILE_WEIGHTS


def test_all_weights_are_bounded_and_positive():
    for role_slug, profile in ROLE_PROFILE_WEIGHTS.items():
        for dimension_key, weight in profile.items():
            assert 0.0 < weight <= 1.0, f'{role_slug}.{dimension_key} = {weight}'


def test_relevance_mapping_passes_validation():
    roles_data, _topics, _questions = load_curated_catalog()
    errors = validate_relevance_mapping(load_relevance_mapping(), roles_yaml_entries=roles_data['roles'])
    assert errors == []


def test_validation_reports_top_ka_divergence():
    mapping = load_relevance_mapping()
    roles_data, _topics, _questions = load_curated_catalog()
    # Break one declared top_ka_codes entry and expect a named error.
    broken_roles = [dict(entry) for entry in roles_data['roles']]
    broken_roles[0] = {**broken_roles[0], 'top_ka_codes': ['KA1', 'KA17', 'KA18']}
    errors = validate_relevance_mapping(mapping, roles_yaml_entries=broken_roles)
    assert any(broken_roles[0]['slug'] in error and 'top_ka_codes' in error for error in errors)


def test_validation_rejects_unknown_source_kind():
    mapping = load_relevance_mapping()
    role_slug = next(iter(mapping['roles']))
    dimension_key = next(iter(mapping['roles'][role_slug]['ka']))
    mapping['roles'][role_slug]['ka'][dimension_key]['sources'] = [{'wikipedia': {'page': 'x'}}]
    roles_data, _topics, _questions = load_curated_catalog()
    errors = validate_relevance_mapping(mapping, roles_yaml_entries=roles_data['roles'])
    assert any('unknown source kind' in error for error in errors)
