import { useState } from "react";
import { parseGitHubUrl } from "./utils/github";
import RepositoryExplorer from "./components/RepositoryExplorer";
import { apiGet, apiPost } from "./utils/api";

function App() {
  const [githubUrl, setGithubUrl] = useState("");
  const [repository, setRepository] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [runError, setRunError] = useState("");

  async function exploreRepository() {
    setError("");
    setRepository(null);
    setRunResult(null);
    setRunError("");

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

  return (
    <main>
      <h1>CodeRunner</h1>

      <p>
        Explore a GitHub repository through CodeRunner.
      </p>

      <div>
        <input
          type="text"
          value={githubUrl}
          onChange={(event) => setGithubUrl(event.target.value)}
          placeholder="https://github.com/user/repository"
        />

        <button onClick={exploreRepository} disabled={loading || running}>
          {loading ? "Exploring..." : "Explore Repository"}
        </button>
      </div>

      {error && <p>{error}</p>}

      {repository && (
        <section>
          <h2>{repository.name}</h2>

          <p>
            <strong>Owner:</strong> {repository.owner}
          </p>

          <p>
            <strong>Language:</strong>{" "}
            {repository.language || "Not specified"}
          </p>

          <p>
            <strong>Stars:</strong> {repository.stars}
          </p>

          <p>
            <strong>Forks:</strong> {repository.forks}
          </p>

          <p>
            {repository.description || "No description available."}
          </p>

          <a
            href={repository.url}
            target="_blank"
            rel="noreferrer"
          >
            View on GitHub
          </a>

          <div>
            <button onClick={runRepository} disabled={running}>
              {running ? "Running..." : "Run main.py"}
            </button>
            <p>
              Runs the repository's root-level main.py with Python's standard
              library. The first version does not install packages.
            </p>
          </div>

          {runError && <p role="alert">{runError}</p>}

          {runResult && (
            <section aria-live="polite">
              <h3>
                Run {runResult.status}
                {runResult.exit_code !== null && ` (exit code ${runResult.exit_code})`}
              </h3>
              <p>Finished in {runResult.duration_ms} ms.</p>
              {runResult.stdout && (
                <div>
                  <h4>Output</h4>
                  <pre>{runResult.stdout}</pre>
                </div>
              )}
              {runResult.stderr && (
                <div>
                  <h4>Error details</h4>
                  <pre>{runResult.stderr}</pre>
                </div>
              )}
            </section>
          )}

          {/* Repository Explorer */}
          <RepositoryExplorer
            owner={repository.owner}
            repo={repository.name}
          />
        </section>
      )}
    </main>
  );
}

export default App;
