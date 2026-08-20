import { useState, useEffect, useCallback } from "react";
import api from "../api";

const STATUS_COLORS = {
  queued: "#888", scheduled: "#3b82f6", claimed: "#f59e0b",
  running: "#f59e0b", completed: "#22c55e", failed: "#ef4444",
  retrying: "#f97316", dead_letter: "#991b1b",
};

// WHY polling (setInterval + refetch) instead of WebSockets for live
// updates: WebSockets would be the "more real-time" choice, but they need
// a persistent connection layer (extra server setup, reconnect handling,
// scaling considerations behind a load balancer). For a dashboard where
// a few seconds of staleness is completely acceptable, polling gets 90%
// of the perceived responsiveness for a fraction of the implementation
// and infra cost -- the right trade-off given the 2-day timeline. This is
// worth saying explicitly if asked "why not real-time."
const POLL_MS = 3000;

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

  useEffect(() => {
    if (selectedProject) loadQueues(selectedProject);
  }, [selectedProject, loadQueues]);

  // WHY polling lives in its own effect keyed on [selectedQueue, statusFilter]:
  // isolates the "keep refetching" concern from the "user changed selection"
  // concern -- changing queue or filter naturally resets the interval instead
  // of needing manual interval-clearing logic scattered elsewhere.
  useEffect(() => {
    if (!selectedQueue) return;
    loadJobs(selectedQueue, statusFilter);
    const interval = setInterval(() => loadJobs(selectedQueue, statusFilter), POLL_MS);
    return () => clearInterval(interval);
  }, [selectedQueue, statusFilter, loadJobs]);

  const createProject = async () => {
    if (!newProjectName) return;
    await api.post("/projects", { name: newProjectName });
    setNewProjectName("");
    loadProjects();
  };

  const createQueue = async () => {
    if (!newQueueName || !selectedProject) return;
    await api.post(`/projects/${selectedProject}/queues`, { name: newQueueName });
    setNewQueueName("");
    loadQueues(selectedProject);
  };

  const createJob = async () => {
    if (!newJobName || !selectedQueue) return;
    await api.post(`/queues/${selectedQueue}/jobs`, {
      name: newJobName, job_type: "example", payload: { source: "dashboard" }
    });
    setNewJobName("");
    loadJobs(selectedQueue, statusFilter);
  };

  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: 900, margin: "40px auto" }}>
      <h2>Job Scheduler Dashboard</h2>

      <section style={{ marginBottom: 24 }}>
        <h4>Projects</h4>
        <input value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} placeholder="new project name" />
        <button onClick={createProject}>Create</button>
        <div style={{ marginTop: 8 }}>
          {projects.map((p) => (
            <button key={p.id} onClick={() => setSelectedProject(p.id)}
              style={{ marginRight: 8, fontWeight: selectedProject === p.id ? "bold" : "normal" }}>
              {p.name}
            </button>
          ))}
        </div>
      </section>

      {selectedProject && (
        <section style={{ marginBottom: 24 }}>
          <h4>Queues</h4>
          <input value={newQueueName} onChange={(e) => setNewQueueName(e.target.value)} placeholder="new queue name" />
          <button onClick={createQueue}>Create</button>
          <div style={{ marginTop: 8 }}>
            {queues.map((q) => (
              <button key={q.id} onClick={() => setSelectedQueue(q.id)}
                style={{ marginRight: 8, fontWeight: selectedQueue === q.id ? "bold" : "normal" }}>
                {q.name} {q.is_paused ? "(paused)" : ""}
              </button>
            ))}
          </div>
        </section>
      )}

      {selectedQueue && (
        <section>
          <h4>Jobs</h4>
          <input value={newJobName} onChange={(e) => setNewJobName(e.target.value)} placeholder="new job name" />
          <button onClick={createJob}>Enqueue Job</button>

          <div style={{ margin: "12px 0" }}>
            <label>Filter: </label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">all</option>
              {Object.keys(STATUS_COLORS).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #ccc", textAlign: "left" }}>
                <th>Name</th><th>Status</th><th>Attempts</th><th>Created</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} style={{ borderBottom: "1px solid #eee" }}>
                  <td>{j.name}</td>
                  <td>
                    <span style={{
                      color: "white", background: STATUS_COLORS[j.status] || "#888",
                      padding: "2px 8px", borderRadius: 4, fontSize: 12
                    }}>
                      {j.status}
                    </span>
                  </td>
                  <td>{j.attempt_count}</td>
                  <td>{new Date(j.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}