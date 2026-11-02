import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BrainCircuit,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Cpu,
  MapPin,
  Search,
  Sparkles,
  Users,
  Wallet,
} from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

const formatMoney = (amount) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(amount || 0);

export default function App() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [project, setProject] = useState(null);
  const [allocation, setAllocation] = useState(null);
  const [health, setHealth] = useState(null);
  const [search, setSearch] = useState("");
  const [description, setDescription] = useState("");
  const [extractedSkills, setExtractedSkills] = useState([]);
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState("");
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState("");

  useEffect(() => {
    Promise.all([api("/api/projects"), api("/api/health")])
      .then(([data, status]) => {
        setProjects(data);
        setHealth(status);
        if (data.length) setProjectId(data[0].project_id);
      })
      .catch((error) => setPageError(error.message));
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setAllocation(null);
    api(`/api/projects/${projectId}`)
      .then((data) => {
        setProject(data);
        setDescription(data.project_description || "");
        setPageError("");
      })
      .catch((error) => setPageError(error.message));
  }, [projectId]);

  useEffect(() => {
    const text = description.trim();
    if (!text) {
      setExtractedSkills([]);
      setExtracting(false);
      setExtractionError("");
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setExtracting(true);
      setExtractionError("");
      try {
        const result = await api("/api/skills/extract", {
          method: "POST",
          body: JSON.stringify({ description: text }),
          signal: controller.signal,
        });
        setExtractedSkills(result.skills);
      } catch (error) {
        if (!controller.signal.aborted) setExtractionError(error.message);
      } finally {
        if (!controller.signal.aborted) setExtracting(false);
      }
    }, 350);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [description]);

  const filteredProjects = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return projects;
    return projects.filter((item) =>
      `${item.project_name} ${item.domain} ${item.location}`.toLowerCase().includes(query),
    );
  }, [projects, search]);

  const visibleSkills = useMemo(() => {
    const skills = project?.requirements || [];
    const known = new Set(
      skills.map((item) =>
        item.required_skill.toLowerCase().replace(/[^a-z0-9+#.]+/g, " ").trim(),
      ),
    );
    return [
      ...skills,
      ...extractedSkills
        .filter((item) => {
          const key = item.skill.toLowerCase().replace(/[^a-z0-9+#.]+/g, " ").trim();
          if (!key || known.has(key)) return false;
          known.add(key);
          return true;
        })
        .map((item) => ({
          required_skill: item.skill,
          importance_1_5: 1,
          extracted: true,
        })),
    ];
  }, [project, extractedSkills]);

  async function createTeam() {
    setLoading(true);
    setPageError("");
    try {
      const result = await api("/api/allocations/optimize", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, description }),
      });
      setAllocation(result);
    } catch (error) {
      setPageError(error.message);
    } finally {
      setLoading(false);
    }
  }

  function downloadCsv() {
    if (!allocation) return;
    const columns = ["employee_id", "employee_name", "job_role", "seniority", "location", "match_score", "skill_coverage_pct"];
    const lines = [columns.join(","), ...allocation.team.map((member) =>
      columns.map((key) => `"${String(member[key] ?? "").replaceAll('"', '""')}"`).join(","),
    )];
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${projectId}-team.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const summary = allocation?.summary;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Workforce Studio home">
          <span className="brand-mark"><BrainCircuit size={21} /></span>
          <span>workforce<span className="brand-light">.studio</span></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <button className="nav-item active"><Users size={17} /> Team allocation</button>
        <button className="nav-item" onClick={() => document.getElementById("project-select")?.focus()}>
          <Activity size={17} /> Project portfolio
        </button>
        <div className="sidebar-spacer" />
        <div className="sidebar-status">
          <span className={`status-dot ${health?.status === "ok" ? "online" : ""}`} />
          <div><b>{health?.database || "Connecting"}</b><small>Database status</small></div>
        </div>
        <div className="sidebar-footer">WORKFORCE INTELLIGENCE <span>v1.0</span></div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumbs">Workspace <span>/</span> Allocation studio</div>
          <div className="topbar-right"><span className="live-pill"><span /> SYSTEM LIVE</span><span className="avatar">WS</span></div>
        </header>

        <section className="page-heading">
          <div>
            <div className="eyebrow"><Sparkles size={14} /> INTELLIGENT STAFFING</div>
            <h1>Build your next <span>great team.</span></h1>
            <p>Match the right people to the work. Skill-aware recommendations, optimized for your constraints.</p>
          </div>
          <div className="heading-icon"><Cpu size={22} /><span>AI powered</span></div>
        </section>

        {pageError && <div className="alert"><CircleAlert size={18} /><span>{pageError}</span></div>}

        <div className="workspace-grid">
          <section className="panel project-panel">
            <div className="panel-heading">
              <div><div className="step-label"><span>01</span> PROJECT BRIEF</div><h2>Set your requirements</h2></div>
              <span className="heading-icon small"><BrainCircuit size={18} /></span>
            </div>
            <label className="field-label" htmlFor="project-search">Select a project</label>
            <div className="search-wrap">
              <Search size={17} />
              <input id="project-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search projects..." />
              <ChevronDown size={16} />
            </div>
            <label className="select-wrap" htmlFor="project-select">
              <select id="project-select" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
                {filteredProjects.map((item) => <option key={item.project_id} value={item.project_id}>{item.project_name}</option>)}
              </select>
              <ChevronDown size={16} />
            </label>

            {project && <>
              <div className="project-meta">
                <span className="domain-tag">{project.domain}</span>
                <span><MapPin size={14} /> {project.location}</span>
                <span><Clock3 size={14} /> {project.duration_months} months</span>
              </div>
              <div className="form-divider" />
              <div className="description-heading">
                <label className="field-label" htmlFor="description">Project description</label>
                <span><Sparkles size={12} /> SKILL EXTRACTION ENABLED</span>
              </div>
              <textarea id="description" rows="7" value={description} onChange={(event) => setDescription(event.target.value)} />
              <div className="detected-heading"><span>REQUIRED SKILLS</span><small>{extracting ? "Extracting from description..." : `${visibleSkills.length} identified`}</small></div>
              <div className="skill-list">
                {visibleSkills.map((requirement) => (
                  <span className={`skill-chip ${requirement.importance_1_5 >= 4 ? "critical" : ""} ${requirement.extracted ? "detected" : ""}`} key={requirement.required_skill}>
                    <span className="skill-dot" />{requirement.required_skill}{requirement.extracted && <small>detected</small>}
                  </span>
                ))}
                {!visibleSkills.length && <small>No skills identified yet. Add them to the project description.</small>}
              </div>
              {extractionError && <p className="extraction-error" role="status">Skill extraction failed: {extractionError}</p>}
              <button className="primary-button" onClick={createTeam} disabled={loading || !projectId || !description.trim()}>
                {loading ? <><span className="spinner" /> Optimizing team...</> : <>Generate optimized team <ArrowRight size={17} /></>}
              </button>
              <p className="button-note"><Check size={13} /> Respects availability, budget, seniority &amp; relocation constraints</p>
            </>}
          </section>

          <section className="results-column">
            {summary ? <>
              <div className="metrics-grid">
                <Metric icon={<Users size={17} />} label="TEAM SIZE" value={summary.team_size} suffix="members" tone="blue" />
                <Metric icon={<Wallet size={17} />} label="EST. PROJECT COST" value={`₹${formatMoney(summary.total_cost_lakh)}`} suffix="lakh" tone="green" />
                <Metric icon={<Sparkles size={17} />} label="SKILL COVERAGE" value={`${Math.round(summary.average_skill_coverage_pct)}%`} suffix="avg. match" tone="violet" />
              </div>
              <div className="panel team-panel">
                <div className="panel-heading team-heading">
                  <div><div className="step-label"><span>02</span> OPTIMIZED RECOMMENDATION</div><h2>Your project team <span className="count-badge">{summary.team_size}</span></h2></div>
                  <button className="export-button" onClick={downloadCsv}><ArrowDownToLine size={15} /> Export</button>
                </div>
                <div className="team-summary">
                  <span className="solver-badge"><Check size={13} /> {allocation.status.toLowerCase()} solution</span>
                  <span>{summary.lead_count} leads</span><i /><span>{summary.senior_plus_count} senior+</span><i /><span>{summary.relocated_count} relocating</span>
                </div>
                <div className="team-table-wrap">
                  <table><thead><tr><th>TEAM MEMBER</th><th>ROLE</th><th>LOCATION</th><th>SKILL FIT</th></tr></thead>
                    <tbody>{allocation.team.map((member) => <tr key={member.employee_id}>
                      <td><div className="member-cell"><span className="member-avatar">{member.employee_name?.split(" ").map((word) => word[0]).slice(0, 2).join("")}</span><div><b>{member.employee_name}</b><small>{member.employee_id}</small></div></div></td>
                      <td><b className="role-name">{member.job_role}</b><small className="role-level">{member.seniority}</small></td>
                      <td><span className="member-location"><MapPin size={13} />{member.location}</span>{member.relocation_required && <small className="relocation-label">Relocating</small>}</td>
                      <td><div className="fit-cell"><b>{Math.round(member.skill_coverage_pct)}%</b><span className="fit-track"><i style={{ width: `${member.skill_coverage_pct}%` }} /></span></div></td>
                    </tr>)}</tbody>
                  </table>
                </div>
                <div className="team-footnote"><Check size={14} /> Team meets all hard constraints · Budget ₹{formatMoney(summary.budget_lakh)} lakh</div>
              </div>
            </> : <div className="empty-state">
              <span className="empty-icon"><BrainCircuit size={29} /></span>
              <div className="step-label"><span>02</span> OPTIMIZED RECOMMENDATION</div>
              <h2>Your team takes shape here.</h2>
              <p>Choose a project and let the skill engine find the best-fit team within your project constraints.</p>
              <div className="empty-features"><span><Check size={13} /> Skill matched</span><span><Check size={13} /> Constraint optimized</span><span><Check size={13} /> Budget aware</span></div>
            </div>}
            {allocation?.extracted_skills?.length > 0 && (
              <div className="extraction-note"><Sparkles size={15} /><span><b>Skills found in description</b> {allocation.extracted_skills.map((skill) => skill.skill).join(" · ")}</span><small>{allocation.skill_extractor}</small></div>
            )}
          </section>
        </div>
        <footer className="page-footer"><span>WORKFORCE STUDIO <i>·</i> SKILL-BASED ALLOCATION</span><span>Built for better teams <b>✳</b></span></footer>
      </main>
    </div>
  );
}

function Metric({ icon, label, value, suffix, tone }) {
  return <div className="metric-card"><span className={`metric-icon ${tone}`}>{icon}</span><span className="metric-label">{label}</span><b className="metric-value">{value}</b><small>{suffix}</small></div>;
}
