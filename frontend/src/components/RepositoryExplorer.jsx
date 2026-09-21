import { useEffect, useState } from "react";

function RepositoryExplorer({ owner, repo }) {
  const [currentPath, setCurrentPath] = useState("");
  const [contents, setContents] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadDirectory(path = "") {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/github/${owner}/${repo}/directory/${path}`
      );

      const data = await response.json();

      if (!response.ok || data.error) {
        setError(data.error || "Unable to load directory.");
        return;
      }

      setContents(data.contents);
      setCurrentPath(path);
      setSelectedFile(null);
    } catch (error) {
      setError("Could not connect to the CodeRunner backend.");
    } finally {
      setLoading(false);
    }
  }

  async function openFile(path) {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/github/${owner}/${repo}/file/${path}`
      );

      const data = await response.json();

      if (!response.ok || data.error) {
        setError(data.error || "Unable to load file.");
        return;
      }

      setSelectedFile(data);
    } catch (error) {
      setError("Could not load the file.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDirectory("");
  }, [owner, repo]);

  function handleItemClick(item) {
    if (item.type === "dir") {
      loadDirectory(item.path);
    } else {
      openFile(item.path);
    }
  }

  function goUp() {
    if (!currentPath) {
      return;
    }

    const parts = currentPath.split("/");
    parts.pop();

    loadDirectory(parts.join("/"));
  }

  return (
    <section>
      <h2>Repository Explorer</h2>

      <p>
        <strong>Path:</strong> /{currentPath}
      </p>

      {currentPath && (
        <button onClick={goUp}>
          Go Up
        </button>
      )}

      {loading && <p>Loading...</p>}

      {error && <p>{error}</p>}

      {!loading && !error && (
        <div>
          {contents.map((item) => (
            <button
              key={item.path}
              onClick={() => handleItemClick(item)}
            >
              {item.type === "dir" ? "📁" : "📄"} {item.name}
            </button>
          ))}
        </div>
      )}

      {selectedFile && (
        <div>
          <h3>{selectedFile.path}</h3>

          <pre>
            <code>{selectedFile.content}</code>
          </pre>
        </div>
      )}
    </section>
  );
}

export default RepositoryExplorer;