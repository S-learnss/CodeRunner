// Maps file extensions (and a few special file names) to highlight.js
// language ids plus a friendly label for the viewer header.

const BY_EXTENSION = {
  js: ["javascript", "JavaScript"],
  jsx: ["javascript", "JavaScript (JSX)"],
  mjs: ["javascript", "JavaScript"],
  cjs: ["javascript", "JavaScript"],
  ts: ["typescript", "TypeScript"],
  tsx: ["typescript", "TypeScript (TSX)"],
  py: ["python", "Python"],
  java: ["java", "Java"],
  kt: ["kotlin", "Kotlin"],
  c: ["c", "C"],
  h: ["c", "C"],
  cpp: ["cpp", "C++"],
  hpp: ["cpp", "C++"],
  cc: ["cpp", "C++"],
  cs: ["csharp", "C#"],
  go: ["go", "Go"],
  rs: ["rust", "Rust"],
  php: ["php", "PHP"],
  rb: ["ruby", "Ruby"],
  swift: ["swift", "Swift"],
  sql: ["sql", "SQL"],
  json: ["json", "JSON"],
  yml: ["yaml", "YAML"],
  yaml: ["yaml", "YAML"],
  toml: ["ini", "TOML"],
  ini: ["ini", "INI"],
  html: ["xml", "HTML"],
  htm: ["xml", "HTML"],
  xml: ["xml", "XML"],
  svg: ["xml", "SVG"],
  css: ["css", "CSS"],
  md: ["markdown", "Markdown"],
  sh: ["bash", "Shell"],
  bash: ["bash", "Shell"],
  ps1: ["powershell", "PowerShell"],
};

const BY_NAME = {
  dockerfile: ["dockerfile", "Dockerfile"],
  ".gitignore": ["bash", "Git ignore"],
  ".env.example": ["ini", "Environment"],
  "requirements.txt": ["plaintext", "Requirements"],
};

// Returns { id, label } where id is a highlight.js language or null.
export function detectLanguage(fileName) {
  const lower = fileName.toLowerCase();

  if (BY_NAME[lower]) {
    const [id, label] = BY_NAME[lower];
    return { id: id === "plaintext" ? null : id, label };
  }

  const dot = lower.lastIndexOf(".");
  const extension = dot === -1 ? "" : lower.slice(dot + 1);

  if (BY_EXTENSION[extension]) {
    const [id, label] = BY_EXTENSION[extension];
    return { id, label };
  }

  return { id: null, label: "Plain text" };
}

export function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
