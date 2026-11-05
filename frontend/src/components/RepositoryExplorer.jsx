import { useCallback, useEffect, useState } from "react";
import { apiGet, encodePath } from "../utils/api";
import FileViewer from "./FileViewer";

function RepositoryExplorer({ owner, repo }) {
  const [currentPath, setCurrentPath] = useState("");
  const [contents, setContents] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fileLoading, setFileLoading] = useState(false);
  const [error, setError] = useState("");
  const [fileError, setFileError] = useState("");

  const repoBase = `/github/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;

  const loadDirectory = useCallback(
    async (path = "") => {
      setLoading(true);
      setError("");
      setFileError("");

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
    setFileLoading(true);
    setFileError("");

    try {
      const data = await apiGet(`${repoBase}/file/${encodePath(path)}`);

      setSelectedFile(data);
    } catch (err) {
      // Keep the folder list visible so the user can pick another file.
      setSelectedFile(null);
      setFileError(err.message);
    } finally {
      setFileLoading(false);
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
    <section className="explorer-panel" aria-labelledby="explorer-title">
      <div className="explorer-panel__header">
        <div>
          <p className="eyebrow">BROWSE FILES</p>
          <h2 id="explorer-title">Repository explorer</h2>
        </div>
        <nav className="breadcrumbs" aria-label="Current path">
          <button onClick={() => loadDirectory("")} disabled={loading}>
            {repo}
          </button>

          {segments.map((segment, index) => {
            const segmentPath = segments.slice(0, index + 1).join("/");

            return (
              <span className="breadcrumbs__segment" key={segmentPath}>
                <span aria-hidden="true">/</span>
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
      </div>

      {currentPath && (
        <button className="button button--quiet explorer-panel__up" onClick={goUp} disabled={loading}>
          ← Up one folder
        </button>
      )}

      {loading && <p className="loading-message" role="status">Loading files…</p>}

      {error && <p className="message message--error" role="alert">{error}</p>}

      {!loading && !error && contents.length === 0 && (
        <p className="empty-message">This folder is empty.</p>
      )}

      {!loading && !error && (
        <div className="repository-list" aria-label="Repository files">
          {contents.map((item) => (
            <button
              className="repository-list__item"
              key={item.path}
              onClick={() => handleItemClick(item)}
              disabled={fileLoading}
              aria-current={
                selectedFile && selectedFile.path === item.path
                  ? "true"
                  : undefined
              }
            >
              <span className={`repository-list__kind repository-list__kind--${item.type}`}>
                {item.type === "dir" ? "FOLDER" : "FILE"}
              </span>
              <span className="repository-list__name">{item.name}</span>
              {item.type === "dir" && <span className="repository-list__arrow" aria-hidden="true">→</span>}
            </button>
          ))}
        </div>
      )}

      {fileLoading && <p className="loading-message" role="status">Opening file…</p>}

      {fileError && <p className="message message--error" role="alert">{fileError}</p>}

      {selectedFile && (
        <FileViewer
          file={selectedFile}
          onClose={() => setSelectedFile(null)}
        />
      )}
    </section>
  );
}

export default RepositoryExplorer;
