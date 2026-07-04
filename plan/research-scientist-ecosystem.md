# University Research AI Scientist Ecosystem

## Vision
A cloud-hosted multi-tenant platform where professors across departments create projects, manage tasks, run experiments, and collaborate with AI scientist agents — all within a single integrated system.

## Architecture

```
University Cloud Server
│
├── nginx (SSL) → PM Frontend (React SPA)
│                      │
│                      ▼
│                PM API (FastAPI, :7860)
│                      │
│             ┌────────┴────────┐
│             ▼                 ▼
│        SQLite/Postgres    Garage S3
│        (projects.db)     (attachments)
│             │
│             ▼
│        Runner Service (:8001)
│             │
│             ▼
│        Agent (LangGraph + 6 sub-agents)
│
├── Admin: manage labs, users, system config
├── PI: see all lab projects, create from templates
├── Student: see assigned tasks, run experiments via AI
└── AI: reads/writes PM entities through API
```

## MVP Timeline (1 Month)

### Week 1: Multi-Tenant Foundation
- `labs` + `lab_members` DB tables, models, CRUD
- Lab API routes (create, list, members)
- Frontend: Lab list, detail, member management pages
- Project filtering by lab

### Week 2: Domain Templates + Project Wizard
- Template YAML files (life-science, medical, ml-research)
- Template loader service
- `POST /from-template` API route
- Frontend: Template picker wizard

### Week 3: AI ↔ PM Integration
- AI creates project from natural language
- AI assigns research tasks
- "Run Experiment" → agent executes → results saved
- Data analysis auto-generated from experiment entries
- Paper section drafting from results

### Week 4: Production Deployment
- Docker compose with nginx + SSL
- Auth hardening (JWT refresh, rate limiting)
- Admin dashboard (stats across labs)
- PI dashboard (cross-lab overview)

## DB Schema Additions

```sql
CREATE TABLE labs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pi_id TEXT REFERENCES users(id),
    department TEXT NOT NULL,
    university TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE lab_members (
    lab_id TEXT REFERENCES labs(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('pi','postdoc','phd','ms','visitor')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY (lab_id, user_id)
);

ALTER TABLE projects ADD COLUMN lab_id TEXT REFERENCES labs(id);
```

## API Endpoints

```
POST   /api/v1/labs                    # Create lab
GET    /api/v1/labs                    # List labs (admin/PI)
GET    /api/v1/labs/{id}               # Lab detail
PUT    /api/v1/labs/{id}               # Update lab
DELETE /api/v1/labs/{id}               # Delete lab (admin only)
POST   /api/v1/labs/{id}/members       # Add member
DELETE /api/v1/labs/{id}/members/{uid} # Remove member
GET    /api/v1/projects?lab_id={id}    # Filter projects by lab
POST   /api/v1/projects/from-template  # Create project from template
GET    /api/v1/templates               # List available templates
```

## What's Deferred Past MVP
- Publication pipeline
- Grant tracking
- SSO/OIDC (JWT auth for MVP)
- Scientific protocol library
- Audit logging
