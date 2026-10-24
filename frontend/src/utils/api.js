import { API_URL } from "../config";

// Encode each path segment but keep the "/" separators.
export function encodePath(path) {
  return path.split("/").map(encodeURIComponent).join("/");
}

// Fetch JSON from the backend and throw a readable error on failure.
// FastAPI reports errors as { detail: "..." }.
export async function apiGet(endpoint) {
  let response;

  try {
    response = await fetch(`${API_URL}${endpoint}`);
  } catch {
    throw new Error("Could not connect to the CodeRunner backend.");
  }

  let data = null;

  try {
    data = await response.json();
  } catch {
    // Non-JSON response; handled below.
  }

  if (!response.ok) {
    const message =
      (data && (data.detail || data.error)) ||
      `Request failed (${response.status}).`;

    throw new Error(
      typeof message === "string" ? message : "Request failed."
    );
  }

  return data;
}

export async function apiPost(endpoint) {
  let response;

  try {
    response = await fetch(`${API_URL}${endpoint}`, { method: "POST" });
  } catch {
    throw new Error("Could not connect to the CodeRunner backend.");
  }

  let data = null;

  try {
    data = await response.json();
  } catch {
    // Non-JSON response; handled below.
  }

  if (!response.ok) {
    const message =
      (data && (data.detail || data.error)) ||
      `Request failed (${response.status}).`;

    throw new Error(
      typeof message === "string" ? message : "Request failed."
    );
  }

  return data;
}
