export function parseGitHubUrl(githubUrl) {
  const url = new URL(githubUrl);

  if (url.hostname !== "github.com") {
    throw new Error("Please enter a GitHub repository URL.");
  }

  const parts = url.pathname.split("/").filter(Boolean);

  if (parts.length < 2) {
    throw new Error("Please enter a valid GitHub repository URL.");
  }

  const owner = parts[0];
  const repo = parts[1].replace(/\.git$/, "");

  return {
    owner,
    repo,
  };
}