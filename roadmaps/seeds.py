from roadmaps.models import Question, QuestionOption, RoadmapTopic, Role, TopicPrerequisite


ROLE_SEEDS = [
    {
        'slug': 'frontend-engineer',
        'name': 'Frontend Engineer',
        'description': 'Builds browser-based user interfaces and application experiences.',
        'topics': [
            {
                'slug': 'html-css',
                'title': 'HTML and CSS Fundamentals',
                'description': 'Structure pages and style interfaces with maintainable CSS.',
                'difficulty': RoadmapTopic.Difficulty.BEGINNER,
                'display_order': 1,
            },
            {
                'slug': 'javascript',
                'title': 'JavaScript Fundamentals',
                'description': 'Work with core language features, DOM APIs, and browser execution.',
                'difficulty': RoadmapTopic.Difficulty.BEGINNER,
                'display_order': 2,
                'prerequisites': ['html-css'],
            },
            {
                'slug': 'frontend-testing',
                'title': 'Frontend Testing',
                'description': 'Validate UI behavior with component and end-to-end testing.',
                'difficulty': RoadmapTopic.Difficulty.INTERMEDIATE,
                'display_order': 3,
                'prerequisites': ['javascript'],
            },
        ],
    },
    {
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'description': 'Builds APIs, data flows, and server-side application logic.',
        'topics': [
            {
                'slug': 'git',
                'title': 'Git Fundamentals',
                'description': 'Track changes, branch safely, and collaborate on code.',
                'difficulty': RoadmapTopic.Difficulty.BEGINNER,
                'display_order': 1,
            },
            {
                'slug': 'http',
                'title': 'HTTP Fundamentals',
                'description': 'Understand requests, responses, status codes, and API semantics.',
                'difficulty': RoadmapTopic.Difficulty.BEGINNER,
                'display_order': 2,
            },
            {
                'slug': 'databases',
                'title': 'Databases',
                'description': 'Model data, query efficiently, and understand relational concepts.',
                'difficulty': RoadmapTopic.Difficulty.INTERMEDIATE,
                'display_order': 3,
                'prerequisites': ['git'],
            },
            {
                'slug': 'apis',
                'title': 'API Design',
                'description': 'Design web APIs with clear resources, validation, and versioning.',
                'difficulty': RoadmapTopic.Difficulty.INTERMEDIATE,
                'display_order': 4,
                'prerequisites': ['http', 'databases'],
            },
        ],
    },
    {
        'slug': 'full-stack-engineer',
        'name': 'Full-Stack Engineer',
        'description': 'Builds user-facing features and the backend systems behind them.',
        'topics': [],
    },
    {
        'slug': 'devops-engineer',
        'name': 'DevOps Engineer',
        'description': 'Owns deployment, automation, observability, and platform reliability.',
        'topics': [],
    },
    {
        'slug': 'data-engineer',
        'name': 'Data Engineer',
        'description': 'Builds data pipelines, storage, and processing systems.',
        'topics': [],
    },
    {
        'slug': 'mobile-engineer',
        'name': 'Mobile Engineer',
        'description': 'Builds native or cross-platform mobile applications.',
        'topics': [],
    },
    {
        'slug': 'qa-test-engineer',
        'name': 'QA / Test Engineer',
        'description': 'Designs quality strategies, automation, and release validation.',
        'topics': [],
    },
    {
        'slug': 'cybersecurity-engineer',
        'name': 'Cybersecurity Engineer',
        'description': 'Protects systems through secure design, detection, and incident response.',
        'topics': [],
    },
]

QUESTION_SEEDS = [
    {
        'code': 'role-preference-systems-vs-ui',
        'stage': Question.Stage.ROLE,
        'question_type': Question.Type.SINGLE_CHOICE,
        'prompt': 'Which kind of work sounds more interesting right now?',
        'help_text': 'Pick the work you would rather spend time learning first.',
        'difficulty': 1,
        'discrimination_score': 2.5,
        'display_order': 1,
        'options': [
            {
                'key': 'ui',
                'label': 'Building polished browser interfaces',
                'display_order': 1,
                'role_weights': {
                    'frontend-engineer': 3,
                    'full-stack-engineer': 1,
                    'mobile-engineer': 1,
                },
            },
            {
                'key': 'systems',
                'label': 'Designing APIs, data flows, and backend services',
                'display_order': 2,
                'role_weights': {
                    'backend-engineer': 3,
                    'full-stack-engineer': 1,
                    'data-engineer': 1,
                },
            },
            {
                'key': 'platform',
                'label': 'Automating deployments and operating infrastructure',
                'display_order': 3,
                'role_weights': {
                    'devops-engineer': 3,
                    'cybersecurity-engineer': 1,
                },
            },
        ],
    },
    {
        'code': 'role-preference-data-vs-quality',
        'stage': Question.Stage.ROLE,
        'question_type': Question.Type.SINGLE_CHOICE,
        'prompt': 'Which problem space feels more natural to you?',
        'help_text': 'Choose the area where you would be most motivated to improve.',
        'difficulty': 1,
        'discrimination_score': 2.0,
        'display_order': 2,
        'options': [
            {
                'key': 'data',
                'label': 'Transforming and modeling data',
                'display_order': 1,
                'role_weights': {
                    'data-engineer': 3,
                    'backend-engineer': 1,
                },
            },
            {
                'key': 'quality',
                'label': 'Finding edge cases and improving reliability',
                'display_order': 2,
                'role_weights': {
                    'qa-test-engineer': 3,
                    'devops-engineer': 1,
                },
            },
            {
                'key': 'security',
                'label': 'Preventing vulnerabilities and strengthening defenses',
                'display_order': 3,
                'role_weights': {
                    'cybersecurity-engineer': 3,
                    'devops-engineer': 1,
                },
            },
        ],
    },
    {
        'code': 'backend-git-basics',
        'stage': Question.Stage.SKILL,
        'question_type': Question.Type.YES_NO_MAYBE,
        'prompt': 'Can you create branches, merge changes, and resolve simple Git conflicts?',
        'difficulty': 1,
        'discrimination_score': 1.5,
        'display_order': 10,
        'role_slug': 'backend-engineer',
        'topic_slug': 'git',
        'options': [
            {'key': 'yes', 'label': 'Yes', 'display_order': 1, 'mastery_value': 1.0},
            {'key': 'maybe', 'label': 'Maybe', 'display_order': 2, 'mastery_value': 0.5},
            {'key': 'no', 'label': 'No', 'display_order': 3, 'mastery_value': 0.0},
        ],
    },
    {
        'code': 'backend-http-basics',
        'stage': Question.Stage.SKILL,
        'question_type': Question.Type.YES_NO_MAYBE,
        'prompt': 'Are you comfortable with HTTP methods, status codes, and request/response structure?',
        'difficulty': 1,
        'discrimination_score': 1.7,
        'display_order': 11,
        'role_slug': 'backend-engineer',
        'topic_slug': 'http',
        'options': [
            {'key': 'yes', 'label': 'Yes', 'display_order': 1, 'mastery_value': 1.0},
            {'key': 'maybe', 'label': 'Maybe', 'display_order': 2, 'mastery_value': 0.5},
            {'key': 'no', 'label': 'No', 'display_order': 3, 'mastery_value': 0.0},
        ],
    },
    {
        'code': 'backend-database-basics',
        'stage': Question.Stage.SKILL,
        'question_type': Question.Type.YES_NO_MAYBE,
        'prompt': 'Can you write basic SQL queries and explain tables, joins, and indexes?',
        'difficulty': 2,
        'discrimination_score': 1.9,
        'display_order': 12,
        'role_slug': 'backend-engineer',
        'topic_slug': 'databases',
        'options': [
            {'key': 'yes', 'label': 'Yes', 'display_order': 1, 'mastery_value': 1.0},
            {'key': 'maybe', 'label': 'Maybe', 'display_order': 2, 'mastery_value': 0.5},
            {'key': 'no', 'label': 'No', 'display_order': 3, 'mastery_value': 0.0},
        ],
    },
    {
        'code': 'backend-api-design',
        'stage': Question.Stage.SKILL,
        'question_type': Question.Type.YES_NO_MAYBE,
        'prompt': 'Have you designed or documented an API with authentication, validation, and clear endpoints?',
        'difficulty': 2,
        'discrimination_score': 2.0,
        'display_order': 13,
        'role_slug': 'backend-engineer',
        'topic_slug': 'apis',
        'options': [
            {'key': 'yes', 'label': 'Yes', 'display_order': 1, 'mastery_value': 1.0},
            {'key': 'maybe', 'label': 'Maybe', 'display_order': 2, 'mastery_value': 0.5},
            {'key': 'no', 'label': 'No', 'display_order': 3, 'mastery_value': 0.0},
        ],
    },
    {
        'code': 'frontend-html-css-basics',
        'stage': Question.Stage.SKILL,
        'question_type': Question.Type.YES_NO_MAYBE,
        'prompt': 'Can you build responsive layouts with semantic HTML and reusable CSS?',
        'difficulty': 1,
        'discrimination_score': 1.5,
        'display_order': 20,
        'role_slug': 'frontend-engineer',
        'topic_slug': 'html-css',
        'options': [
            {'key': 'yes', 'label': 'Yes', 'display_order': 1, 'mastery_value': 1.0},
            {'key': 'maybe', 'label': 'Maybe', 'display_order': 2, 'mastery_value': 0.5},
            {'key': 'no', 'label': 'No', 'display_order': 3, 'mastery_value': 0.0},
        ],
    },
    {
        'code': 'frontend-javascript-basics',
        'stage': Question.Stage.SKILL,
        'question_type': Question.Type.YES_NO_MAYBE,
        'prompt': 'Are you comfortable with JavaScript fundamentals, DOM updates, and asynchronous requests?',
        'difficulty': 1,
        'discrimination_score': 1.8,
        'display_order': 21,
        'role_slug': 'frontend-engineer',
        'topic_slug': 'javascript',
        'options': [
            {'key': 'yes', 'label': 'Yes', 'display_order': 1, 'mastery_value': 1.0},
            {'key': 'maybe', 'label': 'Maybe', 'display_order': 2, 'mastery_value': 0.5},
            {'key': 'no', 'label': 'No', 'display_order': 3, 'mastery_value': 0.0},
        ],
    },
    {
        'code': 'frontend-testing-basics',
        'stage': Question.Stage.SKILL,
        'question_type': Question.Type.YES_NO_MAYBE,
        'prompt': 'Have you written component, integration, or end-to-end tests for frontend code?',
        'difficulty': 2,
        'discrimination_score': 1.6,
        'display_order': 22,
        'role_slug': 'frontend-engineer',
        'topic_slug': 'frontend-testing',
        'options': [
            {'key': 'yes', 'label': 'Yes', 'display_order': 1, 'mastery_value': 1.0},
            {'key': 'maybe', 'label': 'Maybe', 'display_order': 2, 'mastery_value': 0.5},
            {'key': 'no', 'label': 'No', 'display_order': 3, 'mastery_value': 0.0},
        ],
    },
]


def seed_mvp_content(*, stdout=None):
    roles_by_slug: dict[str, Role] = {}
    topics_by_key: dict[tuple[str, str], RoadmapTopic] = {}

    for role_seed in ROLE_SEEDS:
        role, _created = Role.objects.update_or_create(
            slug=role_seed['slug'],
            defaults={
                'name': role_seed['name'],
                'description': role_seed['description'],
                'is_active': True,
            },
        )
        roles_by_slug[role.slug] = role

        for topic_seed in role_seed['topics']:
            topic, _created = RoadmapTopic.objects.update_or_create(
                role=role,
                slug=topic_seed['slug'],
                defaults={
                    'title': topic_seed['title'],
                    'description': topic_seed['description'],
                    'difficulty': topic_seed['difficulty'],
                    'display_order': topic_seed['display_order'],
                    'is_active': True,
                    'parent': None,
                },
            )
            topics_by_key[(role.slug, topic.slug)] = topic

    TopicPrerequisite.objects.all().delete()
    for role_seed in ROLE_SEEDS:
        role_slug = role_seed['slug']
        for topic_seed in role_seed['topics']:
            for prerequisite_slug in topic_seed.get('prerequisites', []):
                TopicPrerequisite.objects.update_or_create(
                    topic=topics_by_key[(role_slug, topic_seed['slug'])],
                    prerequisite=topics_by_key[(role_slug, prerequisite_slug)],
                    defaults={
                        'required_mastery_threshold': 0.7,
                        'dependency_weight': 1.0,
                    },
                )

    for question_seed in QUESTION_SEEDS:
        role = roles_by_slug.get(question_seed.get('role_slug')) if question_seed.get('role_slug') else None
        topic = topics_by_key.get((question_seed['role_slug'], question_seed['topic_slug'])) if question_seed.get('topic_slug') else None
        question, _created = Question.objects.update_or_create(
            code=question_seed['code'],
            defaults={
                'stage': question_seed['stage'],
                'question_type': question_seed['question_type'],
                'prompt': question_seed['prompt'],
                'help_text': question_seed.get('help_text', ''),
                'role': role,
                'topic': topic,
                'difficulty': question_seed['difficulty'],
                'discrimination_score': question_seed['discrimination_score'],
                'display_order': question_seed['display_order'],
                'is_active': True,
            },
        )
        existing_keys = set(question.options.values_list('key', flat=True))
        seed_keys = set()
        for option_seed in question_seed['options']:
            seed_keys.add(option_seed['key'])
            QuestionOption.objects.update_or_create(
                question=question,
                key=option_seed['key'],
                defaults={
                    'label': option_seed['label'],
                    'value': option_seed.get('value', ''),
                    'display_order': option_seed['display_order'],
                    'mastery_value': option_seed.get('mastery_value', 0.0),
                    'role_weights': option_seed.get('role_weights', {}),
                },
            )
        if existing_keys - seed_keys:
            question.options.exclude(key__in=seed_keys).delete()

    if stdout is not None:
        stdout.write(
            f'Seeded {Role.objects.count()} roles, '
            f'{RoadmapTopic.objects.count()} topics, '
            f'{Question.objects.count()} questions, and '
            f'{QuestionOption.objects.count()} options.'
        )
