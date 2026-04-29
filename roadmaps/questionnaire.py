# --- Role-Discovery Dimensions (v3: 6 bipolar trait axes) ---
#
# Role discovery measures work preferences before mapping them to roles. Each
# answer adds positive evidence to one endpoint; the opposite endpoint is pulled
# down only through the axis balance.

ROLE_DIMENSIONS = (
    'people_discovery',
    'technical_build',
    'influence_coordination',
    'independent_deep_work',
    'business_process',
    'product_experience',
    'data_investigation',
    'systems_operation',
    'requirements_modeling',
    'implementation_delivery',
    'risk_control',
    'innovation_experiment',
)

ROLE_TRAIT_AXES = (
    ('people_discovery', 'technical_build'),
    ('influence_coordination', 'independent_deep_work'),
    ('business_process', 'product_experience'),
    ('data_investigation', 'systems_operation'),
    ('requirements_modeling', 'implementation_delivery'),
    ('risk_control', 'innovation_experiment'),
)

ROLE_DIMENSION_LABELS = {
    'people_discovery': 'People Discovery',
    'technical_build': 'Technical Build',
    'influence_coordination': 'Influence and Coordination',
    'independent_deep_work': 'Independent Deep Work',
    'business_process': 'Business Process',
    'product_experience': 'Product Experience',
    'data_investigation': 'Data Investigation',
    'systems_operation': 'Systems Operation',
    'requirements_modeling': 'Requirements Modeling',
    'implementation_delivery': 'Implementation Delivery',
    'risk_control': 'Risk Control',
    'innovation_experiment': 'Innovation Experiment',
}

# --- Role Profile Weights ---
#
# Each role maps to trait endpoints with relative weights. Profiles are grounded
# in O*NET-style work activities and the product taxonomy: development roles
# lean toward building and delivery, analyst roles toward modeling and process,
# security/operations roles toward systems and control, and product/design roles
# toward people and product experience.

ROLE_PROFILE_WEIGHTS = {
    'frontend-engineer': {
        'technical_build': 0.8,
        'independent_deep_work': 0.6,
        'product_experience': 0.8,
        'implementation_delivery': 0.9,
        'innovation_experiment': 0.4,
    },
    'backend-engineer': {
        'technical_build': 1.0,
        'independent_deep_work': 0.8,
        'systems_operation': 0.8,
        'implementation_delivery': 1.0,
        'risk_control': 0.4,
    },
    'full-stack-engineer': {
        'technical_build': 0.9,
        'product_experience': 0.6,
        'systems_operation': 0.5,
        'implementation_delivery': 1.0,
        'innovation_experiment': 0.5,
    },
    'devops-engineer': {
        'technical_build': 0.9,
        'influence_coordination': 0.4,
        'systems_operation': 1.0,
        'implementation_delivery': 0.8,
        'risk_control': 0.7,
    },
    'data-engineer': {
        'technical_build': 0.9,
        'independent_deep_work': 0.7,
        'data_investigation': 0.6,
        'systems_operation': 0.8,
        'implementation_delivery': 0.9,
    },
    'data-scientist': {
        'technical_build': 0.5,
        'independent_deep_work': 0.8,
        'data_investigation': 1.0,
        'requirements_modeling': 0.4,
        'innovation_experiment': 0.7,
    },
    'ai-engineer': {
        'technical_build': 0.9,
        'independent_deep_work': 0.7,
        'data_investigation': 0.7,
        'implementation_delivery': 0.8,
        'innovation_experiment': 0.8,
    },
    'qa-test-engineer': {
        'technical_build': 0.6,
        'independent_deep_work': 0.6,
        'data_investigation': 0.6,
        'requirements_modeling': 0.7,
        'risk_control': 0.9,
    },
    'ux-ui-designer': {
        'people_discovery': 1.0,
        'influence_coordination': 0.4,
        'product_experience': 1.0,
        'requirements_modeling': 0.8,
        'innovation_experiment': 0.6,
    },
    'product-manager': {
        'people_discovery': 0.8,
        'influence_coordination': 1.0,
        'product_experience': 0.9,
        'data_investigation': 0.5,
        'innovation_experiment': 0.7,
    },
    'project-manager': {
        'people_discovery': 0.5,
        'influence_coordination': 1.0,
        'business_process': 0.7,
        'implementation_delivery': 0.9,
        'risk_control': 0.6,
    },
    'business-analyst': {
        'people_discovery': 0.7,
        'influence_coordination': 0.8,
        'business_process': 1.0,
        'requirements_modeling': 1.0,
        'risk_control': 0.4,
    },
    'systems-analyst': {
        'technical_build': 0.5,
        'influence_coordination': 0.5,
        'business_process': 0.8,
        'systems_operation': 0.6,
        'requirements_modeling': 0.9,
    },
    'system-engineer': {
        'technical_build': 1.0,
        'independent_deep_work': 0.7,
        'systems_operation': 1.0,
        'implementation_delivery': 0.7,
        'risk_control': 0.8,
    },
    'sap-erp-consultant': {
        'people_discovery': 0.6,
        'influence_coordination': 0.8,
        'business_process': 1.0,
        'systems_operation': 0.5,
        'requirements_modeling': 0.8,
    },
    'mobile-engineer': {
        'technical_build': 0.8,
        'independent_deep_work': 0.6,
        'product_experience': 0.9,
        'systems_operation': 0.4,
        'implementation_delivery': 0.9,
    },
    'cybersecurity-engineer': {
        'technical_build': 0.8,
        'independent_deep_work': 0.7,
        'data_investigation': 0.6,
        'systems_operation': 0.8,
        'risk_control': 1.0,
    },
    'product-owner': {
        'people_discovery': 0.6,
        'influence_coordination': 0.8,
        'product_experience': 0.7,
        'requirements_modeling': 0.7,
        'implementation_delivery': 0.8,
    },
    'data-analyst': {
        'people_discovery': 0.4,
        'influence_coordination': 0.5,
        'business_process': 0.6,
        'data_investigation': 1.0,
        'requirements_modeling': 0.6,
    },
    'solutions-architect': {
        'technical_build': 0.7,
        'influence_coordination': 0.8,
        'business_process': 0.6,
        'systems_operation': 0.8,
        'requirements_modeling': 0.7,
    },
    'system-architect': {
        'technical_build': 1.0,
        'independent_deep_work': 0.8,
        'systems_operation': 0.9,
        'requirements_modeling': 0.8,
        'risk_control': 0.5,
    },
}

CORE_ROLE_DIMENSIONS = set(ROLE_DIMENSIONS)

# Static trait discovery resolves from the completed 30-question profile.
ROLE_TIEBREAKER_PAIRS = ()
