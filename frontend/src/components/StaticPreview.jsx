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
  const assetBase = `https://cdn.jsdelivr.net/gh/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}@${branchPath}/`;
  const policy = "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'unsafe-inline' https://cdn.jsdelivr.net; img-src data: https://cdn.jsdelivr.net; font-src data: https://cdn.jsdelivr.net; media-src https://cdn.jsdelivr.net; connect-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'; base-uri https://cdn.jsdelivr.net";
  const injected = `<meta http-equiv="Content-Security-Policy" content="${policy}"><base href="${escapeAttribute(assetBase)}">`;
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
      setError(
        err.message === "File not found"
          ? "This repository doesn't have a root-level index.html to preview."
          : err.message || "Could not load this repository's index.html."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="tool-card preview-card" aria-labelledby="preview-title">
      <p className="eyebrow">WEBSITE PREVIEW</p>
      <h3 id="preview-title">See the project in your browser</h3>
      <p className="tool-card__description">
        Opens a root-level <code>index.html</code> with its existing styles and scripts.
      </p>
      <button className="button button--secondary" onClick={loadPreview} disabled={loading}>
        {loading ? "Loading preview..." : "Preview website"}
      </button>
      {error && <p className="message message--error" role="alert">{error}</p>}
      {document && (
        <iframe
          className="site-preview"
          title={`${repository.name} static site preview`}
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          srcDoc={document}
        />
      )}
    </section>
  );
}

export default StaticPreview;
