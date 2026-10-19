// Base URL of the CodeRunner backend.
// Override it by setting VITE_API_URL in a frontend/.env file.
export const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
