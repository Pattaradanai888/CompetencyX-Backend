"""Serve roadmap.sh graph data from our own database.

The frontend used to fetch these graphs from ``raw.githubusercontent.com`` on
every page view, topologically sort them in the browser, and render the result
as the role's learning sequence. That made the page depend on a third party's
fork at ``master``, failed silently when the network was unavailable (dropping
the page from a full roadmap back to the handful of curated topics), and left
us no way to review what a respondent was shown.

The graphs are now imported as master data by
:func:`roadmaps.seeds.sync_external_roadmap_graphs` -- already ordered so a
prerequisite precedes what it unlocks -- and this module reads the same
sequence back out.
"""

from collections import defaultdict

from .models import ExternalRoadmapEdge, ExternalRoadmapNode


def _unique_titles(nodes: list[ExternalRoadmapNode]) -> list[str]:
    seen: set[str] = set()
    titles = []
    for node in sorted(nodes, key=lambda item: (item.display_order, item.title)):
        if node.title not in seen:
            seen.add(node.title)
            titles.append(node.title)
    return titles


def build_external_roadmap_topics(role) -> list[dict]:
    """The role's external roadmap as an ordered topic list.

    Returns ``[]`` when the role has no vendored snapshot, so such a role
    degrades to its curated topics instead of failing.
    """
    nodes = list(ExternalRoadmapNode.objects.filter(role=role).order_by('display_order', 'id'))
    if not nodes:
        return []

    nodes_by_id = {node.id: node for node in nodes}
    prerequisites: dict[int, list[ExternalRoadmapNode]] = defaultdict(list)
    follow_ons: dict[int, list[ExternalRoadmapNode]] = defaultdict(list)
    subtopics: dict[int, list[ExternalRoadmapNode]] = defaultdict(list)

    for node in nodes:
        if node.parent_id is not None:
            subtopics[node.parent_id].append(node)

    for source_id, target_id in ExternalRoadmapEdge.objects.filter(role=role).values_list(
        'source_node_id',
        'target_node_id',
    ):
        source_node = nodes_by_id.get(source_id)
        target_node = nodes_by_id.get(target_id)
        if source_node is None or target_node is None:
            continue
        # A parent -> subtopic edge is nesting, not a prerequisite; it is already
        # reported through `subtopic_titles`.
        if target_node.parent_id == source_id:
            continue
        prerequisites[target_id].append(source_node)
        follow_ons[source_id].append(target_node)

    return [
        {
            'slug': node.slug,
            'title': node.title,
            'topic_group': node.topic_group,
            'node_type': node.node_type,
            'display_order': node.display_order,
            'parent_title': nodes_by_id[node.parent_id].title if node.parent_id else '',
            'prerequisite_titles': _unique_titles(prerequisites.get(node.id, [])),
            'subtopic_titles': _unique_titles(subtopics.get(node.id, [])),
            'follow_on_titles': _unique_titles(follow_ons.get(node.id, [])),
        }
        for node in nodes
    ]


def build_external_source_meta(role) -> dict | None:
    """Provenance of the imported graph, or ``None`` when the role has no snapshot."""
    node = ExternalRoadmapNode.objects.filter(role=role).order_by('display_order', 'id').first()
    if node is None:
        return None
    return {
        'source': node.source,
        'source_url': node.source_url,
        'retrieved_on': node.retrieved_on,
        'node_count': ExternalRoadmapNode.objects.filter(role=role).count(),
    }
