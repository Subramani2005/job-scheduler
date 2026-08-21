import { useState, useEffect, useCallback } from "react";
import api from "../api";

const STATUS_STYLES = {
  queued: { bg: "#F1EFE8", text: "#444441" },
  scheduled: { bg: "#E6F1FB", text: "#0C447C" },
  claimed: { bg: "#FAEEDA", text: "#854F0B" },
  running: { bg: "#FAEEDA", text: "#854F0B" },
  completed: { bg: "#EAF3DE", text: "#27500A" },
  failed: { bg: "#FCEBEB", text: "#791F1F" },
  retrying: { bg: "#FAECE7", text: "#712B13" },
  dead_letter: { bg: "#FCEBEB", text: "#501313" },
};

const POLL_MS = 3000;

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || { bg: "#F1EFE8", text: "#444441" };
  return (
    <span style={{
      background: s.bg, color: s.text, padding: "3px 10px",
      borderRadius: 20, fontSize: 12, fontWeight: 600,
    }}>
      {status.replace("_", " ")}
    </span>
  );
}

function EmptyState({ text }) {
  return (
    <div style={{ padding: "32px 0", textAlign: "center", color: "#9a988e", fontSize: 13 }}>
      {text}
    </div>
  );
}

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [queues, setQueues] = useState([]);
  const [selectedQueue, setSelectedQueue] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [newQueueName, setNewQueueName] = useState("");
  const [newJobName, setNewJobName] = useState("");

  const loadProjects = useCallback(async () => {
    const res = await api.get("/projects");
    setProjects(res.data);
  }, []);

  const loadQueues = useCallback(async (projectId) => {
    const res = await api.get(`/projects/${projectId}/queues`);
    setQueues(res.data);
  }, []);

  const loadJobs = useCallback(async (queueId, status) => {
    const params = status ? { status } : {};
    const res = await api.get(`/queues/${queueId}/jobs`, { params });
    setJobs(res.data);
  }, []);

  useEffect(() => { loadProjects(); }, [loadProjects]);
  useEffect(() => { if (selectedProject) loadQueues(selectedProject); }, [selectedProject, loadQueues]);

  useEffect(() => {
    if (!selectedQueue) return;
    loadJobs(selectedQueue, statusFilter);
    const interval = setInterval(() => loadJobs(selectedQueue, statusFilter), POLL_MS);
    return () => clearInterval(interval);
  }, [selectedQueue, statusFilter, loadJobs]);

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    await api.post("/projects", { name: newProjectName });
    setNewProjectName("");
    loadProjects();
  };

  const createQueue = async () => {
    if (!newQueueName.trim() || !selectedProject) return;
    await api.post(`/projects/${selectedProject}/queues`, { name: newQueueName });
    setNewQueueName("");
    loadQueues(selectedProject);
  };

  const createJob = async () => {
    if (!newJobName.trim() || !selectedQueue) return;
    await api.post(`/queues/${selectedQueue}/jobs`, {
      name: newJobName, job_type: "example", payload: { source: "dashboard" }
    });
    setNewJobName("");
    loadJobs(selectedQueue, statusFilter);
  };

  const logout = () => {
    localStorage.removeItem("token");
    window.location.reload();
  };

  const counts = jobs.reduce((acc, j) => { acc[j.status] = (acc[j.status] || 0) + 1; return acc; }, {});

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={styles.logoDot} />
          <span style={styles.brandName}>Job Scheduler</span>
        </div>
        <button onClick={logout} style={styles.logoutButton}>Log out</button>
      </header>

      <div style={styles.container}>
        <div style={styles.grid}>
          {/* Projects column */}
          <div style={styles.panel}>
            <div style={styles.panelHeader}>Projects</div>
            <div style={styles.panelBody}>
              <div style={styles.addRow}>
                <input
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="New project name"
                  style={styles.input}
                  onKeyDown={(e) => e.key === "Enter" && createProject()}
                />
                <button onClick={createProject} style={styles.addButton}>Add</button>
              </div>
              {projects.length === 0 ? (
                <EmptyState text="No projects yet. Create one above." />
              ) : (
                <div style={styles.list}>
                  {projects.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => { setSelectedProject(p.id); setSelectedQueue(null); setJobs([]); }}
                      style={{
                        ...styles.listItem,
                        ...(selectedProject === p.id ? styles.listItemActive : {}),
                      }}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Queues column */}
          <div style={styles.panel}>
            <div style={styles.panelHeader}>Queues</div>
            <div style={styles.panelBody}>
              {!selectedProject ? (
                <EmptyState text="Select a project first." />
              ) : (
                <>
                  <div style={styles.addRow}>
                    <input
                      value={newQueueName}
                      onChange={(e) => setNewQueueName(e.target.value)}
                      placeholder="New queue name"
                      style={styles.input}
                      onKeyDown={(e) => e.key === "Enter" && createQueue()}
                    />
                    <button onClick={createQueue} style={styles.addButton}>Add</button>
                  </div>
                  {queues.length === 0 ? (
                    <EmptyState text="No queues yet. Create one above." />
                  ) : (
                    <div style={styles.list}>
                      {queues.map((q) => (
                        <button
                          key={q.id}
                          onClick={() => setSelectedQueue(q.id)}
                          style={{
                            ...styles.listItem,
                            ...(selectedQueue === q.id ? styles.listItemActive : {}),
                          }}
                        >
                          {q.name}
                          {q.is_paused && <span style={styles.pausedTag}>paused</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Jobs section */}
        {selectedQueue && (
          <div style={{ ...styles.panel, marginTop: 16 }}>
            <div style={styles.panelHeader}>Jobs</div>
            <div style={styles.panelBody}>

              <div style={styles.statsRow}>
                {["queued", "running", "completed", "failed", "dead_letter"].map((s) => (
                  <div key={s} style={styles.statCard}>
                    <div style={styles.statLabel}>{s.replace("_", " ")}</div>
                    <div style={styles.statValue}>{counts[s] || 0}</div>
                  </div>
                ))}
              </div>

              <div style={{ ...styles.addRow, marginTop: 16 }}>
                <input
                  value={newJobName}
                  onChange={(e) => setNewJobName(e.target.value)}
                  placeholder="New job name"
                  style={styles.input}
                  onKeyDown={(e) => e.key === "Enter" && createJob()}
                />
                <button onClick={createJob} style={styles.addButton}>Enqueue job</button>

                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  style={styles.select}
                >
                  <option value="">All statuses</option>
                  {Object.keys(STATUS_STYLES).map((s) => (
                    <option key={s} value={s}>{s.replace("_", " ")}</option>
                  ))}
                </select>
              </div>

              {jobs.length === 0 ? (
                <EmptyState text="No jobs match this filter." />
              ) : (
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Name</th>
                      <th style={styles.th}>Status</th>
                      <th style={styles.th}>Attempts</th>
                      <th style={styles.th}>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((j) => (
                      <tr key={j.id} style={styles.tr}>
                        <td style={styles.td}>{j.name}</td>
                        <td style={styles.td}><StatusBadge status={j.status} /></td>
                        <td style={styles.td}>{j.attempt_count}</td>
                        <td style={styles.td}>{new Date(j.created_at).toLocaleTimeString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#f6f5f2", fontFamily: "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" },
  header: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "14px 28px", background: "#ffffff", borderBottom: "1px solid #e5e3dd",
  },
  logoDot: { width: 10, height: 10, borderRadius: "50%", background: "#378ADD" },
  brandName: { fontSize: 14, fontWeight: 700, color: "#1f1e1c" },
  logoutButton: {
    padding: "6px 14px", fontSize: 13, fontWeight: 600, background: "transparent",
    border: "1px solid #e5e3dd", borderRadius: 8, color: "#444441",
  },
  container: { maxWidth: 980, margin: "24px auto", padding: "0 20px" },
  grid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 },
  panel: { background: "#ffffff", border: "1px solid #e5e3dd", borderRadius: 12, overflow: "hidden" },
  panelHeader: {
    padding: "12px 18px", fontSize: 13, fontWeight: 700, color: "#1f1e1c",
    borderBottom: "1px solid #e5e3dd", background: "#faf9f7", textTransform: "uppercase", letterSpacing: 0.4,
  },
  panelBody: { padding: 18 },
  addRow: { display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" },
  input: {
    flex: 1, minWidth: 120, padding: "8px 12px", fontSize: 13,
    border: "1px solid #e5e3dd", borderRadius: 8, outline: "none", background: "#faf9f7",
  },
  select: {
    padding: "8px 10px", fontSize: 13, border: "1px solid #e5e3dd", borderRadius: 8, background: "#faf9f7",
  },
  addButton: {
    padding: "8px 16px", fontSize: 13, fontWeight: 600, background: "#1f1e1c",
    color: "#fff", border: "none", borderRadius: 8, whiteSpace: "nowrap",
  },
  list: { display: "flex", flexDirection: "column", gap: 6 },
  listItem: {
    textAlign: "left", padding: "9px 12px", fontSize: 13, background: "#faf9f7",
    border: "1px solid #e5e3dd", borderRadius: 8, color: "#1f1e1c", fontWeight: 500,
    display: "flex", alignItems: "center", gap: 8,
  },
  listItemActive: { background: "#E6F1FB", border: "1px solid #85B7EB", color: "#0C447C" },
  pausedTag: { fontSize: 11, color: "#854F0B", background: "#FAEEDA", padding: "1px 6px", borderRadius: 10 },
  statsRow: { display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 },
  statCard: { background: "#faf9f7", borderRadius: 8, padding: "10px 12px" },
  statLabel: { fontSize: 11, color: "#9a988e", textTransform: "capitalize", marginBottom: 4 },
  statValue: { fontSize: 20, fontWeight: 700, color: "#1f1e1c" },
  table: { width: "100%", borderCollapse: "collapse", marginTop: 6 },
  th: {
    textAlign: "left", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.4,
    color: "#9a988e", padding: "8px 6px", borderBottom: "1px solid #e5e3dd",
  },
  tr: { borderBottom: "1px solid #f0efe9" },
  td: { padding: "10px 6px", fontSize: 13, color: "#1f1e1c" },
};
