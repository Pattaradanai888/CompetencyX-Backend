# Assessable Topic Set review — Canonical Thai wording and grouping

**Reviewed:** 2026-08-26, against all 26 files in `data/content/topic_sets/` (459 sets; 456 after #16).

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
