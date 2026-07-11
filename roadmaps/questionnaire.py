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


# Signal-strength ladder for question authoring: questions declare ordinal
# levels (primary/secondary/contrast) and seeds.py converts them to these
# numbers. Definitions live in docs/scoring-methodology.md.
SIGNAL_STRENGTH_WEIGHTS = {
    'primary': 1.0,
    'secondary': 0.6,
    'contrast': 0.3,
}

# ROLE_PROFILE_WEIGHTS is derived from data/content/role_dimension_relevance.yaml
# (ordinal levels + rationale + sources) via `manage.py generate_role_weights`.
# Never edit weights by hand — edit the mapping levels and regenerate.
from roadmaps.role_weights_generated import ROLE_PROFILE_WEIGHTS  # noqa: E402


__all__ = [
    'CORE_ROLE_DIMENSIONS',
    'ROLE_DIMENSIONS',
    'ROLE_DIMENSION_LABELS',
    'ROLE_PROFILE_WEIGHTS',
    'SIGNAL_STRENGTH_WEIGHTS',
    'SWEBOK_KNOWLEDGE_AREAS',
    'SWEBOK_SOURCE_VERSION',
]
