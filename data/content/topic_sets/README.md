# Assessable Topic Sets

One file per role, named `<role-slug>.yaml`. Each set is a reviewed cluster of
that role's imported roadmap nodes, written so a respondent can place
themselves against it in a single Skill Assessment question.

```yaml
role_slug: backend-developer
sets:
  - key: internet-and-web-protocols
    title: Internet and web protocols
    title_th: อินเทอร์เน็ตและโปรโตคอลเว็บ
    display_order: 1
    nodes: [internet, http, https]
```

- `key` is role-local; the stable catalog key is `<role-slug>--<key>`.
- `nodes` lists `ExternalRoadmapNode.slug` values for that role. A slug matching
  no imported node is reported by `validate_topic_set_catalog`, not dropped.
- `title_th` is the Canonical Thai wording; a set without it is reported as
  unreviewed.
- `display_order` is optional and defaults to the position in the file.

A role with no file here keeps the items derived from its imported roadmap, so
the assessment is never empty while the sets are being authored.

Run `.venv\Scripts\python.exe manage.py validate_topic_set_catalog` to see what
is still missing, and `manage.py sync_content` to load them.
