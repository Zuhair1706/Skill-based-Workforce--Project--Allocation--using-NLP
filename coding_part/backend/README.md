# Workforce allocation backend

FastAPI service for project browsing, skill extraction, and OR-Tools team
optimization. The default local database is SQLite so the app can be tried
without a running MySQL server; set `DATABASE_URL` to use MySQL in production.

## Setup

From `coding_part/backend`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

For MySQL, create `workforce_analytics` and set `DATABASE_URL` in `.env`, for
example:

```text
DATABASE_URL=mysql+mysqlconnector://workforce:your-password@localhost:3306/workforce_analytics
```

Load all source CSVs (100,000 employees and their skill rows included):

```powershell
python -m app.seed
```

The importer reads the repository's CSV folders and creates the application
tables. It replaces the imported rows on each run; it does not drop the tables.

Start the API:

```powershell
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API. Endpoints are under
`/api`: `GET /health`, `GET /projects`, `GET /projects/{project_id}`,
`POST /skills/extract`, and `POST /allocations/optimize`.

## Skill NER

Skill matching uses the project aliases, project requirement vocabulary, and
the employee skill catalog. To train a BERT or RoBERTa token classifier from
the project's character-span annotations:

```powershell
python -m app.train_nlp --base-model bert-base-cased --output-dir models/skill-ner
```

Set `SKILL_NER_MODEL` to the saved model directory and restart the API. The
transformer model recognizes `B-SKILL`/`I-SKILL` labels; the alias matcher
continues to supplement predictions. The checked-in annotation set is small,
so expand and validate it before relying on the trained model in production.
`/api/health` reports which extractor is active.

## Optimization constraints

The solver builds an exact-size team, meets each required skill's qualified
headcount, minimum lead and senior-plus counts, maximum lead/junior/relocation
percentages, and the project budget. A candidate must have at least the
project's member allocation available. Project location and nearby locations
count as local; other candidates must be willing to relocate. The objective
maximizes weighted skill fit, performance, and experience while preferring
local and lower-cost members. Cost estimates use monthly salary, project
duration, and member allocation percentage.

The database query limits the skill-ranked candidate pool (default 3,000) and
adds lead/senior/junior strata before invoking CP-SAT. Increase
`MAX_CANDIDATES` when a project has unusually restrictive skill or location
requirements. Infeasible constraints are returned as HTTP 422, not as a
partial or success-shaped team.
