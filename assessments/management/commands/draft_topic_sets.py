"""Draft Assessable Topic Sets for one role, from its imported roadmap graph.

The draft is a starting point for review, never a publication: it is written
under ``data/content/topic_sets/drafts/`` where the catalog sync does not read
it, no database row is created, and the Canonical Thai wording is left for the
human review that owns it (ADR-0003).

Sets are grown from the graph's own prerequisite edges -- nodes connected to
each other belong to one set -- and adjusted into the 15-20 range by merging
the smallest adjacent sets or splitting the largest ones. Navigational nodes
("Pick a Language") are left unassigned and reported in the draft.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from assessments.services import assessable_topic_set_service
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode, Role


TARGET_MIN_SETS = 15
TARGET_MAX_SETS = 20

# Roadmap graphs carry navigational nodes addressed to the reader rather than
# named skills -- "Pick a Language", "Learn SQL", "Visit the DevOps Roadmap".
# They belong on the roadmap, but "I could work on Pick a Language in a real
# project" is not a question anybody can answer, so a draft leaves them for
# the reviewer rather than putting them in a set.
INSTRUCTION_TITLE_PREFIXES = ('pick ', 'learn ', 'visit ', 'choose ', 'read ', 'explore ', 'go to ')


def is_assessable_topic_title(title: str) -> bool:
    return not title.strip().lower().startswith(INSTRUCTION_TITLE_PREFIXES)


DRAFT_HEADER = """\
# Draft Assessable Topic Sets for {role_name}.
# Generated mechanically from the imported roadmap graph by draft_topic_sets.
# Nothing in this file is live: publication is the separate, reviewed step of
# moving reviewed sets into data/content/topic_sets/{role_slug}.yaml and
# running sync_content.
# Canonical Thai wording is drafted into title_th by whoever reviews this
# file (a person or an agent) and approved only by a person: every set starts
# at review.status: draft, and only a person changes it to reviewed (ADR-0004).
"""


class Command(BaseCommand):
    help = 'Draft Assessable Topic Sets for a role from its imported roadmap graph, for review. Never publishes.'

    def add_arguments(self, parser):
        parser.add_argument('role_slug', help='Slug of the role to draft sets for.')
        parser.add_argument('--force', action='store_true', help='Overwrite an existing draft for the role.')
        parser.add_argument(
            '--output-dir',
            default=None,
            help='Directory to write drafts under (default: data/content/topic_sets/drafts).',
        )

    def handle(self, *args, **options):
        role_slug = options['role_slug']
        try:
            role = Role.objects.get(slug=role_slug)
        except Role.DoesNotExist as exc:
            msg = f'No role with slug "{role_slug}".'
            raise CommandError(msg) from exc

        groups, unassigned = build_draft_groups(role)
        if not groups:
            msg = f'Role "{role_slug}" has no imported roadmap to draft from.'
            raise CommandError(msg)

        # Read the content directory at run time: tests and tooling repoint it.
        content_dir = assessable_topic_set_service.TOPIC_SET_CONTENT_DIR
        output_dir = Path(options['output_dir']) if options['output_dir'] else content_dir / 'drafts'
        draft_path = output_dir / f'{role.slug}.yaml'
        if draft_path.exists() and not options['force']:
            msg = f'A draft already exists at "{draft_path}"; pass --force to rewrite it.'
            raise CommandError(msg)
        reviewed_path = content_dir / f'{role.slug}.yaml'
        if reviewed_path.exists():
            self.stdout.write(
                self.style.WARNING(
                    f'Reviewed content already exists at "{reviewed_path}"; this draft does not touch it.',
                ),
            )

        document = render_draft(role, groups, unassigned)
        output_dir.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(document, encoding='utf-8')

        self.stdout.write(
            self.style.SUCCESS(
                f'Drafted {len(groups)} sets covering {sum(len(group) for group in groups)} nodes '
                f'into "{draft_path}" ({len(unassigned)} node(s) left unassigned).',
            ),
        )


def build_draft_groups(role) -> tuple[list[list[ExternalRoadmapNode]], list[ExternalRoadmapNode]]:
    """Cluster the role's nodes into draft groups, plus the nodes left unassigned.

    Connected components of the prerequisite edges form the groups; a subtopic
    joins its parent's group. Navigational titles are not assessable, so they
    are reported as unassigned rather than forced into a set.
    """
    nodes = list(ExternalRoadmapNode.objects.filter(role=role).order_by('display_order', 'id'))
    candidates = [node for node in nodes if is_assessable_topic_title(node.title)]
    unassigned = [node for node in nodes if not is_assessable_topic_title(node.title)]
    if not candidates:
        return [], unassigned

    root_of = {node.id: node.id for node in candidates}

    def find(node_id):
        while root_of[node_id] != node_id:
            root_of[node_id] = root_of[root_of[node_id]]
            node_id = root_of[node_id]
        return node_id

    def union(left_id, right_id):
        if left_id not in root_of or right_id not in root_of:
            return
        root_of[find(left_id)] = find(right_id)

    for source_id, target_id in ExternalRoadmapEdge.objects.filter(role=role).values_list('source_node_id', 'target_node_id'):
        union(source_id, target_id)
    for node in candidates:
        if node.parent_id is not None:
            union(node.id, node.parent_id)

    grouped: dict[int, list[ExternalRoadmapNode]] = {}
    for node in candidates:
        grouped.setdefault(find(node.id), []).append(node)
    groups = sorted(
        (sorted(members, key=lambda node: (node.display_order, node.id)) for members in grouped.values()),
        key=lambda members: (members[0].display_order, members[0].id),
    )
    return _fit_target_range(groups), unassigned


def _fit_target_range(groups):
    """Merge or split draft groups towards the 15-20 range without splitting pairs."""
    groups = list(groups)
    while len(groups) > TARGET_MAX_SETS:
        # Merge the adjacent pair that keeps every set as small as possible:
        # order in the roadmap is preserved, so the merged set stays coherent.
        sizes = [len(group) for group in groups]
        adjacent_pairs = [(sizes[index] + sizes[index + 1], index) for index in range(len(groups) - 1)]
        _combined, index = min(adjacent_pairs)
        groups[index:index + 2] = [groups[index] + groups[index + 1]]
    while len(groups) < TARGET_MIN_SETS:
        splittable = [index for index, group in enumerate(groups) if len(group) > 1]
        if not splittable:
            break
        index = max(splittable, key=lambda idx: len(groups[idx]))
        group = groups[index]
        middle = len(group) // 2
        groups[index:index + 1] = [group[:middle], group[middle:]]
    return groups


def _draft_title(group: list[ExternalRoadmapNode]) -> str:
    titles = [node.title for node in group if node.node_type == ExternalRoadmapNode.NodeType.TOPIC] or [group[0].title]
    if len(titles) == 1:
        return titles[0]
    return f'{titles[0]} and {titles[1]}'


def _draft_key(title: str, used: set[str]) -> str:
    base = title.lower().replace(' ', '-').replace('/', '-').replace('&', 'and')[:64].strip('-')
    key, attempt = base, 2
    while key in used:
        key = f'{base}-{attempt}'
        attempt += 1
    used.add(key)
    return key


def render_draft(role, groups, unassigned) -> str:
    """The reviewable draft document, including what the draft does not decide."""
    used_keys: set[str] = set()
    lines = [DRAFT_HEADER.format(role_name=role.name, role_slug=role.slug), 'role_slug: ' + role.slug, 'status: draft', '', 'sets:']
    for group in groups:
        key = _draft_key(slugify(_draft_title(group)), used_keys)
        lines.append(f'  - key: {key}')
        lines.append(f'    title: {_draft_title(group)}')
        lines.append("    title_th: ''")
        lines.append('    review: {status: draft}')
        lines.append(f'    nodes: [{", ".join(node.slug for node in group)}]')
    lines.append('')
    lines.append('unassigned:')
    for node in unassigned:
        lines.append(f'  - slug: {node.slug}')
        lines.append(f'    title: {node.title}')
    if not unassigned:
        lines.append('  []')
    assigned_total = sum(len(group) for group in groups)
    lines.extend(
        [
            '',
            'counts:',
            f'  sets: {len(groups)}',
            f'  assigned: {assigned_total}',
            f'  unassigned: {len(unassigned)}',
            '',
        ],
    )
    return '\n'.join(lines)
