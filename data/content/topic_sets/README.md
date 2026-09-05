# Assessable Topic Sets

One file per role, named `<role-slug>.yaml`. Each set is an authored cluster of
that role's imported roadmap nodes, written so a respondent can place
themselves against it in a single Skill Assessment question.

```yaml
role_slug: backend-developer
sets:
  - key: internet-and-web-protocols
    title: Internet and web protocols
    title_th: อินเทอร์เน็ตและโปรโตคอลเว็บ
    review: {status: draft}
    display_order: 1
    nodes: [internet, http, https]
```

- `key` is role-local; the stable catalog key is `<role-slug>--<key>`.
- `nodes` lists `ExternalRoadmapNode.slug` values for that role. A slug matching
  no imported node is reported by `validate_topic_set_catalog`, not dropped.
- `title_th` is the Canonical Thai wording. `review: {status: draft | reviewed}`
  records whether a person has approved it (ADR-0004); an agent drafts wording
  but never sets `reviewed`. `validate_topic_set_catalog --strict` gates on the
  status, and a set is served with its draft wording in the meantime.
- `display_order` is optional and defaults to the position in the file.

A role with no file here has no Skill Assessment: nothing is read off its
imported roadmap, and the role-independent items that once stood in were
retired (ADR-0005). Every curated role has a file, and a test fails if one is
dropped.

Run `.venv\Scripts\python.exe manage.py validate_topic_set_catalog` to see what
is still missing, and `manage.py sync_content` to load them.
