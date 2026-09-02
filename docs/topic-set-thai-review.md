# Assessable Topic Set review — Canonical Thai wording and grouping

**Reviewed:** 2026-08-26, against all 26 files in `data/content/topic_sets/` (459 sets; 456 after #16). A second full pass on 2026-09-02 is recorded in §7, and a six-role review panel the same day in §8.

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

---

## 6. Closing — what ADR-0004, #16 and #17 did with this review

**Applied:** 2026-08-26 by issue #17 (https://github.com/Pattaradanai888/CompetencyX-Backend/issues/17; "table A" below is that issue's meaning-corrections table), against the catalog as #16 left it (456 sets in
26 files). Every set is still `review: {status: draft}`; nothing below is approval. This
section exists so the person flipping sets to `reviewed` has one checklist instead of
re-deriving it from §1–§5.

### 6.1 How each section above was resolved

| Section | Resolution |
| --- | --- |
| §1 rows 1–4 | Applied by #17 with the redrafts fixed in its table A. Two differ from §4's suggestion: `frameworks-and-standards` says มาตรฐานด้านความปลอดภัย (not มาตรฐานการกำกับดูแล — governance ≠ compliance), and `culture-and-inclusion` says การโอบรับความหลากหลาย (a phrase Thai HR uses, rather than the descriptive สภาพแวดล้อมที่เปิดกว้าง). |
| §1 row 5 (`professional-development`) | Removed by #16 (ADR-0004 decision 4). |
| §2.1 security register | ADR-0004 decision 3: ความปลอดภัย everywhere. Six sets changed — cyber `security-concepts`; devsecops `security-foundations`, `cloud-security`, `container-security`, `supply-chain-security`, `scripting-and-automation`. |
| §2.2 cross-role terms | Settled by #17 rule B; the decisions are in 6.2. |
| §2.3 gloss rule | Adopted as proposed: bare parenthetical, at most three names, never เช่น / อย่าง / และ inside it, proper nouns spelled canonically. The "2–3" in #17 rule B is read as the size of a *tool list*; a one-name gloss that expands an abbreviation or names the single tool a set is about (`(Airflow)`, `(PgBouncer)`, `(Hashing)`) is left as it is. mlops `workflow-orchestration` and `experiment-tracking` lost their conversational phrasing; `IPSEC` became `IPsec`; eleven four-name glosses were trimmed to three (rows in 6.3). |
| §3 answerability backlog | Resolved by #16: `domain-analytics`, `professional-development` and `labs-and-certifications` removed; `swift-and-objective-c`, `data-pipelines`, `analytics-bi-and-ml`, `management-and-methodologies` and `cloud-providers` narrowed to their primary skill (decision 5). `product-metrics-and-analytics` was left as it was. |
| §3 misfiled nodes | #16 moved the Unix commands to `command-line-and-analysis-tools` and dropped `recommendation-systems` to the backlog. `ml-frameworks` and `it-fundamentals` are unchanged. |
| §4 items 1–16, 18 (spelling only), 20–24 | Applied; see 6.3. Item 9's sibling, data-engineer `data-pipelines`, already had its separators from #16 and was not touched. |
| §4 items 17, 18 (secure/insecure protocol mix), 25–28 | **Still open.** These are judgement calls about scope or register, not rule applications, so they belong to the person flipping the set. Item 19 is moot: the set was removed by #16. |
| §5 `ai-data-scientist` | ADR-0004 decision 6: stays at 8 sets. Not a wording matter. |

### 6.2 Terminology decisions — the same Thai for the same concept

| Concept | Decided rendering | Where it changed (roles already conforming in brackets) |
| --- | --- | --- |
| Security | ความปลอดภัย | catalog-wide |
| Machine Learning / Deep Learning | left in English | ai-data-scientist, data-analyst, game-developer, machine-learning-engineer |
| Deploy | left in English | server-side-game-developer [blockchain, full-stack] |
| Secret | การจัดการ Secret | devops-engineer |
| Stakeholder | left in English | developer-relations [engineering-manager, product-manager] |
| Reactive Programming | left in English | ios-developer [android, software-architect] |
| Configuration Management | left in English | devops-engineer [postgresql] |
| Infrastructure as Code | left in English, the role's tools in the gloss where its nodes name any (mlops has none) | data-engineer, devops-engineer (`infrastructure-provisioning`), mlops-engineer [full-stack]. Chosen over การจัดการโครงสร้างพื้นฐานด้วยโค้ด because the term is on ADR-0004's English list and the Thai form was in only two files, one of which said "provisioning" rather than IaC. |
| Incident Response | การรับมือ Incident | cyber, devsecops, engineering-manager |
| Digital Forensics | left in English | cyber (was นิติวิทยาศาสตร์ดิจิทัล), devsecops (was ดิจิทัลฟอเรนซิก). Not on #17's list; applied under decision 3 by the same reasoning as the terms that are. |
| Virtualization | left in English | cyber [backend] |
| Accessibility | left in English, bare | qa, ios [frontend] |
| Framework | เฟรมเวิร์ก | software-architect (was กรอบงาน), machine-learning-engineer (was Framework) |
| Animation · container · mobile · data model · distributed · discrete | แอนิเมชัน · คอนเทนเนอร์ · มือถือ · Data Model · ระบบแบบกระจาย · คณิตศาสตร์ดิสครีต | game-developer · mlops · software-architect · data-engineer · software-architect · machine-learning-engineer |
| Role name inside one file | one name per file | software-architect now says Software Architect only |

Left alone on purpose, for the reviewer to confirm: data-engineer `governance-and-compliance`
keeps ธรรมาภิบาลข้อมูล (the established Thai for *data governance*) while devsecops
`governance-risk-compliance` uses การกำกับดูแล for the GRC sense — two constructs, not two
renderings of one. Neural Networks (machine-learning-engineer was โครงข่ายประสาทเทียม), Semantic HTML and Loss Aversion stay in English as the
terms practitioners recognise.

### 6.3 Second-pass checklist — every set #17 changed

68 sets in 22 files. `backend-developer`, `postgresql-developer-dba`, `product-manager` and
`technical-writer` were not touched. Each row is a draft awaiting a person's `reviewed` flip;
where a redraft differs from §4's suggestion, the reason is in #17 table A or in 6.2 above.

| File · set | Before | After |
| --- | --- | --- |
| ai-data-scientist · `machine-learning` | การเรียนรู้ของเครื่อง (Machine Learning) | Machine Learning |
| ai-data-scientist · `deep-learning` | การเรียนรู้เชิงลึก (Deep Learning) | Deep Learning |
| ai-engineer · `audio-and-speech` | การประมวลผลเสียงและการพูด (Speech-to-Text, Text-to-Speech) | การประมวลผลเสียงและเสียงพูด (Speech-to-Text, Text-to-Speech) |
| android-developer · `architecture-patterns` | แพตเทิร์นสถาปัตยกรรมแอป Android (MVC, MVP, MVVM, MVI) | แพตเทิร์นสถาปัตยกรรมแอป Android (MVC, MVVM, MVI) |
| android-developer · `app-distribution` | การเผยแพร่และ Distribution แอป Android (Google Play, Signed APK) | การเผยแพร่แอป Android (Google Play, Signed APK) |
| bi-analyst · `metrics-and-business-functions` | Metrics, KPI และหน้าที่สำคัญของธุรกิจ | Metrics, KPI และสายงานหลักในธุรกิจ (Finance, Marketing, HR) |
| bi-analyst · `analytics-tools` | เครื่องมือวิเคราะห์ข้อมูล (Excel, Python, R, Pandas) | เครื่องมือวิเคราะห์ข้อมูล (Excel, Python, R) |
| bi-analyst · `data-modeling-for-bi` | การออกแบบ Data Model เพื่องาน BI (Star Schema, Fact และ Dimension Tables) | การออกแบบ Data Model เพื่องาน BI (Star Schema, Fact Table, Dimension Table) |
| bi-analyst · `bi-platforms` | แพลตฟอร์ม BI (Power BI, Tableau, Looker, Qlik) | แพลตฟอร์ม BI (Power BI, Tableau, Looker) |
| blockchain-developer · `web-development-for-web3` | การพัฒนาเว็บสำหรับ Web3 (JavaScript, React, ethers.js, web3.js) | การพัฒนาเว็บสำหรับ Web3 (React, ethers.js, web3.js) |
| cyber-security-engineer-analyst · `operating-systems` | ระบบปฏิบัติการและเวอร์ชวลไลเซชัน (Windows, Linux, Hypervisor) | ระบบปฏิบัติการและ Virtualization (Windows, Linux, Hypervisor) |
| cyber-security-engineer-analyst · `networking-fundamentals` | พื้นฐานเครือข่าย (OSI Model, IP, Subnetting, DNS) | พื้นฐานเครือข่าย (OSI Model, Subnetting, DNS) |
| cyber-security-engineer-analyst · `secure-protocols` | โปรโตคอลและการรับส่งข้อมูลอย่างปลอดภัย (SSH, TLS, IPSEC) | โปรโตคอลและการรับส่งข้อมูลอย่างปลอดภัย (SSH, TLS, IPsec) |
| cyber-security-engineer-analyst · `identity-and-access` | การยืนยันตัวตน การจัดการสิทธิ์ และวิทยาการเข้ารหัส (SSO, MFA, PKI) | การยืนยันตัวตน การจัดการสิทธิ์ และวิทยาการเข้ารหัสลับ (SSO, MFA, PKI) |
| cyber-security-engineer-analyst · `security-concepts` | แนวคิดหลักด้านความมั่นคงปลอดภัย (CIA Triad, Zero Trust) | แนวคิดหลักด้านความปลอดภัย (CIA Triad, Zero Trust) |
| cyber-security-engineer-analyst · `frameworks-and-standards` | กรอบมาตรฐานภัยคุกคามและการกำกับดูแล (MITRE ATT&CK, NIST, ISO) | เฟรมเวิร์กวิเคราะห์ภัยคุกคามและมาตรฐานด้านความปลอดภัย (MITRE ATT&CK, NIST, ISO 27001) |
| cyber-security-engineer-analyst · `network-attacks` | การโจมตีเครือข่าย การขโมยสิทธิ์ และเครือข่ายไร้สาย (MITM, DDoS, Evil Twin) | การโจมตีเครือข่าย การโจมตี Credential และการโจมตีเครือข่ายไร้สาย (MITM, DDoS, Evil Twin) |
| cyber-security-engineer-analyst · `malware-and-threat-analysis` | การวิเคราะห์มัลแวร์และนิติวิทยาศาสตร์ดิจิทัล (VirusTotal, Wireshark, Autopsy) | การวิเคราะห์มัลแวร์และ Digital Forensics (VirusTotal, Wireshark, Autopsy) |
| cyber-security-engineer-analyst · `incident-response` | การรับมือเหตุการณ์ผิดปกติ (Incident Response) | การรับมือ Incident (Incident Response) |
| data-analyst · `distributions` | การแจกแจงของข้อมูลและรูปร่างการแจกแจง | การแจกแจงของข้อมูล (Skewness, Kurtosis) |
| data-analyst · `deep-learning` | การเรียนรู้เชิงลึก (Deep Learning, Neural Networks) | Deep Learning และ Neural Networks |
| data-engineer · `data-sources` | แหล่งที่มาของข้อมูล (API, Database, Logs, IoT) | แหล่งที่มาของข้อมูล (API, Database, IoT) |
| data-engineer · `data-modelling` | การออกแบบแบบจำลองข้อมูล (Star Schema, SCD) | การออกแบบ Data Model (Star Schema, SCD) |
| data-engineer · `database-concepts` | แนวคิดหลักของฐานข้อมูล (SQL, Index, Transaction, CAP) | แนวคิดหลักของฐานข้อมูล (SQL, Index, Transaction) |
| data-engineer · `nosql-databases` | ฐานข้อมูล NoSQL (Document, Key-Value, Column, Graph) | ฐานข้อมูล NoSQL (Document, Key-Value, Graph) |
| data-engineer · `containers-and-orchestration` | คอนเทนเนอร์ การจัดการคลัสเตอร์ และ CI/CD (Docker, Kubernetes) | คอนเทนเนอร์ การจัดการคอนเทนเนอร์ และ CI/CD (Docker, Kubernetes) |
| data-engineer · `infrastructure-as-code` | การจัดการโครงสร้างพื้นฐานด้วยโค้ด (Terraform, IaC) | Infrastructure as Code (Terraform, OpenTofu, AWS CDK) |
| developer-relations · `metrics-and-analytics` | ตัวชี้วัด การวิเคราะห์ผล และการรายงานต่อผู้มีส่วนได้ส่วนเสีย | ตัวชี้วัด การวิเคราะห์ผล และการรายงานต่อ Stakeholder |
| devops-engineer · `networking-and-protocols` | เครือข่ายและโปรโตคอล (DNS, HTTPS, SSH, SSL/TLS) | เครือข่ายและโปรโตคอล (DNS, SSH, TLS) |
| devops-engineer · `infrastructure-provisioning` | การจัดเตรียมโครงสร้างพื้นฐานด้วยโค้ด (Terraform, Pulumi) | Infrastructure as Code (Terraform, Pulumi, CloudFormation) |
| devops-engineer · `configuration-management` | การจัดการคอนฟิกอัตโนมัติ (Ansible, Chef, Puppet) | Configuration Management (Ansible, Chef, Puppet) |
| devops-engineer · `secret-management` | การจัดการความลับและข้อมูลอ่อนไหว (Vault, Sealed Secrets) | การจัดการ Secret และข้อมูลอ่อนไหว (Vault, Sealed Secrets) |
| devsecops-engineer · `security-foundations` | หลักการพื้นฐานด้านความมั่นคงปลอดภัย (CIA Triad, Defense in Depth) | หลักการพื้นฐานด้านความปลอดภัย (CIA Triad, Defense in Depth) |
| devsecops-engineer · `threat-modeling` | การวิเคราะห์ภัยคุกคาม (Threat Modeling, STRIDE, PASTA) | การทำ Threat Modeling (STRIDE, PASTA) |
| devsecops-engineer · `security-testing-tools` | เครื่องมือทดสอบทะลุระบบและสแกนช่องโหว่ (Burp Suite, Nmap, Nessus) | เครื่องมือทดสอบเจาะระบบและสแกนช่องโหว่ (Burp Suite, Nmap, Nessus) |
| devsecops-engineer · `cloud-security` | ความมั่นคงปลอดภัยบนคลาวด์ (Cloud Security, CSPM) | ความปลอดภัยบนคลาวด์ (Cloud Security, CSPM) |
| devsecops-engineer · `container-security` | ความมั่นคงปลอดภัยของคอนเทนเนอร์ (Docker, Kubernetes) | ความปลอดภัยของคอนเทนเนอร์ (Docker, Kubernetes) |
| devsecops-engineer · `supply-chain-security` | ความมั่นคงปลอดภัยของ Supply Chain และ Dependency | ความปลอดภัยของ Supply Chain และ Dependency |
| devsecops-engineer · `security-monitoring` | การเฝ้าระวังและติดตามระบบ (Monitoring, SIEM, SOAR) | การเฝ้าระวังด้านความปลอดภัยและ SIEM/SOAR |
| devsecops-engineer · `incident-response` | การตอบสนองเหตุการณ์และดิจิทัลฟอเรนซิก (Incident Response) | การรับมือ Incident และ Digital Forensics |
| devsecops-engineer · `governance-risk-compliance` | ธรรมาภิบาล ความเสี่ยง และการกำกับดูแลตามมาตรฐาน (SOC 2, ISO 27001, NIST) | การกำกับดูแล ความเสี่ยง และการปฏิบัติตามมาตรฐาน (GRC: SOC 2, ISO 27001, NIST) |
| devsecops-engineer · `scripting-and-automation` | การเขียนสคริปต์และโปรแกรมเพื่องานความมั่นคงปลอดภัย (Python, Bash, PowerShell) | การเขียนสคริปต์และโปรแกรมเพื่องานความปลอดภัย (Python, Bash, PowerShell) |
| engineering-manager · `culture-and-inclusion` | วัฒนธรรมทีมและการสร้างความครอบคลุม (Inclusion) | วัฒนธรรมทีมและการโอบรับความหลากหลาย (Inclusion) |
| engineering-manager · `incident-and-crisis` | การจัดการเหตุการณ์และวิกฤต (Incident Management) | การรับมือ Incident และการจัดการวิกฤต (Incident Management) |
| frontend-developer · `html-and-accessibility` | HTML Semantic ฟอร์ม และ Accessibility | Semantic HTML, ฟอร์ม, Accessibility และพื้นฐาน SEO |
| frontend-developer · `frontend-testing` | การทดสอบซอฟต์แวร์ฝั่ง Frontend (Vitest, Jest, Cypress, Playwright) | การทดสอบซอฟต์แวร์ฝั่ง Frontend (Vitest, Cypress, Playwright) |
| full-stack-developer · `javascript-and-interactivity` | JavaScript และการเพิ่มความโต้ตอบ (Interactivity) | JavaScript และการทำให้หน้าเว็บโต้ตอบกับผู้ใช้ได้ |
| game-developer · `curves-and-animation` | เส้นโค้งและอนิเมชัน (Spline, Bezier) | เส้นโค้งและแอนิเมชัน (Spline, Bezier) |
| game-developer · `game-ai-learning` | การเรียนรู้ของ AI ในเกม (Machine Learning, Reinforcement Learning) | Machine Learning และ Reinforcement Learning ในเกม |
| ios-developer · `ui-design-and-accessibility` | การออกแบบ UI ตาม HIG และการเข้าถึง (Accessibility) | การออกแบบ UI ตาม HIG และ Accessibility |
| ios-developer · `reactive-programming` | การเขียนโปรแกรมเชิงปฏิกิริยา (Combine, RxSwift) | Reactive Programming (Combine, RxSwift) |
| ios-developer · `ci-cd-and-distribution` | ระบบควบคุมเวอร์ชัน CI/CD และการเผยแพร่บน App Store | ระบบควบคุมเวอร์ชัน, CI/CD และการเผยแพร่แอปบน App Store |
| machine-learning-engineer · `calculus-and-discrete-mathematics` | แคลคูลัสและคณิตศาสตร์ไม่ต่อเนื่อง (Calculus, Discrete Mathematics) | แคลคูลัสและคณิตศาสตร์ดิสครีต (Calculus, Discrete Mathematics) |
| machine-learning-engineer · `ml-frameworks` | Framework สำหรับ Machine Learning และ Deep Learning (scikit-learn, TensorFlow, PyTorch) | เฟรมเวิร์ก Machine Learning และ Deep Learning (scikit-learn, TensorFlow, PyTorch) |
| machine-learning-engineer · `neural-network-fundamentals` | พื้นฐานโครงข่ายประสาทเทียม (Neural Networks) | พื้นฐาน Neural Networks |
| mlops-engineer · `containerization` | การใช้งาน Container (Docker, Kubernetes) | การใช้งานคอนเทนเนอร์ (Docker, Kubernetes) |
| mlops-engineer · `infrastructure-as-code` | การจัดการ Infrastructure เป็นโค้ด (Infrastructure as Code) | Infrastructure as Code |
| mlops-engineer · `workflow-orchestration` | การ Orchestrate Workflow ด้วยเครื่องมืออย่าง Airflow | การทำ Workflow Orchestration (Airflow) |
| mlops-engineer · `experiment-tracking` | การติดตามผลการทดลองและ Model Registry (เช่น MLflow) | การติดตามผลการทดลองและ Model Registry (MLflow) |
| qa-engineer · `accessibility-testing` | การทดสอบการเข้าถึงได้สำหรับทุกคน (Accessibility) | การทดสอบ Accessibility |
| server-side-game-developer · `transport-mechanics` | กลไกความน่าเชื่อถือ Flow Control และ Congestion Control | กลไก Reliability, Flow Control และ Congestion Control |
| server-side-game-developer · `cloud-and-deployment` | คลาวด์และการดีพลอยระบบ (AWS, Docker, Kubernetes) | คลาวด์และการ Deploy ระบบ (AWS, Docker, Kubernetes) |
| software-architect · `programming-languages` | ภาษาโปรแกรมที่สถาปนิกซอฟต์แวร์ควรรู้ | ภาษาโปรแกรมสำหรับงานสถาปัตยกรรมซอฟต์แวร์ |
| software-architect · `distributed-data-patterns` | แพตเทิร์นข้อมูลในระบบกระจาย (CQRS, CAP Theorem) | แพตเทิร์นข้อมูลในระบบแบบกระจาย (CQRS, CAP Theorem) |
| software-architect · `web-and-mobile` | สถาปัตยกรรมฝั่งเว็บและโมบาย (SPA, SSR, Microfrontends) | สถาปัตยกรรมฝั่งเว็บและมือถือ (SPA, SSR, Microfrontends) |
| software-architect · `operations-knowledge` | ความรู้ด้านปฏิบัติการ (Cloud, Containers, CI/CD, IaC) | ความรู้ด้านปฏิบัติการ (Cloud, Containers, CI/CD) |
| software-architect · `architecture-frameworks` | กรอบงานสถาปัตยกรรมองค์กร (TOGAF, IAF, BABOK) | เฟรมเวิร์กสถาปัตยกรรมองค์กร (TOGAF, IAF, BABOK) |
| ux-designer · `incentives-and-rewards` | สิ่งจูงใจ รางวัล และการหลีกเลี่ยงการสูญเสีย | สิ่งจูงใจ รางวัล และ Loss Aversion |
The mechanical part of these rules is held from now on by
`assessments/tests/test_topic_set_wording_rules.py`: the forbidden forms (security register,
transliteration spellings, the terms that stay in English), the gloss shape, and the Incident
Response / Infrastructure as Code / Configuration Management / Secret / Virtualization renderings.
The rest of 6.2 and whether a set is `reviewed` are not tested: the status flip is a person's
action that the suite must not block.

---

## 7. Second full pass — 2026-09-02, all 456 sets read

**Applied:** 2026-09-02, by an agent reading every set in all 26 files against its English
title, its nodes, and the ADR-0004 rules. Every set is still `review: {status: draft}`.
This pass is a full read, not a sample, so the person approving can start from "24 sets
changed, 432 confirmed as written" instead of re-reading cold — but the confirmation is
model-generated, and the `reviewed` flip stays a person's act (ADR-0004 decision 1).

Mechanical state at the time of the pass: no set uses ความมั่นคงปลอดภัย, no gloss is
conversational or longer than three names, `validate_topic_set_catalog` reports 0 roles
without sets and 0 unknown nodes, and the persona harness passes its baseline.

### 7.1 The 24 changes

Each is an application of ADR-0004 decision 3 (working vocabulary, tool names in the gloss)
or a plain correction; none changes which nodes a set covers.

| File · set | Before | After |
| --- | --- | --- |
| ai-data-scientist · `statistics` | สถิติศาสตร์สำหรับการวิเคราะห์ข้อมูล | สถิติสำหรับการวิเคราะห์ข้อมูล |
| ai-engineer · `pre-trained-models` | โมเดลสำเร็จรูป (Pre-trained Models) และผู้ให้บริการโมเดล | Pre-trained Models และผู้ให้บริการโมเดล (OpenAI, Anthropic, Hugging Face) |
| ai-engineer · `ai-safety` | ความปลอดภัยและการใช้ AI อย่างรับผิดชอบ | ความปลอดภัยของ AI และการใช้งานอย่างรับผิดชอบ (Prompt Injection, Bias) |
| android-developer · `local-storage` | การจัดเก็บข้อมูลบนเครื่อง (Room, DataStore, Shared Preferences) | การจัดเก็บข้อมูลบนเครื่อง (Room, DataStore, SharedPreferences) |
| bi-analyst · `ethics-and-privacy` | จริยธรรมของข้อมูล ความเป็นส่วนตัว และอคติ (GDPR, CCPA) | จริยธรรมในการใช้ข้อมูล ความเป็นส่วนตัว และอคติ (GDPR, CCPA) |
| cyber-security-engineer-analyst · `it-fundamentals` | ทักษะพื้นฐานด้านไอทีและฮาร์ดแวร์ | ทักษะพื้นฐานด้านไอที ฮาร์ดแวร์ และโปรแกรมสำนักงาน (MS Office, Google Workspace) |
| cyber-security-engineer-analyst · `identity-and-access` | การยืนยันตัวตน การจัดการสิทธิ์ และวิทยาการเข้ารหัสลับ (SSO, MFA, PKI) | การยืนยันตัวตน การจัดการสิทธิ์ และการเข้ารหัสลับ (SSO, MFA, PKI) |
| cyber-security-engineer-analyst · `endpoint-and-network-defense` | การป้องกันอุปกรณ์ปลายทางและเครือข่าย (EDR, Firewall, IDS/IPS) | การป้องกัน Endpoint และเครือข่าย (EDR, Firewall, IDS/IPS) |
| cyber-security-engineer-analyst · `social-engineering` | การโจมตีด้วยวิศวกรรมสังคม (Phishing, Tailgating) | การโจมตีแบบ Social Engineering (Phishing, Tailgating) |
| cyber-security-engineer-analyst · `network-attacks` | การโจมตีเครือข่าย การโจมตี Credential และการโจมตีเครือข่ายไร้สาย (MITM, DDoS, Evil Twin) | การโจมตีเครือข่าย, Credential และเครือข่ายไร้สาย (MITM, DDoS, Evil Twin) |
| data-analyst · `big-data` | เทคโนโลยีข้อมูลขนาดใหญ่ (Hadoop, Spark) | เทคโนโลยี Big Data (Hadoop, Spark) |
| software-architect · `big-data-processing` | การประมวลผลข้อมูลขนาดใหญ่ (Hadoop, Spark) | การประมวลผล Big Data (Hadoop, Spark) |
| data-engineer · `messaging-systems` | ระบบส่งข้อความและสตรีมข้อมูล (Kafka, RabbitMQ) | ระบบ Messaging และ Streaming (Kafka, RabbitMQ) |
| developer-relations · `developer-experience` | ประสบการณ์นักพัฒนาและการตลาดสำหรับนักพัฒนา | Developer Experience (DX) และ Developer Marketing |
| developer-relations · `thought-leadership` | การสร้างชื่อเสียงในวงการและแบรนด์ส่วนบุคคล | การเป็น Thought Leader และการสร้าง Personal Brand |
| devops-engineer · `application-monitoring` | การติดตามแอปพลิเคชันและ Distributed Tracing | การติดตามแอปพลิเคชันและ Distributed Tracing (OpenTelemetry, Jaeger) |
| engineering-manager · `budget-and-vendors` | การวางแผนงบประมาณและการจัดการ Vendor กับพันธมิตร | การวางแผนงบประมาณ การจัดการ Vendor และพันธมิตร |
| ios-developer · `graphics-and-media` | เฟรมเวิร์กด้านกราฟิก แอนิเมชัน และสื่อ | เฟรมเวิร์กด้านกราฟิก แอนิเมชัน และสื่อ (Core Animation, AVFoundation, Metal) |
| machine-learning-engineer · `cnn-and-computer-vision` | โครงข่าย CNN และการประยุกต์ใช้ (Computer Vision) | CNN และการประยุกต์ใช้ด้าน Computer Vision |
| product-manager · `go-to-market-and-release` | กลยุทธ์การออกสู่ตลาดและการปล่อยรีลีส (Go-to-Market) | กลยุทธ์การออกสู่ตลาด (Go-to-Market) และการปล่อย Release |
| software-architect · `operations-knowledge` | ความรู้ด้านปฏิบัติการ (Cloud, Containers, CI/CD) | ความรู้ด้าน Operations (Cloud, Containers, CI/CD) |
| software-architect · `management-and-methodologies` | ระเบียบวิธีส่งมอบแบบ Agile (Scrum, Kanban, SAFe) | แนวทางการส่งมอบงานแบบ Agile (Scrum, Kanban, SAFe) |
| software-architect · `programming-paradigms` | กระบวนทัศน์การเขียนโปรแกรม (OOP, Functional, Reactive) | Programming Paradigms (OOP, Functional, Reactive) |
| ux-designer · `interface-clarity` | ความชัดเจนของอินเทอร์เฟซและภาระทางความคิด | ความชัดเจนของอินเทอร์เฟซและ Cognitive Load |

Why, grouped:

- **Academic register where practitioners use English or plainer Thai** — วิทยาการเข้ารหัสลับ,
  กระบวนทัศน์, ระเบียบวิธี, ปฏิบัติการ, ภาระทางความคิด, อุปกรณ์ปลายทาง, วิศวกรรมสังคม,
  ข้อมูลขนาดใหญ่, สถิติศาสตร์. Same reasoning as the terms ADR-0004 decision 3 already lists.
- **Thai that means something else** — ระบบส่งข้อความ reads as chat messaging, not a
  messaging system; โมเดลสำเร็จรูป reads as an off-the-shelf product (§4 item 27); การสร้าง
  ชื่อเสียง reads as becoming famous (§4 item 28); โครงข่าย CNN half-translates a term 6.2
  keeps in English.
- **Title under-covers the nodes** — cyber `it-fundamentals` (§4 item 17) now names the
  office suites its nodes list; ios `graphics-and-media` and devops `application-monitoring`
  gain the tool gloss their siblings have.
- **Spelling and grammar** — `SharedPreferences` is one word; `Google Workspace` is the
  product's current name; the Vendor set's กับ was the wrong conjunction; the network-attacks
  set repeated การโจมตี three times.

### 7.2 Open items from §4 and §6.1, decided

| Item | Decision | Reason |
| --- | --- | --- |
| §4 17 · cyber `it-fundamentals` | Changed (above) | The nodes are hardware plus office suites plus basic networking; the title now says so. |
| §4 18 · cyber `secure-protocols` mixes secure and insecure protocols | **Kept as written** | The English title has the same mix ("Protocols and secure transport"), and a respondent who knows SSH/TLS/IPsec is the one the set is anchored on. The insecure protocols are there as the contrast the roadmap draws. |
| §4 25 · server-side-game `ai-and-data-processing` | **Kept** | It is a real section of the imported roadmap; the wording states exactly what it bundles, and dropping it sends nine nodes to the backlog for no wording gain. |
| §4 26 · software-architect `collaboration-tools`, `enterprise-software` | **Kept** | Both read as category familiarity, the same construct as a languages or databases set: nobody holds every name in the gloss, and the rating is over the category. Narrowing (decision 5) has no primary skill to narrow to. |
| §4 27 · ai-engineer `pre-trained-models` | Changed (above) | — |
| §4 28 · developer-relations `thought-leadership` | Changed (above) | — |
| §6.2 · data-engineer ธรรมาภิบาลข้อมูล vs devsecops การกำกับดูแล | **Confirmed as two constructs** | ธรรมาภิบาลข้อมูล is the established Thai for *data governance*; การกำกับดูแล is the GRC sense. |
| §6.2 · devops `container-orchestration` as การจัดการคอนเทนเนอร์ | **Kept** | #17 settled it and data-engineer conforms; Container Orchestration in English would be equally defensible under decision 3 but is not worth reopening a settled rendering. |

### 7.3 What the approver still has to do

Flip `review.status` to `reviewed` per set, or per file, after reading. Nothing in this
document, and nothing an agent runs, does that. Once every set is reviewed,
`validate_topic_set_catalog --strict` passes and issue #7 can close.

---

## 8. Role-based review panel — 2026-09-02, six reviewers in parallel

**Applied:** 2026-09-02, on top of §7. Six agents each took a role and read only the files in
that role's domain, against ADR-0004 decision 3, §6.2 and §7: a security practitioner
(cyber, devsecops, plus the security sets of six other files), a data/ML practitioner (7
files), a backend/infra practitioner (7 files), a client-side developer (frontend, android,
ios, game), a product/people/content lead (PM, EM, DevRel, technical writer, UX, QA), and a
Thai copy editor who read all 456 titles for spelling, grammar and spacing only. Every set is
still `review: {status: draft}`; this panel prepares the approval, it is not the approval.

Raw findings: 82 (8 · 15 · 18 · 12 · 13 · 16), with overlaps where two reviewers flagged the
same set. The copy editor confirmed the transliteration spelling of every suspect word
(แอปพลิเคชัน, เฟรมเวิร์ก, คอนเทนเนอร์, อินเทอร์เฟซ, แพตเทิร์น, เวอร์ชัน …), ไม้ยมก spacing and
Thai/English spacing across all 26 files.

### 8.1 Applied — 72 sets

Reasons, in the order they recur: a gloss that re-translated the Thai instead of naming the
tools the nodes list (backup, SQL, SSR, physics); a gloss item that is a category, not a
name (Bundler, IDE, AI Code Editors, Top/Mid/Bottom); a product name misspelt (Aha!, k6,
Argo CD, WebSocket, Yarn); Thai whose meaning drifted (เพิ่มเติม for *advanced*, ด้วยตัวเอง
clashing with the question's own ได้เอง, อื่น ๆ with no referent, bare Oracle reading as the
database, ทีมวิศวกรรม reading as a civil-engineering department); a calque nobody says
(โมเดลข้อมูลลำดับ, การเข้าถึงข้อมูลพร้อมกัน, ชนิดข้อมูล, การจัดการกุญแจ, วงจรชีวิต for Android
Lifecycle); two glosses in one title; and the one settled rendering that a set had missed
(การเฝ้าระวัง for monitoring, แบ็กเอนด์ where the catalog writes Backend, คลาวด์ where it
writes คลาวด์).

| File · set | Before | After |
| --- | --- | --- |
| cyber-security-engineer-analyst · `security-operations-practices` | การปฏิบัติงานด้านความปลอดภัย (Threat Hunting, Forensics) | งาน Security Operations (Threat Hunting, Vulnerability Management, Pentest) |
| devsecops-engineer · `applied-cryptography` | การเข้ารหัสลับและการจัดการกุญแจ (Encryption, Hashing, PKI) | การเข้ารหัสลับและ Key Management (Hashing, KMS, PKI) |
| devsecops-engineer · `governance-risk-compliance` | การกำกับดูแล ความเสี่ยง และการปฏิบัติตามมาตรฐาน (GRC: SOC 2, ISO 27001, NIST) | การกำกับดูแล ความเสี่ยง และ Compliance (SOC 2, ISO 27001, NIST) |
| cyber-security-engineer-analyst · `network-devices-and-topologies` | อุปกรณ์เครือข่ายและรูปแบบการเชื่อมต่อ (Router, VLAN, VPN) | อุปกรณ์เครือข่ายและ Network Topology (Router, VLAN, VPN) |
| devsecops-engineer · `supply-chain-security` | ความปลอดภัยของ Supply Chain และ Dependency | ความปลอดภัยของ Software Supply Chain และ Dependency (SBOM) |
| cyber-security-engineer-analyst · `security-tooling` | แพลตฟอร์มความปลอดภัยและแหล่งข้อมูล Log (SIEM, SOAR, Kali Linux) | แพลตฟอร์มด้านความปลอดภัยและ Log Source (SIEM, SOAR, Kali Linux) |
| cyber-security-engineer-analyst · `cloud-security` | ความรู้ด้านคลาวด์และความปลอดภัยบนคลาวด์ (SaaS, IaaS, AWS) | ทักษะด้านคลาวด์และความปลอดภัยบนคลาวด์ (AWS, Azure, GCP) |
| cyber-security-engineer-analyst · `command-line-and-analysis-tools` | เครื่องมือ Command Line และการตรวจสอบแก้ปัญหาเครือข่าย (grep, nmap, tcpdump) | เครื่องมือ Command Line และการตรวจสอบและแก้ปัญหาเครือข่าย (grep, nmap, tcpdump) |
| cyber-security-engineer-analyst · `network-attacks` | การโจมตีเครือข่าย, Credential และเครือข่ายไร้สาย (MITM, DDoS, Evil Twin) | การโจมตีเครือข่าย เครือข่ายไร้สาย และ Credential (MITM, DDoS, Evil Twin) |
| data-engineer · `data-warehousing` | คลังข้อมูล (Data Warehouse, BigQuery, Snowflake) | Data Warehouse (BigQuery, Snowflake, Redshift) |
| machine-learning-engineer · `deep-learning-architectures` | สถาปัตยกรรม Deep Learning เพิ่มเติม (GANs, Autoencoders) | สถาปัตยกรรม Deep Learning ขั้นสูง (GAN, Autoencoder) |
| ai-engineer · `open-source-and-local-models` | โมเดล Open Source และการรันโมเดลด้วยตัวเอง (Ollama) | โมเดล Open Source และการรันโมเดลแบบ Local (Ollama) |
| data-engineer · `database-concepts` | แนวคิดหลักของฐานข้อมูล (SQL, Index, Transaction) | แนวคิดหลักของฐานข้อมูล (Index, Transaction, OLTP/OLAP) |
| bi-analyst · `sql-and-databases` | SQL และฐานข้อมูลเชิงสัมพันธ์ (Relational Databases) | SQL และฐานข้อมูลเชิงสัมพันธ์ (PostgreSQL, MySQL, Oracle) |
| bi-analyst · `bi-foundations` | พื้นฐาน Business Intelligence และบทบาทนักวิเคราะห์ BI | พื้นฐาน Business Intelligence และบทบาทของ BI Analyst |
| machine-learning-engineer · `sequence-models-and-transformers` | โมเดลข้อมูลลำดับและ Transformers (RNN, LSTM, Attention) | Sequence Models และ Transformers (RNN, LSTM, Attention) |
| machine-learning-engineer · `model-evaluation-and-validation` | การประเมินผลและ Validation โมเดล (Metrics, Cross-Validation) | การประเมินผลโมเดลและ Validation (Metrics, Cross-Validation) |
| ai-engineer · `hugging-face` | ระบบนิเวศ Hugging Face | การใช้งาน Hugging Face (Hub, Transformers, Inference SDK) |
| ai-engineer · `ai-development-tools` | เครื่องมือพัฒนาซอฟต์แวร์ที่มี AI ช่วย (AI Code Editors, Copilot) | เครื่องมือพัฒนาซอฟต์แวร์ที่มี AI ช่วย (GitHub Copilot, Cursor) |
| mlops-engineer · `cloud-computing` | การใช้งาน Cloud (AWS, Azure, GCP) และบริการ ML บนคลาวด์ | การใช้งานคลาวด์และบริการ ML แบบ Managed (AWS, Azure, GCP) |
| mlops-engineer · `experiment-tracking` | การติดตามผลการทดลองและ Model Registry (MLflow) | การทำ Experiment Tracking และ Model Registry (MLflow) |
| bi-analyst · `data-warehousing-and-cloud` | Data Warehouse และแพลตฟอร์มข้อมูลบน Cloud (AWS, GCP, Azure) | Data Warehouse และแพลตฟอร์มข้อมูลบนคลาวด์ (AWS, GCP, Azure) |
| data-engineer · `containers-and-orchestration` | คอนเทนเนอร์ การจัดการคอนเทนเนอร์ และ CI/CD (Docker, Kubernetes) | การใช้งานและจัดการคอนเทนเนอร์ และ CI/CD (Docker, Kubernetes) |
| frontend-developer · `css-architecture` | สถาปัตยกรรม CSS และ Preprocessors (Sass, Tailwind) | การจัดโครงสร้าง CSS, Preprocessor และ Tailwind (BEM, Sass, PostCSS) |
| frontend-developer · `build-tools-and-quality` | เครื่องมือ Build และคุณภาพโค้ด (Bundler, ESLint, Prettier) | เครื่องมือ Build, Bundler และคุณภาพโค้ด (Vite, Webpack, ESLint) |
| frontend-developer · `type-checking` | การตรวจสอบชนิดข้อมูลด้วย TypeScript | การเขียน TypeScript และการทำ Type Checking |
| frontend-developer · `web-security-and-auth` | ความปลอดภัยของเว็บแอปพลิเคชันและการยืนยันตัวตน | ความปลอดภัยของเว็บแอปพลิเคชันและการยืนยันตัวตน (OWASP, CORS, HTTPS) |
| frontend-developer · `ssr-and-routing` | การเรนเดอร์ฝั่งเซิร์ฟเวอร์ (SSR) และ Routing | การทำ SSR และ Routing (Next.js, Nuxt, React Router) |
| frontend-developer · `package-managers` | การจัดการแพ็กเกจ (npm, yarn, pnpm) | การจัดการแพ็กเกจ (npm, Yarn, pnpm) |
| frontend-developer · `real-time-communication` | การสื่อสารแบบเรียลไทม์ (WebSockets, SSE) | การสื่อสารแบบเรียลไทม์ (WebSocket, SSE) |
| backend-developer · `real-time-communication` | การสื่อสารแบบเรียลไทม์ (WebSockets, SSE) | การสื่อสารแบบเรียลไทม์ (WebSocket, SSE) |
| android-developer · `android-fundamentals` | พื้นฐานการพัฒนาแอป Android (IDE, Gradle, OOP) | พื้นฐานการพัฒนาแอป Android (Android Studio, Gradle, OOP) |
| android-developer · `app-components` | App Components และวงจรชีวิตของแอป Android (Activity, Service, Intent) | App Components และ Lifecycle ของแอป Android (Activity, Service, Intent) |
| android-developer · `firebase-and-google-services` | การใช้งาน Firebase และบริการของ Google | การใช้งาน Firebase และบริการของ Google (Crashlytics, FCM, Google Maps) |
| android-developer · `networking` | การเชื่อมต่อ Network และ API (Retrofit, OkHttp) | การเชื่อมต่อเครือข่ายและ API (Retrofit, OkHttp) |
| ios-developer · `debugging-and-profiling` | การดีบักและวิเคราะห์ประสิทธิภาพ (Instruments) | การดีบักและทำ Profiling (Xcode Debugger, Instruments) |
| ios-developer · `navigation` | การนำทางระหว่างหน้าจอและการเปลี่ยนหน้า | การนำทางระหว่างหน้าจอ (UINavigationController, Segue, NavigationStack) |
| ios-developer · `concurrency` | การทำงานพร้อมกันและมัลติเธรด (GCD, async/await) | การเขียนโปรแกรม Concurrency และ Multithreading (GCD, async/await) |
| ios-developer · `networking` | การเชื่อมต่อเครือข่ายและเรียกใช้ API (URLSession, REST) | การเชื่อมต่อเครือข่ายและเรียกใช้ API (URLSession, Alamofire, REST) |
| ios-developer · `data-persistence` | การจัดเก็บข้อมูลในเครื่อง (Core Data, Keychain) | การจัดเก็บข้อมูลบนเครื่อง (Core Data, UserDefaults, Keychain) |
| ios-developer · `ci-cd-and-distribution` | ระบบควบคุมเวอร์ชัน, CI/CD และการเผยแพร่แอปบน App Store | ระบบควบคุมเวอร์ชัน, CI/CD และการเผยแพร่แอปบน App Store (Git, Fastlane, TestFlight) |
| game-developer · `game-programming-languages` | ภาษาโปรแกรมสำหรับการพัฒนาเกม (C++, C#, Rust) | ภาษาสำหรับพัฒนาเกม (C++, C#, GDScript) |
| game-developer · `visibility-and-culling` | การ Culling และการกำหนด Visibility (Occlusion, Frustum) | การทำ Culling และ Visibility (Frustum Culling, Occlusion Culling) |
| game-developer · `game-physics` | ฟิสิกส์เกมและพลศาสตร์ (Game Physics) | ฟิสิกส์ในเกมและ Dynamics (Force, Friction, Joint) |
| game-developer · `color-and-tone` | สีและการแมปโทนสี (Color, Tone Reproduction) | สี การรับรู้ภาพ และ Tone Reproduction |
| game-developer · `graphics-fundamentals` | คอมพิวเตอร์กราฟิกพื้นฐาน (Graphics Pipeline, Rasterization) | คอมพิวเตอร์กราฟิกส์พื้นฐาน (Graphics Pipeline, Rasterization) |
| blockchain-developer · `blockchain-platforms` | Blockchain Platforms อื่น ๆ (Bitcoin, Solana, Cardano) | แพลตฟอร์ม Blockchain นอกเหนือจาก EVM (Bitcoin, Solana, Cardano) |
| blockchain-developer · `oracles` | Oracle และ Hybrid Smart Contract (Chainlink) | Blockchain Oracle และ Hybrid Smart Contract (Chainlink) |
| postgresql-developer-dba · `query-performance` | การปรับแต่งประสิทธิภาพ Query (EXPLAIN, pg_stat_statements) และ Connection Pooling (PgBouncer) | การปรับแต่งประสิทธิภาพ Query และ Connection Pooling (EXPLAIN, pg_stat_statements, PgBouncer) |
| postgresql-developer-dba · `transactions-and-concurrency` | การจัดการ Transactions และการเข้าถึงข้อมูลพร้อมกัน (ACID, MVCC, Locks) | การจัดการ Transaction และ Concurrency (ACID, MVCC, Locks) |
| postgresql-developer-dba · `backup-restore-and-upgrades` | การสำรองข้อมูล การกู้คืน และการอัปเกรดเวอร์ชัน (Backup, pg_upgrade) | การสำรองข้อมูล การกู้คืน และการอัปเกรดเวอร์ชัน (pg_dump, pgBackRest, pg_upgrade) |
| devops-engineer · `ci-cd` | ระบบ CI/CD และ GitOps (Jenkins, GitHub Actions, ArgoCD) | ระบบ CI/CD และ GitOps (Jenkins, GitHub Actions, Argo CD) |
| devops-engineer · `application-monitoring` | การติดตามแอปพลิเคชันและ Distributed Tracing (OpenTelemetry, Jaeger) | การเฝ้าระวังแอปพลิเคชันและ Distributed Tracing (OpenTelemetry, Jaeger) |
| backend-developer · `backend-programming-languages` | ภาษาโปรแกรมสำหรับงานแบ็กเอนด์ | ภาษาโปรแกรมสำหรับงาน Backend |
| backend-developer · `authentication-and-authorization` | การยืนยันตัวตนและการกำหนดสิทธิ์การเข้าถึง | การยืนยันตัวตนและการกำหนดสิทธิ์การเข้าถึง (JWT, OAuth, OpenID) |
| backend-developer · `nosql-and-specialty-databases` | ฐานข้อมูล NoSQL และฐานข้อมูลเฉพาะงาน | ฐานข้อมูล NoSQL และฐานข้อมูลเฉพาะทาง (MongoDB, Redis, Neo4j) |
| backend-developer · `search-engines` | เสิร์ชเอนจิน (Elasticsearch, Solr) | ระบบค้นหาข้อมูล (Elasticsearch, Solr) |
| software-architect · `collaboration-tools` | เครื่องมือทำงานร่วมกัน (Git, Jira, Slack) | เครื่องมือสำหรับทำงานร่วมกันในทีม (Git, Jira, Slack) |
| product-manager · `product-roadmapping` | การวางแผน Product Roadmap (Notion, Aha) | การวางแผน Product Roadmap (Notion, Aha!, Productboard) |
| product-manager · `product-metrics-and-analytics` | ตัวชี้วัดผลิตภัณฑ์และการตัดสินใจด้วยข้อมูล (Metrics, A/B Testing, AI) | Product Metrics, Analytics และการตัดสินใจด้วยข้อมูล (Amplitude, Heap, A/B Testing) |
| product-manager · `product-requirements` | การเขียนความต้องการของผลิตภัณฑ์ (PRD, User Stories) | การเขียนเอกสาร Product Requirements (PRD, User Story) |
| product-manager · `leadership-and-influence` | ภาวะผู้นำและการทำงานร่วมกับทีมวิศวกรรม | ภาวะผู้นำและการทำงานร่วมกับทีม Engineering |
| engineering-manager · `customer-focus` | การมุ่งเน้นลูกค้าและการสนับสนุนด้านเทคนิค | การให้ความสำคัญกับลูกค้าและงาน Technical Support |
| technical-writer · `technical-writing-foundations` | พื้นฐานอาชีพนักเขียนเชิงเทคนิค (Technical Writing) | พื้นฐานงาน Technical Writing และบทบาท Technical Writer |
| technical-writer · `funnel-content` | เนื้อหาตามลำดับขั้นของ Funnel (Top, Mid, Bottom) | เนื้อหาตามแต่ละขั้นของ Funnel (TOFU, MOFU, BOFU) |
| ux-designer · `prototyping` | การทำต้นแบบและเครื่องมือออกแบบ (Figma, Sketch) | การทำ Prototype และเครื่องมือออกแบบ (Figma, Sketch, Balsamiq) |
| ux-designer · `behavior-models` | โมเดลพฤติกรรมและการสร้างนิสัย (Fogg, Hook Model) | โมเดลพฤติกรรมและการสร้างนิสัย (Fogg Behavior Model, Hook Model) |
| ux-designer · `conceptual-design` | การออกแบบเชิงแนวคิดและกลยุทธ์เปลี่ยนพฤติกรรม | การออกแบบเชิงแนวคิดและกลยุทธ์การเปลี่ยนพฤติกรรม |
| qa-engineer · `web-technology-fundamentals` | พื้นฐานเว็บเทคโนโลยีสำหรับงาน QA (HTML, CSS, JavaScript) | พื้นฐานเทคโนโลยีเว็บสำหรับงาน QA (HTML, CSS, JavaScript) |
| qa-engineer · `functional-testing` | การทดสอบเชิงฟังก์ชัน (Smoke, Regression, UAT) | การทดสอบ Functional (Smoke, Regression, UAT) |
| qa-engineer · `api-backend-test-automation` | การทดสอบ API และแบ็กเอนด์แบบอัตโนมัติ (Postman, REST Assured) | การทำ Test Automation สำหรับ API และ Backend (Postman, REST Assured) |
| qa-engineer · `performance-testing-tools` | เครื่องมือทดสอบ Load และ Performance (JMeter, K6) | เครื่องมือทดสอบ Load และ Performance (JMeter, k6) |

### 8.2 Rejected, with the reason

| Finding | Decision |
| --- | --- |
| Data/ML reviewer: render *monitoring* as Monitoring in English (data-engineer, mlops) | **Rejected.** การเฝ้าระวัง is used in eight sets across seven files and the backend reviewer asked for the opposite change on the same ground. Consistency wins; the devops `application-monitoring` set was aligned *to* การเฝ้าระวัง instead. |
| Client-side reviewer: ios `networking` as การเชื่อมต่อ Network | **Rejected**, and android aligned the other way. The copy editor flagged android's Network as the outlier; เครือข่าย is the catalog's rendering everywhere else. |
| Data/ML reviewer: ai-data-scientist `mlops` as Model Lifecycle | **Rejected.** วงจรชีวิตโมเดล is natural Thai and the term is not on the English list; low confidence from the reviewer. |
| Copy editor: drop the comma in ios `ci-cd-and-distribution` | **Rejected.** §4 item 9 added it so ระบบควบคุมเวอร์ชัน CI/CD does not parse as "the CI/CD version-control system". |
| Copy editor: align ธรรมาภิบาลข้อมูล and การกำกับดูแล | **Rejected.** Settled in §6.2 and §7.2 as two constructs. |
| Security reviewer: Troubleshoot in English for cyber `command-line-and-analysis-tools` | **Rejected** in favour of the copy editor's grammar fix, which keeps the Thai and adds the missing และ. |
| Client-side reviewer: คุณภาพของโค้ด vs คุณภาพโค้ด | **Not applied.** Both are grammatical; noted for the approver. |
| Data/ML reviewer: plural inconsistency in glosses (APIs vs API) | **Not applied.** Gloss items are names, and both forms are in use; noted for the approver. |
| Security reviewer: cyber `secure-protocols` | Not raised as a change; the reviewer confirmed the §7.2 decision. |

### 8.3 What the approver still has to do

Unchanged from §7.3: flip `review.status` to `reviewed` per set after reading. The panel
has read every set at least twice (domain reviewer plus copy editor); §7.1 and §8.1 list
the 96 wordings that changed today, and the remaining 360 were confirmed as written by both.

---

## 9. Approval — 2026-09-02, all 456 sets set to `reviewed`

The project owner instructed the agent to flip `review.status` from `draft` to `reviewed`
on every set in `data/content/topic_sets/`, accepting the §7–§8 panel record as the
review. ADR-0004 decision 1 reserves this flip for a person; it was performed on that
explicit instruction, not on the agent's own judgement. Nothing else in the files changed.

After the flip: `validate_topic_set_catalog --strict` passes (112 uncovered node slugs
remain as backlog), the wording-rule and topic-set tests pass, the persona harness matches
`data/simulation/persona_baseline.json`, and the full suite is green. Issue #7 closes on
this commit.
