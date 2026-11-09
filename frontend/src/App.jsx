import { useState } from "react";
import { parseGitHubUrl } from "./utils/github";
import RepositoryExplorer from "./components/RepositoryExplorer";
import StaticPreview from "./components/StaticPreview";
import { apiGet, apiPost } from "./utils/api";
import "./App.css";

function RunResult({ result }) {
  if (!result) return null;

  return (
    <section className={`run-result run-result--${result.status}`} aria-live="polite">
      <div className="run-result__header">
        <h4>Run {result.status.replaceAll("_", " ")}</h4>
        <span>
          {result.exit_code !== null ? `Exit code ${result.exit_code}` : "No exit code"}
          {` · ${result.duration_ms} ms`}
        </span>
      </div>
      {result.stdout && (
        <div className="run-output">
          <h5>Output</h5>
          <pre>{result.stdout}</pre>
        </div>
      )}
      {result.stderr && (
        <div className="run-output run-output--error">
          <h5>Error details</h5>
          <pre>{result.stderr}</pre>
        </div>
      )}
      {!result.stdout && !result.stderr && (
        <p className="run-result__empty">The script finished without printing output.</p>
      )}
    </section>
  );
}

function App() {
  const [githubUrl, setGithubUrl] = useState("");
  const [repository, setRepository] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [nodeRunning, setNodeRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [runError, setRunError] = useState("");
  const [nodeRunResult, setNodeRunResult] = useState(null);
  const [nodeRunError, setNodeRunError] = useState("");

  async function exploreRepository() {
    setError("");
    setRepository(null);
    setRunResult(null);
    setRunError("");
    setNodeRunResult(null);
    setNodeRunError("");

    if (!githubUrl.trim()) {
      setError("Please enter a GitHub repository URL.");
      return;
    }

    try {
      const { owner, repo } = parseGitHubUrl(githubUrl);

      setLoading(true);

      const data = await apiGet(
        `/github/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`
      );

      setRepository(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function runRepository() {
    if (!repository) return;

    setRunError("");
    setRunResult(null);
    setRunning(true);

    try {
      const data = await apiPost(
        `/github/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}/run`
      );
      setRunResult(data);
    } catch (error) {
      setRunError(error.message);
    } finally {
      setRunning(false);
    }
  }

  async function runNodeRepository() {
    if (!repository) return;

    setNodeRunError("");
    setNodeRunResult(null);
    setNodeRunning(true);

    try {
      const data = await apiPost(
        `/github/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}/run/node`
      );
      setNodeRunResult(data);
    } catch (error) {
      setNodeRunError(error.message);
    } finally {
      setNodeRunning(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="CodeRunner home">
          <span className="brand-mark" aria-hidden="true">C</span>
          <span>CodeRunner</span>
        </a>
        <span className="site-header__note">A simpler way to explore code</span>
      </header>

      <main id="top" className="page-content">
        <section className="welcome-section" aria-labelledby="welcome-title">
          <p className="eyebrow">LEARN BY EXPLORING</p>
          <h1 id="welcome-title">Try a project before setting it up.</h1>
          <p className="welcome-copy">
            Browse a public GitHub repository, preview a simple website, or run a
            small Python or JavaScript script in a restricted container.
          </p>

          <form
            className="repository-form"
            onSubmit={(event) => {
              event.preventDefault();
              exploreRepository();
            }}
          >
            <label htmlFor="repository-url">GitHub repository URL</label>
            <div className="repository-form__controls">
              <input
                id="repository-url"
                type="text"
                inputMode="url"
                autoComplete="url"
                value={githubUrl}
                onChange={(event) => setGithubUrl(event.target.value)}
                placeholder="https://github.com/owner/repository"
                aria-describedby="repository-hint"
              />
              <button className="button button--primary" type="submit" disabled={loading || running || nodeRunning}>
                {loading ? "Loading repository…" : "Explore repository"}
              </button>
            </div>
            <p id="repository-hint" className="field-hint">
              Start with a public repository URL. No downloads or setup needed.
            </p>
          </form>

          {error && <p className="message message--error" role="alert">{error}</p>}
        </section>

        {repository && (
          <div className="repository-workspace">
            <section className="repository-summary" aria-labelledby="repository-title">
              <div className="repository-summary__main">
                <p className="eyebrow">REPOSITORY</p>
                <h2 id="repository-title">{repository.name}</h2>
                <p className="repository-owner">by {repository.owner}</p>
                <p className="repository-description">
                  {repository.description || "This repository has no description yet."}
                </p>
              </div>
              <div className="repository-summary__aside">
                <div className="metadata-list" aria-label="Repository details">
                  <span>{repository.language || "Language not specified"}</span>
                  <span>{repository.stars} stars</span>
                  <span>{repository.forks} forks</span>
                </div>
                <a className="text-link" href={repository.url} target="_blank" rel="noreferrer">
                  View on GitHub <span aria-hidden="true">↗</span>
                </a>
              </div>
            </section>

            <div className="feature-grid">
              <section className="tool-card run-card" aria-labelledby="run-title">
                <p className="eyebrow">RUN A SCRIPT</p>
                <h3 id="run-title">Try the Python entry point</h3>
                <p className="tool-card__description">
                  Runs root-level <code>main.py</code> and its sibling Python
                  files using the standard library. Packages and subfolders
                  aren&apos;t included.
                </p>
                <button className="button button--primary" onClick={runRepository} disabled={running || nodeRunning}>
                  {running ? "Running script…" : "Run main.py"}
                </button>
                {runError && <p className="message message--error" role="alert">{runError}</p>}
                <RunResult result={runResult} />

                <section className="node-runner" aria-labelledby="node-run-title">
                  <p className="eyebrow">RUN JAVASCRIPT</p>
                  <h3 id="node-run-title">Try the Node.js entry point</h3>
                  <p className="tool-card__description">
                    Runs root-level <code>main.js</code> and sibling JavaScript
                    files with Node&apos;s standard library. Packages and
                    subfolders aren&apos;t included.
                  </p>
                  <button
                    className="button button--primary"
                    onClick={runNodeRepository}
                    disabled={running || nodeRunning}
                  >
                    {nodeRunning ? "Running JavaScript…" : "Run main.js with Node.js"}
                  </button>
                  {nodeRunError && <p className="message message--error" role="alert">{nodeRunError}</p>}
                  <RunResult result={nodeRunResult} />
                </section>
              </section>

              <StaticPreview repository={repository} />
            </div>

            <RepositoryExplorer owner={repository.owner} repo={repository.name} />
          </div>
        )}
      </main>

      <footer className="site-footer">
        <span>CodeRunner</span>
        <span>Explore first. Set up later.</span>
      </footer>
    </div>
  );
}

export default App;
