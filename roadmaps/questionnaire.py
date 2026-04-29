# --- SWEBOK 2024 Role-Discovery Dimensions ---
#
# Role discovery measures work preferences against SWEBOK V4 knowledge areas.
# The public flow still uses beginner-friendly Likert statements; internally,
# each answer adds evidence to KAs, role families, or specialization endpoints.

SWEBOK_SOURCE_VERSION = 'SWEBOK V4.0'

SWEBOK_KNOWLEDGE_AREAS = (
    ('requirements', 'KA1 Software Requirements'),
    ('architecture', 'KA2 Software Architecture'),
    ('design', 'KA3 Software Design'),
    ('construction', 'KA4 Software Construction'),
    ('testing', 'KA5 Software Testing'),
    ('operations', 'KA6 Software Engineering Operations'),
    ('maintenance', 'KA7 Software Maintenance'),
    ('configuration_management', 'KA8 Software Configuration Management'),
    ('management', 'KA9 Software Engineering Management'),
    ('process', 'KA10 Software Engineering Process'),
    ('models_methods', 'KA11 Software Engineering Models and Methods'),
    ('quality', 'KA12 Software Quality'),
    ('security', 'KA13 Software Security'),
    ('professional_practice', 'KA14 Software Engineering Professional Practice'),
    ('economics', 'KA15 Software Engineering Economics'),
    ('computing_ai', 'KA16 Computing Foundations'),
    ('math', 'KA17 Mathematical Foundations'),
    ('engineering', 'KA18 Engineering Foundations'),
)

ROLE_SPECIALIZATION_DIMENSIONS = (
    ('web_frontend', 'Web Frontend'),
    ('server_backend', 'Server Backend'),
    ('android_platform', 'Android Platform'),
    ('ios_platform', 'iOS Platform'),
    ('database_postgresql', 'PostgreSQL Database'),
    ('blockchain_platform', 'Blockchain Platform'),
    ('game_client', 'Game Client'),
    ('game_server', 'Game Server'),
    ('developer_community', 'Developer Community'),
    ('technical_documentation', 'Technical Documentation'),
    ('business_intelligence', 'Business Intelligence'),
    ('ml_platform', 'ML Platform'),
)

ROLE_FAMILY_DIMENSIONS = (
    ('people_product', 'People and Product'),
    ('application_build', 'Application Build'),
    ('backend_platform', 'Backend and Platform'),
    ('data_ai', 'Data and AI'),
    ('operations_security', 'Operations and Security'),
    ('leadership_process', 'Leadership and Process'),
    ('documentation_practice', 'Documentation and Practice'),
    ('game_family', 'Game Development'),
)

ROLE_DIMENSIONS = tuple(key for key, _label in (*SWEBOK_KNOWLEDGE_AREAS, *ROLE_FAMILY_DIMENSIONS, *ROLE_SPECIALIZATION_DIMENSIONS))
CORE_ROLE_DIMENSIONS = {key for key, _label in SWEBOK_KNOWLEDGE_AREAS}

ROLE_DIMENSION_LABELS = dict((*SWEBOK_KNOWLEDGE_AREAS, *ROLE_FAMILY_DIMENSIONS, *ROLE_SPECIALIZATION_DIMENSIONS))


def _profile(*entries: tuple[str, float]) -> dict[str, float]:
    return dict(entries)


# Role weights are grounded in the user-provided SWEBOK 2024 role definitions:
# top KAs receive stronger weights, task KAs and specialization endpoints add
# extra separation for roles that share the same broad KA footprint.
ROLE_PROFILE_WEIGHTS = {
    'frontend-developer': _profile(
        ('design', 1.0), ('construction', 1.0), ('quality', 1.0), ('requirements', 0.6), ('testing', 0.6),
        ('operations', 0.4), ('process', 0.4), ('computing_ai', 0.4), ('web_frontend', 1.0),
    ),
    'backend-developer': _profile(
        ('construction', 1.0), ('architecture', 1.0), ('operations', 1.0), ('design', 0.6), ('testing', 0.6),
        ('quality', 0.6), ('maintenance', 0.5), ('configuration_management', 0.5), ('server_backend', 1.0),
    ),
    'full-stack-developer': _profile(
        ('construction', 1.0), ('design', 1.0), ('operations', 1.0), ('requirements', 0.6), ('process', 0.6),
        ('testing', 0.6), ('quality', 0.6), ('maintenance', 0.5), ('configuration_management', 0.5),
        ('web_frontend', 0.7), ('server_backend', 0.7),
    ),
    'devops-engineer': _profile(
        ('operations', 1.0), ('configuration_management', 1.0), ('process', 1.0), ('management', 0.6),
        ('quality', 0.6), ('construction', 0.4), ('engineering', 0.4),
    ),
    'devsecops-engineer': _profile(
        ('security', 1.0), ('operations', 1.0), ('configuration_management', 1.0), ('quality', 0.7),
        ('requirements', 0.5), ('process', 0.6), ('engineering', 0.4),
    ),
    'data-analyst': _profile(
        ('computing_ai', 1.0), ('math', 1.0), ('economics', 1.0), ('requirements', 0.6), ('professional_practice', 0.6),
        ('quality', 0.5), ('business_intelligence', 0.6),
    ),
    'ai-engineer': _profile(
        ('computing_ai', 1.0), ('construction', 1.0), ('architecture', 1.0), ('design', 0.6), ('quality', 0.7),
        ('security', 0.5), ('operations', 0.6), ('configuration_management', 0.5), ('process', 0.5),
    ),
    'ai-data-scientist': _profile(
        ('computing_ai', 1.0), ('math', 1.0), ('models_methods', 1.0), ('quality', 0.7), ('professional_practice', 0.6),
        ('economics', 0.6), ('construction', 0.4), ('operations', 0.4), ('configuration_management', 0.4),
    ),
    'data-engineer': _profile(
        ('construction', 1.0), ('operations', 1.0), ('computing_ai', 1.0), ('architecture', 0.6), ('design', 0.6),
        ('testing', 0.5), ('quality', 0.7), ('configuration_management', 0.6),
    ),
    'android-developer': _profile(
        ('construction', 1.0), ('design', 1.0), ('testing', 1.0), ('requirements', 0.6), ('quality', 0.7),
        ('operations', 0.4), ('configuration_management', 0.4), ('computing_ai', 0.3), ('android_platform', 1.0),
    ),
    'machine-learning-engineer': _profile(
        ('computing_ai', 1.0), ('construction', 1.0), ('operations', 1.0), ('math', 0.8), ('testing', 0.6),
        ('quality', 0.7), ('configuration_management', 0.7), ('process', 0.5), ('ml_platform', 0.8),
    ),
    'postgresql-developer-dba': _profile(
        ('construction', 1.0), ('operations', 1.0), ('quality', 1.0), ('design', 0.6), ('configuration_management', 0.7),
        ('maintenance', 0.6), ('security', 0.6), ('professional_practice', 0.4), ('database_postgresql', 1.0),
    ),
    'ios-developer': _profile(
        ('construction', 1.0), ('design', 1.0), ('testing', 1.0), ('requirements', 0.6), ('process', 0.5),
        ('quality', 0.7), ('operations', 0.4), ('configuration_management', 0.4), ('ios_platform', 1.0),
    ),
    'blockchain-developer': _profile(
        ('construction', 1.0), ('security', 1.0), ('architecture', 1.0), ('testing', 0.7), ('quality', 0.6),
        ('economics', 0.7), ('operations', 0.5), ('configuration_management', 0.5), ('blockchain_platform', 1.0),
    ),
    'qa-engineer': _profile(
        ('testing', 1.0), ('quality', 1.0), ('process', 1.0), ('requirements', 0.6), ('operations', 0.4),
        ('maintenance', 0.5), ('models_methods', 0.4),
    ),
    'software-architect': _profile(
        ('architecture', 1.0), ('design', 1.0), ('quality', 1.0), ('security', 0.7), ('economics', 0.6),
        ('professional_practice', 0.6), ('operations', 0.5), ('process', 0.5), ('engineering', 0.6),
    ),
    'cyber-security-engineer-analyst': _profile(
        ('security', 1.0), ('operations', 1.0), ('quality', 1.0), ('maintenance', 0.6), ('requirements', 0.5),
        ('process', 0.5), ('engineering', 0.5),
    ),
    'ux-designer': _profile(
        ('requirements', 1.0), ('design', 1.0), ('quality', 1.0), ('professional_practice', 0.7), ('testing', 0.6),
        ('process', 0.5), ('economics', 0.3),
    ),
    'technical-writer': _profile(
        ('professional_practice', 1.0), ('requirements', 1.0), ('maintenance', 1.0), ('design', 0.5),
        ('configuration_management', 0.7), ('quality', 0.6), ('computing_ai', 0.4), ('technical_documentation', 1.0),
    ),
    'game-developer': _profile(
        ('construction', 1.0), ('design', 1.0), ('computing_ai', 1.0), ('quality', 0.7), ('testing', 0.6),
        ('operations', 0.4), ('process', 0.4), ('game_client', 1.0),
    ),
    'server-side-game-developer': _profile(
        ('construction', 1.0), ('operations', 1.0), ('architecture', 1.0), ('design', 0.6), ('quality', 0.7),
        ('security', 0.6), ('configuration_management', 0.5), ('process', 0.4), ('server_backend', 0.7), ('game_server', 1.0),
    ),
    'mlops-engineer': _profile(
        ('operations', 1.0), ('configuration_management', 1.0), ('computing_ai', 1.0), ('quality', 0.7), ('testing', 0.6),
        ('process', 0.6), ('security', 0.5), ('professional_practice', 0.4), ('ml_platform', 1.0),
    ),
    'product-manager': _profile(
        ('requirements', 1.0), ('economics', 1.0), ('management', 1.0), ('process', 0.6), ('professional_practice', 0.7),
        ('computing_ai', 0.5), ('quality', 0.5),
    ),
    'engineering-manager': _profile(
        ('management', 1.0), ('process', 1.0), ('professional_practice', 1.0), ('quality', 0.7), ('operations', 0.5),
        ('computing_ai', 0.4), ('engineering', 0.6),
    ),
    'developer-relations': _profile(
        ('professional_practice', 1.0), ('requirements', 1.0), ('construction', 1.0), ('quality', 0.6),
        ('operations', 0.4), ('computing_ai', 0.5), ('developer_community', 1.0), ('technical_documentation', 0.6),
    ),
    'bi-analyst': _profile(
        ('economics', 1.0), ('computing_ai', 1.0), ('math', 1.0), ('requirements', 0.6), ('quality', 0.6),
        ('testing', 0.4), ('business_intelligence', 1.0),
    ),
}

ROLE_FAMILY_PROFILE_WEIGHTS = {
    'frontend-developer': _profile(('application_build', 1.0)),
    'backend-developer': _profile(('backend_platform', 1.0)),
    'full-stack-developer': _profile(('application_build', 0.8), ('backend_platform', 0.8)),
    'devops-engineer': _profile(('operations_security', 1.0), ('backend_platform', 0.5)),
    'devsecops-engineer': _profile(('operations_security', 1.2), ('backend_platform', 0.4)),
    'data-analyst': _profile(('data_ai', 1.0), ('people_product', 0.4)),
    'ai-engineer': _profile(('data_ai', 1.0), ('backend_platform', 0.7)),
    'ai-data-scientist': _profile(('data_ai', 1.2)),
    'data-engineer': _profile(('data_ai', 0.9), ('backend_platform', 0.8)),
    'android-developer': _profile(('application_build', 1.0)),
    'machine-learning-engineer': _profile(('data_ai', 1.0), ('backend_platform', 0.5)),
    'postgresql-developer-dba': _profile(('backend_platform', 1.0), ('operations_security', 0.5)),
    'ios-developer': _profile(('application_build', 1.0)),
    'blockchain-developer': _profile(('backend_platform', 0.8), ('operations_security', 0.8)),
    'qa-engineer': _profile(('leadership_process', 0.7), ('application_build', 0.4)),
    'software-architect': _profile(('leadership_process', 0.8), ('backend_platform', 0.6)),
    'cyber-security-engineer-analyst': _profile(('operations_security', 1.2)),
    'ux-designer': _profile(('people_product', 1.2), ('application_build', 0.3)),
    'technical-writer': _profile(('documentation_practice', 1.2), ('people_product', 0.4)),
    'game-developer': _profile(('game_family', 1.2), ('application_build', 0.8)),
    'server-side-game-developer': _profile(('game_family', 1.0), ('backend_platform', 1.0)),
    'mlops-engineer': _profile(('operations_security', 0.9), ('data_ai', 0.8), ('backend_platform', 0.5)),
    'product-manager': _profile(('people_product', 1.0), ('leadership_process', 0.8)),
    'engineering-manager': _profile(('leadership_process', 1.2), ('people_product', 0.4)),
    'developer-relations': _profile(('documentation_practice', 0.8), ('people_product', 0.8), ('application_build', 0.4)),
    'bi-analyst': _profile(('data_ai', 0.8), ('people_product', 0.5)),
}

for role_slug, family_weights in ROLE_FAMILY_PROFILE_WEIGHTS.items():
    ROLE_PROFILE_WEIGHTS[role_slug].update(family_weights)
