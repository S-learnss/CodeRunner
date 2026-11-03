import { useState } from "react";
import { apiGet, encodePath } from "../utils/api";

function escapeAttribute(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

function buildPreviewDocument(html, repository) {
  const branchPath = repository.default_branch
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  const rawBase = `https://raw.githubusercontent.com/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}/${branchPath}/`;
  const policy = "default-src 'none'; script-src 'unsafe-inline' https://raw.githubusercontent.com; style-src 'unsafe-inline' https://raw.githubusercontent.com; img-src data: https://raw.githubusercontent.com; font-src data: https://raw.githubusercontent.com; media-src https://raw.githubusercontent.com; connect-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'; base-uri https://raw.githubusercontent.com";
  const injected = `<meta http-equiv="Content-Security-Policy" content="${policy}"><base href="${escapeAttribute(rawBase)}">`;
  const head = /<head(?:\s[^>]*)?>/i;

  if (head.test(html)) {
    return html.replace(head, (openingTag) => `${openingTag}${injected}`);
  }

  return `<!doctype html><html><head>${injected}</head><body>${html}</body></html>`;
}

function StaticPreview({ repository }) {
  const [document, setDocument] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadPreview() {
    setLoading(true);
    setError("");
    setDocument("");

    try {
      const base = `/github/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}`;
      const file = await apiGet(`${base}/file/${encodePath("index.html")}`);
      setDocument(buildPreviewDocument(file.content, repository));
    } catch (err) {
      setError(err.message || "Could not load this repository's index.html.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-label="Static site preview">
      <h2>Static site preview</h2>
      <p>Previews a root-level index.html with its relative static assets.</p>
      <button onClick={loadPreview} disabled={loading}>
        {loading ? "Loading preview..." : "Preview website"}
      </button>
      {error && <p role="alert">{error}</p>}
      {document && (
        <iframe
          title={`${repository.name} static site preview`}
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          srcDoc={document}
          style={{ width: "100%", minHeight: "480px", border: "1px solid #888" }}
        />
      )}
    </section>
  );
}

export default StaticPreview;
