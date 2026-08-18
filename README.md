# CompetencyX Backend

REST API (Django + Django REST Framework) สำหรับ **Role Discovery** (ค้นหาสายงานที่น่าจะเหมาะ), **Skill Assessment** (ประเมินทักษะตัวเองตาม PSP/SDLC) และ **Recommendation** (แนะนำหัวข้อถัดไปใน roadmap)

เอกสารนี้เขียนสำหรับ dev ที่เพิ่งเข้ามาในโปรเจกต์ — ทำตามทีละขั้นได้เลย ไม่ต้องเดาว่าต้องรันคำสั่งไหน

> คำศัพท์ในโปรเจกต์นี้มีนิยามชัดเจน (Role Affinity, Role Readiness, Role Resolution ฯลฯ) อ่านได้ที่ [CONTEXT.md](CONTEXT.md) ก่อนเริ่มแก้ logic

---

## 1. สิ่งที่ต้องมีก่อน

| ต้องมี | หมายเหตุ |
| --- | --- |
| Python 3.12 | ดู `.python-version` |
| [uv](https://docs.astral.sh/uv/) | ใช้ติดตั้ง dependencies (`uv sync`) |
| Docker (ไม่บังคับ) | ใช้เฉพาะตอนอยากรันคู่กับ PostgreSQL |

---

## 2. ติดตั้งครั้งแรก

รันตามลำดับนี้ (ตัวอย่างเป็น PowerShell บน Windows)

```powershell
# 2.1 ติดตั้ง dependencies ทั้งหมด (รวม dev tools เช่น pytest / ruff) ลงใน .venv
uv sync

# 2.2 สร้างไฟล์ .env สำหรับเครื่องตัวเอง
Copy-Item .env.example .env

# 2.3 สร้าง/อัปเดตตารางในฐานข้อมูล
.\.venv\Scripts\python.exe manage.py migrate

# 2.4 โหลดเนื้อหา (roles, roadmap topics, คำถาม, Skill Assessment catalog) เข้า DB
.\.venv\Scripts\python.exe manage.py sync_content

# 2.5 สตาร์ทเซิร์ฟเวอร์
.\.venv\Scripts\python.exe manage.py runserver
```

เปิด `http://localhost:8000/api/schema/swagger-ui/` ถ้าเห็นหน้า Swagger = ใช้ได้แล้ว

**หมายเหตุ**

- ไม่ต้องใส่ `--env-file` เพราะ `manage.py` โหลด `.env` ให้เองผ่าน `config/env.py`
- ค่าใน `.env.example` เป็นค่าสำหรับ dev เท่านั้น (`DJANGO_SECRET_KEY` เป็นค่าปลอม) ถ้าจะเอาไปใช้ที่อื่นต้องเปลี่ยนก่อน
- ค่าเริ่มต้นคือ SQLite ที่ไฟล์ `db.sqlite3` (ไฟล์นี้ถูก gitignore ไว้ `migrate` + `sync_content` จะสร้างให้เอง) ถ้าตั้ง `POSTGRES_HOST` หรือ `DATABASE_URL` ระบบจะสลับไปใช้ PostgreSQL อัตโนมัติ
- `sync_content` รันซ้ำได้ทุกเมื่อ ใช้ตอนที่แก้ไฟล์ใต้ `data/content/` แล้วอยากให้ DB ตรงกับไฟล์

### ทำไมใช้ `.\.venv\Scripts\python.exe` แทน `uv run`

บนเครื่อง Windows บางเครื่อง `uv run <tool>` และ shim ใน `.venv\Scripts\*.exe` (เช่น `pytest.exe`, `ruff.exe`) พังด้วย error
`uv trampoline failed to canonicalize script path` ทั้งที่ตัว venv เองปกติดี

ทางที่ชัวร์ที่สุดคือเรียกผ่าน interpreter ของ venv ตรง ๆ

```powershell
.\.venv\Scripts\python.exe -m pytest        # แทน uv run pytest
.\.venv\Scripts\python.exe -m ruff check .  # แทน uv run ruff
.\.venv\Scripts\python.exe manage.py <cmd>  # แทน uv run python manage.py
```

ถ้าเครื่องของคุณ `uv run` ทำงานได้ปกติ จะใช้ `uv run ...` แทนก็ได้ ผลลัพธ์เหมือนกัน
บน macOS / Linux ให้เปลี่ยน path เป็น `./.venv/bin/python`

---

## 3. รันแบบ Docker (Django + PostgreSQL)

```powershell
docker compose up --build
```

คำสั่งเดียวจบ: ยก PostgreSQL 16 + Django ขึ้นมา รัน migration และ seed เนื้อหาให้ แอปอยู่ที่ `http://localhost:8000`

```powershell
docker compose down        # ปิด
docker compose down -v     # ปิดและลบ volume ของ database ทิ้ง (เริ่มใหม่หมด)
docker compose logs -f web # ดู log ของแอป
```

ยิงคำสั่ง management ด้วย image เดียวกันได้ผ่าน service `cli` (อยู่ใน profile `tools` จึงไม่ start เองตอน `up`)

```powershell
docker compose run --rm cli manage.py sync_content
docker compose run --rm cli manage.py validate_question_catalog
```

คอนเทนเนอร์รันด้วย **gunicorn** (ไม่ใช่ `runserver`) ตาม `docker/entrypoint.sh` ซึ่งจะ `migrate` → `sync_content` → `collectstatic` ให้ก่อนเสมอ
และต่อ DB ผ่าน `DATABASE_URL` เหมือนที่ Railway ใช้ — stack นี้จึงทดสอบ config ชุดเดียวกับ production
เปลี่ยนพอร์ตที่เปิดออกมาได้ด้วย `WEB_PORT` / `POSTGRES_PORT` ใน `.env`
ถ้าอยากได้ auto-reload ตอน dev ให้ใช้ `manage.py runserver` ในหัวข้อ 2 แทน

---

## 4. Deploy ขึ้น Railway

repo นี้พร้อม deploy ขึ้น [Railway](https://railway.com) แล้ว — Railway จะ build จาก `Dockerfile` และอ่านค่าจาก `railway.json`
(healthcheck ชี้ไปที่ `/api/v1/health/`, restart แบบ `ON_FAILURE`)

### 4.1 สร้าง project และ database

1. ไปที่ [railway.com/new](https://railway.com/new) → **Deploy from GitHub repo** → เลือก `CompetencyX-Backend`
2. ในหน้า project กด **+ Create** → **Database** → **PostgreSQL**

### 4.2 ตั้งค่า Variables ของ service ตัวแอป

| ตัวแปร | ค่าที่ใส่ |
| --- | --- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (variable reference ของ Railway ไม่ต้อง copy ค่าจริง) |
| `DJANGO_SECRET_KEY` | ค่าสุ่มยาว ๆ ห้ามใช้ค่าจาก `.env.example` |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_CORS_ALLOW_ALL_ORIGINS` | `true` ถ้ายังไม่มีโดเมน frontend แน่นอน |

สร้าง secret key ได้ด้วย

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`DJANGO_ALLOWED_HOSTS` **ไม่ต้องตั้ง** — settings อ่าน `RAILWAY_PUBLIC_DOMAIN` ที่ Railway ใส่ให้ตอน runtime แล้วเติมเข้า `ALLOWED_HOSTS` กับ `CSRF_TRUSTED_ORIGINS` ให้เอง พร้อมเปิด `SECURE_PROXY_SSL_HEADER` เพราะ Railway ทำ TLS termination ให้

### 4.3 เปิดโดเมนและตรวจผล

ที่ service → **Settings** → **Networking** → **Generate Domain** แล้วลอง

```powershell
curl.exe -s https://<your-app>.up.railway.app/api/v1/health/
```

ตัว entrypoint รัน `migrate` และ `sync_content` ทุกครั้งที่ deploy ดังนั้น content ใน DB จะตามไฟล์ใน `data/content/` อัตโนมัติ ไม่ต้องเข้าไปรันเอง

### 4.4 ใช้ Railway CLI (ถ้าไม่อยาก deploy ผ่าน GitHub)

```powershell
npm i -g @railway/cli
railway login
railway link          # ผูกโฟลเดอร์นี้กับ project ที่สร้างไว้
railway up            # build + deploy จากเครื่อง
railway logs          # ดู log
railway run .\.venv\Scripts\python.exe manage.py createsuperuser   # รันคำสั่งโดยใช้ env ของ Railway
```

### สิ่งที่ควรรู้

- ต้องมี PostgreSQL เสมอ — SQLite บน Railway จะหายทุกครั้งที่ deploy ใหม่เพราะ filesystem ไม่ persist
- static ของ `/admin/` และ DRF browsable API เสิร์ฟด้วย **whitenoise** ส่วน Swagger UI โหลดจาก CDN จึงใช้ได้ทันที
- ยังไม่มี authentication บน API — ถ้า deploy สาธารณะ ใครก็ยิงได้ ควรใส่ auth ก่อนใช้งานจริง

---

## 5. URL ที่ใช้บ่อย

| จุดประสงค์ | URL |
| --- | --- |
| Health check | `http://localhost:8000/api/v1/health/` |
| Swagger UI | `http://localhost:8000/api/schema/swagger-ui/` |
| OpenAPI schema | `http://localhost:8000/api/schema/` |
| Django admin | `http://localhost:8000/admin/` |

### Endpoint หลัก

Catalog (ข้อมูล role / roadmap — อ่านอย่างเดียว)

- `GET /api/v1/catalog/roles/` — รายชื่อ role ที่ active
- `GET /api/v1/catalog/roles/{slug}/topics/` — หัวข้อทั้งหมดของ role
- `GET /api/v1/catalog/roles/{slug}/roadmap/` — roadmap เรียงตามลำดับ prerequisite

Assessment session (flow หลัก)

- `POST /api/v1/assessment-sessions/` — เปิด session ใหม่
- `GET  /api/v1/assessment-sessions/{id}/` — ดูสถานะ session + คำถามปัจจุบัน
- `POST /api/v1/assessment-sessions/{id}/answers/` — ส่งคำตอบ
- `GET  /api/v1/assessment-sessions/{id}/insights/` — evidence ระหว่างทาง (pillar / ranked roles)
- `GET  /api/v1/assessment-sessions/{id}/results/` — ผลสรุป + recommendation
- `GET  /api/v1/assessment-sessions/{id}/history/` — ประวัติคำตอบ
- `GET  /api/v1/assessment-sessions/{id}/skill-assessment/catalog/` — dimension ของ PSP/SDLC
- `POST /api/v1/assessment-sessions/{id}/skill-assessment/next-question/` — ขอคำถาม Skill Assessment ถัดไป
- `GET|POST /api/v1/assessment-sessions/{id}/skill-assessment/` — อ่าน / บันทึกผล Skill Assessment

ตอนนี้ API **ยังไม่มี authentication** และรายละเอียด payload ทั้งหมดอยู่ใน [docs/frontend-integration.md](docs/frontend-integration.md)

### ลองยิง API ดูเร็ว ๆ

```powershell
# เปิด session (language ใส่ "th" หรือ "en")
curl.exe -s -X POST http://localhost:8000/api/v1/assessment-sessions/ -H "Content-Type: application/json" -d '{\"language\":\"th\"}'

# ตอบคำถาม (session id เป็น UUID จาก response ก่อนหน้า, question_id มาจาก current_question)
curl.exe -s -X POST http://localhost:8000/api/v1/assessment-sessions/<session-id>/answers/ -H "Content-Type: application/json" -d '{\"question_id\":1,\"scale_value\":4}'

# ดูผลลัพธ์
curl.exe -s http://localhost:8000/api/v1/assessment-sessions/<session-id>/results/
```

ทำซ้ำขั้นตอน "ตอบคำถาม" ไปเรื่อย ๆ จนกว่า `current_question` จะเป็น `null` — backend เป็นคนเลือกคำถามถัดไปให้เอง ฝั่ง frontend ไม่ต้องตัดสินใจ

---

## 6. คำสั่งที่ใช้ตอน dev

### เทสต์และ lint

```powershell
# รันเทสต์ทั้งหมดแบบขนาน (ใช้ config.settings.test + SQLite อัตโนมัติ)
.\.venv\Scripts\python.exe -m pytest

# รันเฉพาะไฟล์เดียว และปิด parallel เพื่อ debug
.\.venv\Scripts\python.exe -m pytest assessments/tests.py -n 0

# lint
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff check . --fix

# coverage (ต้องใส่ -n 0 เพราะ xdist แต่ละ worker วัดเฉพาะส่วนของตัวเอง)
.\.venv\Scripts\python.exe -m pytest -n 0 --cov=. --cov-report=xml:coverage/coverage.xml --cov-report=term-missing
```

`-n auto` ถูกใส่ไว้ใน `addopts` ของ `pyproject.toml` แล้ว จึงไม่ต้องพิมพ์เอง
รัน pytest และ ruff ให้ผ่านก่อนเปิด PR เสมอ

### จัดการ content / ข้อมูล

```powershell
# ซิงก์เนื้อหาจาก data/content/ เข้า DB
.\.venv\Scripts\python.exe manage.py sync_content

# ตรวจ YAML คำถามโดยไม่แตะ DB
.\.venv\Scripts\python.exe manage.py validate_question_catalog

# สร้าง ROLE_PROFILE_WEIGHTS ใหม่จาก data/content/role_dimension_relevance.yaml
.\.venv\Scripts\python.exe manage.py generate_role_weights

# ตรวจว่าไฟล์ที่ generate ไว้ยัง up-to-date ไหม (ใช้ใน CI, ถ้าเก่าจะ exit ไม่เป็น 0)
.\.venv\Scripts\python.exe manage.py generate_role_weights --check

# นำเข้า roadmap snapshot ดิบเข้า normalized tables
.\.venv\Scripts\python.exe manage.py import_roadmap_snapshot --path data/upstream/<file>.json --role-slug backend-developer
```

> น้ำหนัก (weights) ของ role มาจาก rubric แล้ว generate ออกมา — **อย่าแก้ไฟล์ที่ generate ด้วยมือ** ให้แก้ YAML ต้นทางแล้วรัน `generate_role_weights`

### Simulation และการจูนคะแนน

ใช้ตรวจว่าการแก้ scoring ทำให้ผลแย่ลงหรือไม่ รายละเอียดอยู่ใน [docs/scoring-simulation.md](docs/scoring-simulation.md)

```powershell
# Monte Carlo แบบ in-memory เร็วที่สุด ไม่เขียน DB
.\.venv\Scripts\python.exe manage.py simulate_inmemory --samples 1000

# จำลอง persona ของทุก role แล้วเทียบกับ baseline (regression gate — exit 1 ถ้าตกเกณฑ์)
.\.venv\Scripts\python.exe manage.py simulate_personas --check-baseline data/simulation/persona_baseline.json

# อัปเดต baseline หลังยืนยันแล้วว่าผลใหม่ดีขึ้นจริง
.\.venv\Scripts\python.exe manage.py simulate_personas --write-baseline data/simulation/persona_baseline.json

# grid search หา hyperparameter ของ scoring
.\.venv\Scripts\python.exe manage.py tune_scoring --grid data/scoring_tuning_grid.yaml --samples 500

# จำลองผ่าน DB จริง (ช้ากว่า แต่เดินครบทั้ง flow)
.\.venv\Scripts\python.exe manage.py simulate_assessment --samples 100
```

ทุกคำสั่ง simulation รองรับ `--random-seed` (ค่าเริ่มต้น 42) และ `--format json` ถ้าจะเอาผลไปประมวลผลต่อ
ด่าน persona-harness เป็น **gate บังคับ** ก่อน merge การแก้ scoring

### Django ทั่วไป

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser   # เอาไว้เข้า /admin/
.\.venv\Scripts\python.exe manage.py shell
.\.venv\Scripts\python.exe manage.py spectacular --file docs/openapi.json   # อัปเดต schema snapshot
```

---

## 7. โครงสร้างโปรเจกต์

| โฟลเดอร์ | หน้าที่ |
| --- | --- |
| `api/` | จุดเข้า API รวม, health check, และคำสั่ง `sync_content` |
| `assessments/` | session, คำตอบ, scoring, serializers, คำสั่ง simulation |
| `roadmaps/` | role, topic, คำถาม, seed data, logic ของ questionnaire |
| `recommendations/` | logic การแนะนำหัวข้อถัดไป |
| `config/` | Django settings (`settings/runtime.py`, `settings/test.py`) และ root URLs |
| `data/content/` | เนื้อหาที่ curate เอง (role, topic, คำถาม) — แหล่งความจริงของ content |
| `data/upstream/` | snapshot ที่ import มาจากภายนอก ถือเป็น source material |
| `simulation/` | เอนจิน Monte Carlo และ persona fidelity |
| `docker/` | asset สำหรับ Docker |
| `docs/` | ADR, เอกสาร scoring, ticket, และ integration notes |

---

## 8. อ่านต่อ

- [CONTEXT.md](CONTEXT.md) — คำศัพท์ของ domain (อ่านก่อนแก้ logic)
- [AGENTS.md](AGENTS.md) — coding style, testing, commit convention
- [docs/frontend-integration.md](docs/frontend-integration.md) — สัญญา API สำหรับฝั่ง frontend
- [docs/scoring-methodology.md](docs/scoring-methodology.md) — วิธีคิดคะแนน
- [docs/scoring-simulation.md](docs/scoring-simulation.md) — วิธีใช้ simulation harness
- [docs/adr/](docs/adr/) — เหตุผลเบื้องหลังการตัดสินใจเชิงสถาปัตยกรรม
- [docs/tickets/](docs/tickets/) — งานที่ทำไปแล้วและที่ยังค้าง

---

## 9. ปัญหาที่เจอบ่อย

| อาการ | วิธีแก้ |
| --- | --- |
| `uv trampoline failed to canonicalize script path` | เรียกผ่าน `.\.venv\Scripts\python.exe -m <tool>` แทน (ดูหัวข้อ 2) |
| ยิง API แล้วไม่มี role หรือคำถามเลย | ยังไม่ได้รัน `manage.py sync_content` |
| `no such table` | ยังไม่ได้รัน `manage.py migrate` |
| `DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false` | ยังไม่ได้สร้าง `.env` หรือไม่ได้ตั้ง `DJANGO_SECRET_KEY` |
| เทสต์ผลไม่ตรงกับที่แก้ | `--reuse-db` ค้าง DB เก่าไว้ ลบ `test_db.sqlite3` แล้วรันใหม่ |
