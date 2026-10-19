import { useCallback, useEffect, useState } from "react";
import { apiGet, encodePath } from "../utils/api";

function RepositoryExplorer({ owner, repo }) {
  const [currentPath, setCurrentPath] = useState("");
  const [contents, setContents] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const repoBase = `/github/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;

  const loadDirectory = useCallback(
    async (path = "") => {
      setLoading(true);
      setError("");

      try {
        const data = await apiGet(
          `${repoBase}/directory/${encodePath(path)}`
        );

        setContents(data.contents);
        setCurrentPath(path);
        setSelectedFile(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [repoBase]
  );

  async function openFile(path) {
    setLoading(true);
    setError("");

    try {
      const data = await apiGet(`${repoBase}/file/${encodePath(path)}`);

      setSelectedFile(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadDirectory("");
  }, [loadDirectory]);

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

  // Breadcrumb segments, e.g. "src/utils" -> [src, src/utils]
  const segments = currentPath ? currentPath.split("/") : [];

  return (
    <section>
      <h2>Repository Explorer</h2>

      <nav aria-label="Current path">
        <button onClick={() => loadDirectory("")} disabled={loading}>
          {repo}
        </button>

        {segments.map((segment, index) => {
          const segmentPath = segments.slice(0, index + 1).join("/");

          return (
            <span key={segmentPath}>
              {" / "}
              <button
                onClick={() => loadDirectory(segmentPath)}
                disabled={loading || segmentPath === currentPath}
              >
                {segment}
              </button>
            </span>
          );
        })}
      </nav>

      {currentPath && (
        <button onClick={goUp} disabled={loading}>
          Go Up
        </button>
      )}

      {loading && <p>Loading...</p>}

      {error && <p role="alert">{error}</p>}

      {!loading && !error && contents.length === 0 && (
        <p>This directory is empty.</p>
      )}

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
