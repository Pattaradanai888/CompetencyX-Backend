# Assessable Topic Set review — Canonical Thai wording and grouping

**Reviewed:** 2026-08-26, against all 26 files in `data/content/topic_sets/` (459 sets).

**Status: triage, not approval.** `CONTEXT.md` makes the Canonical Thai wording the
authoritative definition of what an item means, and issue #7 states that the final review
of that wording is a human gate: "An agent can prepare, mechanically check, and land the
reviewed content; it cannot approve it." Nothing in this document has been applied. It
exists so a Thai-speaking reviewer can start with the ~40 sets most likely to be wrong
instead of reading all 459 cold.

Every Thai string quoted below was verified to exist verbatim in the file named. The
judgements about whether that Thai is *good* are model-generated and unverified — treat
them as candidates, not findings.

Two files came back with nothing to flag: `ux-designer.yaml` and `technical-writer.yaml`.

---

## 1. Start here — highest-confidence errors

These five are wrong on the facts, not on taste.

| File | Set | Current Thai | Problem |
| --- | --- | --- | --- |
| `devsecops-engineer.yaml` | `security-testing-tools` | เครื่องมือ**ทดสอบทะลุระบบ**และสแกนช่องโหว่ | Penetration testing is ทดสอบ**เจาะ**ระบบ. ทะลุระบบ is not a term Thai security practitioners use. |
| `data-engineer.yaml` | `containers-and-orchestration` | คอนเทนเนอร์ **การจัดการคลัสเตอร์** และ CI/CD | Renders *orchestration* as "cluster management", which collides with `cluster-and-big-data` seven lines above (line 68 vs line 75) and diverges from `devops-engineer.yaml`, which calls the same concept การจัดการคอนเทนเนอร์. |
| `cyber-security-engineer-analyst.yaml` | `frameworks-and-standards` | **กรอบมาตรฐานภัยคุกคาม**และการกำกับดูแล | Garbled compound ("threat standard framework"). The set is two distinct things: threat-analysis frameworks (Kill Chain, ATT&CK, Diamond) and compliance standards (ISO, NIST, CIS). |
| `engineering-manager.yaml` | `culture-and-inclusion` | วัฒนธรรมทีมและการสร้าง**ความครอบคลุม** (Inclusion) | ความครอบคลุม means coverage/comprehensiveness, not inclusion. Literal-translation artifact. |
| `bi-analyst.yaml` | `professional-development` | — | Not a wording problem: 21 nodes covering portfolio, interview prep, and salary negotiation. These are career logistics, not a competency a respondent can self-rate. Wrong kind of content for the instrument. |

---

## 2. Cross-role terminology — one table, applied mechanically

The same concept is worded differently across roles, and in two files inconsistently
*within* one file. A respondent moving between roles sees different Thai for the same
thing. Deciding this table once resolves items 8, 9, 13, 14, 16, 17, 22, 23, 25, 32, and
34 of the ranked list below.

### 2.1 Security register — measured, not estimated

| File | ความมั่นคงปลอดภัย | ความปลอดภัย |
| --- | --- | --- |
| `devsecops-engineer.yaml` | 5 sets | 1 set |
| `cyber-security-engineer-analyst.yaml` | 1 set | 3 sets |
| backend, frontend, qa, data-engineer, ai-engineer, blockchain, postgresql, server-side-game, software-architect | 0 | 1 each |

Both are correct Thai. ความมั่นคงปลอดภัย is the formal/legal register and reads like a
ministry document; ความปลอดภัย is how practitioners speak. **Both security-heavy files are
internally inconsistent**, so this cannot be resolved by leaving each role to its own
convention. Pick one for the catalog.

### 2.2 Remaining terms to settle

| Concept | Renderings in use | Files |
| --- | --- | --- |
| Incident Response | การรับมือเหตุการณ์ผิดปกติ · การตอบสนองเหตุการณ์ · การจัดการเหตุการณ์และวิกฤต | cyber · devsecops · engineering-manager |
| Forensics | นิติวิทยาศาสตร์ดิจิทัล · ดิจิทัลฟอเรนซิก | cyber · devsecops |
| Machine Learning / Deep Learning | translated · half-translated · left English | ai-data-scientist · data-analyst · mlops, bi-analyst, data-engineer |
| Secret management | การจัดการความลับ | devops (reads as managing personal secrets; practitioners say การจัดการ Secret) |
| Stakeholder | ผู้มีส่วนได้ส่วนเสีย · Stakeholder | developer-relations · engineering-manager, product-manager |
| Accessibility | การทดสอบการเข้าถึงได้สำหรับทุกคน · การเข้าถึง | qa · ios |
| Infrastructure as Code | การจัดการโครงสร้างพื้นฐานด้วยโค้ด · การจัดการ Infrastructure เป็นโค้ด · left English | data-engineer, backend · mlops · full-stack |
| Virtualization | Virtualization · เวอร์ชวลไลเซชัน | backend · cyber |
| Reactive Programming | การเขียนโปรแกรมเชิงปฏิกิริยา · left English | ios · android, software-architect |
| Deploy | การดีพลอยระบบ (transliterated) · Deploy (Latin) | server-side-game · blockchain, full-stack |
| Configuration Management | การจัดการคอนฟิกอัตโนมัติ · left English | devops · postgresql |

Recommendation from the review, for the reviewer to accept or reject: Thai practitioners
overwhelmingly leave ML/DL, Reactive Programming, Secret, Stakeholder, and Deploy in
English. The translated forms read as textbook Thai rather than working vocabulary.

### 2.3 Parenthetical gloss rule

Gloss density ranges from ~90% of sets (cyber) to ~20% (ux-designer, engineering-manager).
**The uneven density is mostly harmless** — management and UX sets genuinely have no tool
names to cite. What is inconsistent is the *form*:

- `mlops-engineer.yaml` is the only file using conversational เช่น / อย่าง phrasing
  ("การ Orchestrate Workflow ด้วยเครื่องมือ**อย่าง** Airflow", "(**เช่น** MLflow)") instead of
  the bare parenthetical used everywhere else.
- Gloss length runs from 1 to 4 items.
- `cyber-security-engineer-analyst.yaml` `secure-protocols` spells it `IPSEC`; canonical is `IPsec`.

Proposed rule: gloss when the set is anchored by named tools or standards (2–3
representative names), or when the Thai is a translation whose English term is what
practitioners actually recognise. Never เช่น/อย่าง. Never more than 3 items. English proper
nouns spelled canonically.

---

## 3. Answerability backlog — deferred, not fixed

Each set becomes exactly one Skill Assessment question. These sets bundle things a
respondent could plausibly be expert in one of and ignorant of the other, so a single
self-rating carries no information.

**Deliberately not acted on in this pass**: splitting them changes set counts, and every
file was just brought inside the 15–20 band that ADR-0003 decision 2 and issue #7 require.
This is follow-up work, not a defect to fix in place.

| File | Set | Why one rating is meaningless |
| --- | --- | --- |
| `bi-analyst.yaml` | `domain-analytics` | Finance + retail + healthcare + manufacturing as one rating. A respondent is experienced in at most one industry. |
| `bi-analyst.yaml` | `professional-development` | 21 nodes; portfolio and salary negotiation are unrelated skills (also §1). |
| `data-engineer.yaml` | `analytics-bi-and-ml` | BI dashboarding (Power BI, Tableau, Looker) bundled with ML and MLOps. |
| `data-engineer.yaml` | `data-pipelines` | 19 nodes; a strong Airflow engineer can honestly know nothing about reverse ETL (Census, Segment, Hightouch). |
| `product-manager.yaml` | `product-metrics-and-analytics` | 19 nodes; the gloss "(Metrics, A/B Testing, AI)" itself names three constructs. |
| `devops-engineer.yaml` | `cloud-providers` | 16 nodes mixing hyperscalers, budget hosts, frontend PaaS, and serverless runtimes. |
| `cyber-...-analyst.yaml` | `labs-and-certifications` | CTF platforms + 15 professional certifications. Holding CISSP is a credential, not a self-rated skill. |
| `ios-developer.yaml` | `swift-and-objective-c` | Many modern iOS developers are Swift-fluent and Objective-C-ignorant. |
| `software-architect.yaml` | `management-and-methodologies` | Nearly everyone knows Scrum; almost nobody knows RUP + ITIL + PRINCE2 together. |

Proposed rule if this is taken up: **if two named tools in a set would never appear on the
same CV, split the set.**

### Misfiled nodes

| File | Set | Node(s) | Note |
| --- | --- | --- | --- |
| `cyber-...-analyst.yaml` | `malware-and-threat-analysis` | `cat`, `head`, `tail`, `grep`, `dd` | Unix commands under a title promising malware analysis and digital forensics. Natural home is `command-line-and-analysis-tools`. |
| `machine-learning-engineer.yaml` | `cnn-and-computer-vision` | `recommendation-systems` | `ai-engineer.yaml` files recsys under embeddings, which is the more natural home. |
| `machine-learning-engineer.yaml` | `ml-frameworks` | data-loading, tuning, prediction | Title promises frameworks; half the nodes are workflow steps. |
| `cyber-...-analyst.yaml` | `it-fundamentals` | MS Office, Google Suite, basic networking | Title promises "ไอทีและฮาร์ดแวร์"; under-covers the nodes. |

---

## 4. Ranked wording candidates

Severity is the reviewing model's, not measured. Entries marked *(uncertain)* were
self-flagged as low-confidence.

| # | File · Set | Objection | Suggested |
| --- | --- | --- | --- |
| 1 | devsecops · `security-testing-tools` | ทดสอบทะลุระบบ | ทดสอบเจาะระบบ |
| 2 | data-engineer · `containers-and-orchestration` | การจัดการคลัสเตอร์ mistranslates orchestration | การจัดการคอนเทนเนอร์ |
| 3 | cyber · `frameworks-and-standards` | กรอบมาตรฐานภัยคุกคาม garbled | เฟรมเวิร์กวิเคราะห์ภัยคุกคามและมาตรฐานการกำกับดูแล |
| 4 | engineering-manager · `culture-and-inclusion` | ความครอบคลุม ≠ inclusion | สภาพแวดล้อมที่เปิดกว้างสำหรับทุกคน, or keep `Inclusion` bare |
| 5 | devops · `secret-management` | การจัดการความลับ reads as personal secrets | การจัดการ Secrets และข้อมูลอ่อนไหว |
| 6 | mlops · `infrastructure-as-code` | การจัดการ Infrastructure เป็นโค้ด awkward | การจัดการโครงสร้างพื้นฐานด้วยโค้ด (matches backend/data-engineer) |
| 7 | mlops · `workflow-orchestration` | conversational ด้วยเครื่องมืออย่าง Airflow | การทำ Workflow Orchestration (Airflow) |
| 8 | mlops · `experiment-tracking` | conversational (เช่น MLflow) | การติดตามผลการทดลองและ Model Registry (MLflow) |
| 9 | ios · `ci-cd-and-distribution` | no separator — parses as "the CI/CD version-control system" | ระบบควบคุมเวอร์ชัน, CI/CD และการเผยแพร่แอปบน App Store |
| 10 | ios · `reactive-programming` | การเขียนโปรแกรมเชิงปฏิกิริยา textbook-literal | Reactive Programming (Combine, RxSwift) |
| 11 | software-architect · `programming-languages` | "ที่สถาปนิกซอฟต์แวร์**ควรรู้**" — only prescriptive title in the catalog; respondent is rating self, not being told what to learn | ภาษาโปรแกรมสำหรับงานสถาปัตยกรรมซอฟต์แวร์ |
| 12 | software-architect · file-wide | สถาปนิกซอฟต์แวร์ vs "Software Architect" in the same file | pick one |
| 13 | qa · `accessibility-testing` | การทดสอบการเข้าถึงได้สำหรับทุกคน wordy | การทดสอบการเข้าถึง (Accessibility) |
| 14 | frontend · `html-and-accessibility` | "HTML Semantic" word order reversed; SEO in the English title and nodes but dropped from the Thai | Semantic HTML, ฟอร์ม, Accessibility และพื้นฐาน SEO |
| 15 | server-side-game · `cloud-and-deployment` | การดีพลอยระบบ transliterated where catalog uses Latin `Deploy` | คลาวด์และการ Deploy ระบบ |
| 16 | server-side-game · `transport-mechanics` | missing connector — "กลไกความน่าเชื่อถือ Flow Control" parses as one phrase | กลไก Reliability, Flow Control และ Congestion Control |
| 17 | cyber · `it-fundamentals` | title promises hardware, nodes include Office suites | ทักษะพื้นฐานด้านไอที (ฮาร์ดแวร์ โปรแกรมสำนักงาน เครือข่ายเบื้องต้น) |
| 18 | cyber · `secure-protocols` | `IPSEC` → `IPsec`; set mixes secure and insecure protocols (FTP, RDP) under "การรับส่งข้อมูลอย่างปลอดภัย" | โปรโตคอลเครือข่ายและการรับส่งข้อมูลอย่างปลอดภัย |
| 19 | cyber · `labs-and-certifications` | สนามฝึก reads like a military training ground | แล็บฝึกปฏิบัติ / แพลตฟอร์มฝึก CTF |
| 20 | developer-relations · `metrics-and-analytics` | ผู้มีส่วนได้ส่วนเสีย where peer roles keep `Stakeholder` | Stakeholder |
| 21 | full-stack · `javascript-and-interactivity` | ความโต้ตอบ stilted | JavaScript และการทำให้หน้าเว็บโต้ตอบได้ |
| 22 | data-analyst · `distributions` | การแจกแจงของข้อมูลและรูปร่างการแจกแจง repeats การแจกแจง; no gloss where siblings have one | การแจกแจงของข้อมูล (Skewness, Kurtosis) |
| 23 | backend · `containers-and-virtualization` | English `Virtualization` vs cyber's เวอร์ชวลไลเซชัน | pick one |
| 24 | postgresql · `automation` | English `Configuration Management` vs devops's Thai | pick one |
| 25 | server-side-game · `ai-and-data-processing` | grab-bag tail set (cloud ML + TensorFlow/PyTorch + Spark) for a game-server role | consider dropping, or ความรู้เสริมด้าน AI และการประมวลผลข้อมูล |
| 26 | software-architect · `collaboration-tools`, `enterprise-software` | self-rating "Slack/Trello skill" is near-contentless; SAP and Salesforce expertise never co-occur | roadmap tails — accept, or cut |
| 27 | ai-engineer · `pre-trained-models` | โมเดลสำเร็จรูป reads as "off-the-shelf models"; gloss doing the real work | *(uncertain)* |
| 28 | developer-relations · `thought-leadership` | การสร้างชื่อเสียงในวงการ closer to "becoming famous"; nodes also include stray open-source and continuous-learning | การเป็น Thought Leader และการสร้างแบรนด์ส่วนตัว *(uncertain)* |

---

## 5. `ai-data-scientist.yaml` needs re-authoring, not a wording pass

8 sets of exactly 1 node each — `machine-learning` is a single set. Mechanically valid and
inside no rule it breaks, but respondents on this role get a far coarser assessment than
every other role. The cause is upstream: the role has only 8 imported roadmap node slugs
(`full-stack-developer` has 37, `mlops-engineer` 32; the median role has ~130). The 15–20
band in ADR-0003 is unreachable without either a richer roadmap import or hand-authored
sets that are not roadmap-derived.

---

## Method

Reviewed by an LLM pass over all 26 files with the format contract (`README.md`), project
vocabulary (`CONTEXT.md`), and the reference file (`backend-developer.yaml`) in context.
Mechanical properties were excluded from the brief because they are already enforced:
`validate_topic_set_catalog --strict` passes, every node slug resolves, no slug appears in
two sets of a role, and `display_order` is contiguous in all 26 files.

The reviewing model's Thai-language quality is not independently established. Nineteen of
its quoted Thai strings were verified verbatim against the files; its *judgements* about
that Thai were not, and cannot be by another agent — that is what the human gate is for.
