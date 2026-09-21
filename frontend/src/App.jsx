import { useState } from "react";

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
      const url = new URL(githubUrl);

      if (url.hostname !== "github.com") {
        setError("Please enter a GitHub repository URL.");
        return;
      }

      const parts = url.pathname.split("/").filter(Boolean);

      if (parts.length < 2) {
        setError("Please enter a valid GitHub repository URL.");
        return;
      }

      const owner = parts[0];
      const repo = parts[1];

      setLoading(true);

      const response = await fetch(
        `http://127.0.0.1:8000/github/${owner}/${repo}`
      );

      const data = await response.json();

      if (!response.ok || data.error) {
        setError(data.error || "Failed to retrieve repository.");
        return;
      }

      setRepository(data);
    } catch (error) {
      setError("Please enter a valid GitHub URL.");
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

      <input
        type="text"
        value={githubUrl}
        onChange={(event) => setGithubUrl(event.target.value)}
        placeholder="https://github.com/user/repository"
      />

      <button onClick={exploreRepository} disabled={loading}>
        {loading ? "Exploring..." : "Explore Repository"}
      </button>

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
        </section>
      )}
    </main>
  );
}

export default App;