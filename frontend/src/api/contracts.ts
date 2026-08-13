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

export interface Conversation {
  id: string;
  course_id: string;
  created_at: string;
  updated_at: string;
}

export interface MessageCitation {
  source_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  snippet: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  refused: boolean;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number | null;
  citations: MessageCitation[];
  created_at: string;
}

export interface WeakTopic {
  knowledge_point: string;
  answered_count: number;
  wrong_count: number;
  weak_score: number;
}

export interface CourseAnalytics {
  total_questions: number;
  total_attempts: number;
  average_percent_score: number;
  weak_topics: WeakTopic[];
  recent_attempts: unknown[];
}
