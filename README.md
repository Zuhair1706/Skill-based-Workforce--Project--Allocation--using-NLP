# Skill-based Workforce Project Allocation

Full-stack workforce planning application built around the project's supplied
employee, skill, and project datasets.

- **Backend:** Python, FastAPI, SQLAlchemy, MySQL-compatible database
- **NLP:** fine-tunable BERT/RoBERTa token classification plus skill alias
  matching for project descriptions
- **Optimization:** Google OR-Tools CP-SAT under team, skill, location,
  availability, seniority, relocation, and budget constraints
- **Frontend:** React and Vite

## Run the website locally

Requirements: Python 3.11+ and Node.js 20+ (npm is included with Node.js).
The local database uses SQLite; no external database server is needed.

1. In a terminal, install the backend and load the supplied datasets:

   ```powershell
   cd coding_part/backend
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m app.seed
   uvicorn app.main:app --reload
   ```

2. In a second terminal, install and start the website:

   ```powershell
   cd coding_part/frontend
   npm install
   npm run dev
   ```

3. Open the Vite URL shown in the terminal (normally
   `http://localhost:5173`). The website extracts skills from the edited
   project description, filters employees by availability and location, then
   uses OR-Tools to optimize a team against the project's constraints.

The API and interactive documentation are available at
`http://localhost:8000` and `http://localhost:8000/docs`. Set `VITE_API_URL` in
`coding_part/frontend/.env` to point the website at a different API address.
For MySQL setup, model training, and optimization details, see the
[backend README](./coding_part/backend/README.md).
