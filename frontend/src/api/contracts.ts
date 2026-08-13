export interface ApiErrorPayload {
  code: string;
  message: string;
  request_id: string;
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface Course {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface AuthCredentials {
  email: string;
  password: string;
}

export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface CourseDocument {
  id: string;
  course_id: string;
  original_name: string;
  size_bytes: number;
  page_count: number | null;
  status: DocumentStatus;
  failure_code: string | null;
  failure_message: string | null;
  created_at: string;
  updated_at: string;
}
