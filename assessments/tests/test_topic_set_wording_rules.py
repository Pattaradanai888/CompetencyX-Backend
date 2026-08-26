"""The authored topic-set catalog follows the ADR-0004 wording rules.

ADR-0004 decision 3 fixes the register of the Canonical Thai Wording: the
working vocabulary of the role, ความปลอดภัย (never ความมั่นคงปลอดภัย), bare
parenthetical glosses with canonically spelled proper nouns, and one spelling
per transliterated word. Decision 1 keeps approval a human act: nothing an agent
lands may carry ``review.status: reviewed``. These checks are the mechanical
part of that gate; whether the Thai is *good* stays a person's call.
"""

import re

import pytest

from assessments.services.assessable_topic_set_service import load_assessable_topic_sets


FORBIDDEN_TERMS = {
    'ความมั่นคงปลอดภัย': 'security register is ความปลอดภัย',
    'IPSEC': 'canonical spelling is IPsec',
    'กรอบงาน': 'framework is เฟรมเวิร์ก',
    'โมบาย': 'mobile is มือถือ',
    'ควรรู้': 'a set names what it contains, never what the respondent should learn',
    'ผู้มีส่วนได้ส่วนเสีย': 'Stakeholder stays in English',
    'การเรียนรู้ของเครื่อง': 'Machine Learning stays in English',
    'การเรียนรู้เชิงลึก': 'Deep Learning stays in English',
    'ดีพลอย': 'Deploy stays in English',
    'การเขียนโปรแกรมเชิงปฏิกิริยา': 'Reactive Programming stays in English',
    'คณิตศาสตร์ไม่ต่อเนื่อง': 'discrete mathematics is คณิตศาสตร์ดิสครีต',
}
FORBIDDEN_PATTERNS = {re.compile(re.escape(term)): reason for term, reason in FORBIDDEN_TERMS.items()}
# The misspelling is a suffix of the correct spelling, so it needs a lookbehind rather than a literal.
FORBIDDEN_PATTERNS[re.compile(r'(?<!แ)อนิเมชัน')] = 'animation is แอนิเมชัน'
FORBIDDEN_INSIDE_GLOSS = ('เช่น', 'อย่าง', 'และ')
GLOSS = re.compile(r'\(([^)]*)\)')

AUTHORED_SETS = load_assessable_topic_sets()
SET_IDS = [entry['set_key'] for entry in AUTHORED_SETS]


@pytest.mark.parametrize('entry', AUTHORED_SETS, ids=SET_IDS)
def test_wording_uses_the_adr_0004_register(entry):
    title_th = entry['title_th']
    offences = [f'{pattern.pattern} ({reason})' for pattern, reason in FORBIDDEN_PATTERNS.items() if pattern.search(title_th)]
    assert not offences, f'{entry["set_key"]}: {title_th!r} contains {offences}'


@pytest.mark.parametrize('entry', AUTHORED_SETS, ids=SET_IDS)
def test_a_gloss_is_a_bare_parenthetical_of_at_most_three_names(entry):
    title_th = entry['title_th']
    for gloss in GLOSS.findall(title_th):
        assert not any(word in gloss for word in FORBIDDEN_INSIDE_GLOSS), f'{entry["set_key"]}: conversational gloss in {title_th!r}'
        items = [item for item in re.split(r',\s*', gloss.split('--')[-1]) if item.strip()]
        assert len(items) <= 3, f'{entry["set_key"]}: gloss lists {len(items)} names in {title_th!r}'


@pytest.mark.parametrize('entry', AUTHORED_SETS, ids=SET_IDS)
def test_no_set_is_marked_reviewed_by_an_agent(entry):
    assert entry['review_status'] == 'draft', f"{entry['set_key']} is marked reviewed; that flip is a person's action"


def test_the_same_concept_has_the_same_thai_across_roles():
    """One rendering per cross-role term (docs/topic-set-thai-review.md §6.2)."""
    titles = {entry['set_key']: entry['title_th'] for entry in AUTHORED_SETS}

    def titled(prefix, *set_keys):
        return {key: titles[key] for key in set_keys if not titles[key].startswith(prefix)}

    assert (
        titled(
            'การรับมือ Incident',
            'cyber-security-engineer-analyst--incident-response',
            'devsecops-engineer--incident-response',
            'engineering-manager--incident-and-crisis',
        )
        == {}
    )
    assert (
        titled(
            'Infrastructure as Code',
            'data-engineer--infrastructure-as-code',
            'devops-engineer--infrastructure-provisioning',
            'mlops-engineer--infrastructure-as-code',
            'full-stack-developer--infrastructure-as-code',
        )
        == {}
    )
    assert titled('Configuration Management', 'devops-engineer--configuration-management') == {}
    assert titles['postgresql-developer-dba--automation'].count('Configuration Management') == 1
    assert titled('การจัดการ Secret ', 'devops-engineer--secret-management') == {}
    assert 'Virtualization' in titles['backend-developer--containers-and-virtualization']
    assert 'Virtualization' in titles['cyber-security-engineer-analyst--operating-systems']
