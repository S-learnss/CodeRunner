import { useState } from "react";
import { parseGitHubUrl } from "./utils/github";
import RepositoryExplorer from "./components/RepositoryExplorer";
import { apiGet } from "./utils/api";

function App() {
  const [githubUrl, setGithubUrl] = useState("");
  const [repository, setRepository] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function exploreRepository() {
    setError("");
    setRepository(null);

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

        <button onClick={exploreRepository} disabled={loading}>
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