import { useEffect, useMemo, useState } from "react";
import { createJob, getJob, getTransactions, startJob } from "./api";

const pageSize = 12;

function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

function formatAmount(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isTerminal = useMemo(() => {
    if (!job) {
      return false;
    }
    return job.status === "completed" || job.status === "failed";
  }, [job]);

  async function handleUpload() {
    if (!selectedFile) {
      setError("Please choose a CSV file first.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const data = await createJob(selectedFile);
      setJobId(data.id);
      setPage(1);
      setTransactions([]);
      const statusData = await getJob(data.id);
      setJob(statusData);
    } catch (uploadError) {
      setError(uploadError?.response?.data?.detail || "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleStart() {
    if (!jobId) {
      setError("Upload a file first.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const data = await startJob(jobId);
      setJob(data);
    } catch (startError) {
      setError(startError?.response?.data?.detail || "Unable to start job.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!jobId) {
      return undefined;
    }

    let cancelled = false;

    async function pullStatusAndTransactions() {
      try {
        const [jobData, transactionsData] = await Promise.all([
          getJob(jobId),
          getTransactions(jobId, page, pageSize, filter),
        ]);

        if (cancelled) {
          return;
        }

        setJob(jobData);
        setTransactions(transactionsData.items);
        setTotalPages(transactionsData.total_pages);
        setTotalItems(transactionsData.total_items);
      } catch (refreshError) {
        if (!cancelled) {
          setError(refreshError?.response?.data?.detail || "Error fetching job updates.");
        }
      }
    }

    pullStatusAndTransactions();

    const interval = setInterval(() => {
      pullStatusAndTransactions();
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId, page, filter]);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <h1>Batch Processing Monitor</h1>
        <p>Upload transactions, run the batch processor, and track every record in near real time.</p>

        <div className="upload-row">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
          />
          <button onClick={handleUpload} disabled={loading}>
            Upload CSV
          </button>
          <button onClick={handleStart} disabled={loading || !jobId || (job?.status === "running") }>
            Start Processing
          </button>
        </div>

        {jobId && (
          <p className="meta-line">
            Active Job ID: <span>{jobId}</span>
          </p>
        )}

        {error && <p className="error-text">{error}</p>}
      </section>

      {job && (
        <section className="status-card">
          <div className="status-header">
            <h2>Job Status</h2>
            <span className={`badge badge-${job.status}`}>{job.status}</span>
          </div>

          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${job.progress_percent}%` }} />
          </div>
          <p className="meta-line">Progress: {job.progress_percent}%</p>

          <div className="stats-grid">
            <article>
              <h3>Total</h3>
              <p>{job.total_records}</p>
            </article>
            <article>
              <h3>Processed</h3>
              <p>{job.processed_records}</p>
            </article>
            <article>
              <h3>Valid</h3>
              <p>{job.valid_records}</p>
            </article>
            <article>
              <h3>Invalid</h3>
              <p>{job.invalid_records}</p>
            </article>
          </div>

          <p className="meta-line">Started: {formatDate(job.started_at)}</p>
          <p className="meta-line">Completed: {formatDate(job.completed_at)}</p>
          {job.error_message && <p className="error-text">Failure: {job.error_message}</p>}
        </section>
      )}

      {jobId && (
        <section className="results-card">
          <div className="results-top-bar">
            <h2>Processed Transactions</h2>
            <div className="filter-group">
              <label htmlFor="statusFilter">Filter</label>
              <select
                id="statusFilter"
                value={filter}
                onChange={(event) => {
                  setFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="all">All</option>
                <option value="valid">Valid</option>
                <option value="invalid">Invalid</option>
                <option value="suspicious">Suspicious</option>
              </select>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Transaction ID</th>
                  <th>User ID</th>
                  <th>Amount</th>
                  <th>Timestamp</th>
                  <th>Flags</th>
                  <th>Errors</th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 && (
                  <tr>
                    <td colSpan={6} className="empty-row">
                      No records yet.
                    </td>
                  </tr>
                )}
                {transactions.map((row) => (
                  <tr key={row.id}>
                    <td>{row.transaction_id || row.transaction_id_raw || "-"}</td>
                    <td>{row.user_id || row.user_id_raw || "-"}</td>
                    <td>{formatAmount(row.amount ?? row.amount_raw)}</td>
                    <td>{row.timestamp ? formatDate(row.timestamp) : row.timestamp_raw || "-"}</td>
                    <td>
                      {row.is_valid ? "valid" : "invalid"}
                      {row.is_suspicious ? " / suspicious" : ""}
                    </td>
                    <td>{row.error_reasons?.length ? row.error_reasons.join("; ") : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination-row">
            <span>
              Showing page {page} of {totalPages} ({totalItems} records)
            </span>
            <div>
              <button onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1}>
                Prev
              </button>
              <button
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                disabled={page >= totalPages}
              >
                Next
              </button>
            </div>
          </div>

          {isTerminal && <p className="meta-line">Job is in terminal state. Polling continues until you upload a new file.</p>}
        </section>
      )}
    </main>
  );
}
