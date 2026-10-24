import { useEffect, useMemo, useRef, useState } from "react";
import hljs from "highlight.js/lib/core";

import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import csharp from "highlight.js/lib/languages/csharp";
import css from "highlight.js/lib/languages/css";
import dockerfile from "highlight.js/lib/languages/dockerfile";
import go from "highlight.js/lib/languages/go";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import kotlin from "highlight.js/lib/languages/kotlin";
import markdown from "highlight.js/lib/languages/markdown";
import php from "highlight.js/lib/languages/php";
import powershell from "highlight.js/lib/languages/powershell";
import python from "highlight.js/lib/languages/python";
import ruby from "highlight.js/lib/languages/ruby";
import rust from "highlight.js/lib/languages/rust";
import sql from "highlight.js/lib/languages/sql";
import swift from "highlight.js/lib/languages/swift";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

import { detectLanguage, formatBytes } from "../utils/language";
import "./FileViewer.css";

const LANGUAGES = {
  bash, c, cpp, csharp, css, dockerfile, go, ini, java, javascript, json,
  kotlin, markdown, php, powershell, python, ruby, rust, sql, swift,
  typescript, xml, yaml,
};

Object.entries(LANGUAGES).forEach(([name, definition]) => {
  hljs.registerLanguage(name, definition);
});

// Highlighting very large files can freeze the page, so skip it above
// this size and show plain text instead.
const MAX_HIGHLIGHT_CHARS = 200_000;

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function FileViewer({ file, onClose }) {
  const containerRef = useRef(null);
  const [copied, setCopied] = useState(false);

  const language = useMemo(() => detectLanguage(file.name), [file.name]);

  const skippedHighlight = file.content.length > MAX_HIGHLIGHT_CHARS;

  // highlight.js escapes the source it receives, so the HTML it returns
  // is safe to inject. Anything we can't highlight is escaped by hand.
  const html = useMemo(() => {
    if (!language.id || skippedHighlight) {
      return escapeHtml(file.content);
    }

    return hljs.highlight(file.content, {
      language: language.id,
      ignoreIllegals: true,
    }).value;
  }, [file.content, language.id, skippedHighlight]);

  // A trailing newline should not create an extra empty line number.
  const lineCount = useMemo(() => {
    if (file.content === "") {
      return 0;
    }

    const lines = file.content.split("\n").length;

    return file.content.endsWith("\n") ? lines - 1 : lines;
  }, [file.content]);

  const lineNumbers = useMemo(
    () => Array.from({ length: lineCount }, (_, i) => i + 1).join("\n"),
    [lineCount]
  );

  // Bring the viewer into view when a new file is opened.
  useEffect(() => {
    containerRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [file.path]);

  async function copyContents() {
    try {
      await navigator.clipboard.writeText(file.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be blocked; nothing useful to show.
    }
  }

  return (
    <div className="file-viewer" ref={containerRef}>
      <div className="file-viewer__header">
        <div className="file-viewer__title">
          <strong>{file.path}</strong>

          <span className="file-viewer__meta">
            {language.label} · {lineCount} {lineCount === 1 ? "line" : "lines"} ·{" "}
            {formatBytes(file.size)}
          </span>
        </div>

        <div className="file-viewer__actions">
          <button onClick={copyContents}>{copied ? "Copied!" : "Copy"}</button>

          <a href={file.url} target="_blank" rel="noreferrer">
            View on GitHub
          </a>

          <button onClick={onClose}>Close</button>
        </div>
      </div>

      {skippedHighlight && (
        <p className="file-viewer__notice">
          This file is large, so syntax highlighting was turned off.
        </p>
      )}

      {file.content === "" ? (
        <p className="file-viewer__empty">This file is empty.</p>
      ) : (
        <div className="file-viewer__body">
          <pre className="file-viewer__gutter" aria-hidden="true">
            {lineNumbers}
          </pre>

          <pre className="file-viewer__code">
            <code
              className="hljs"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          </pre>
        </div>
      )}
    </div>
  );
}

export default FileViewer;
