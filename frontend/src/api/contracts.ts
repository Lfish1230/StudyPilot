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
  recent_attempts: RecentAttempt[];
}

export type QuizQuestionType = "multiple_choice" | "short_answer";

export interface QuizSummary {
  id: string;
  course_id: string;
  title: string;
  question_count: number;
  created_at: string;
}

interface QuizQuestionBase {
  id: string;
  position: number;
  prompt: string;
  knowledge_point: string;
  difficulty: "easy" | "medium" | "hard";
  source_document_id: string;
  source_document_name: string;
  source_page: number;
}

export interface MultipleChoiceQuizQuestion extends QuizQuestionBase {
  type: "multiple_choice";
  options: string[];
}

export interface ShortAnswerQuizQuestion extends QuizQuestionBase {
  type: "short_answer";
  options: null;
}

export type QuizQuestion = MultipleChoiceQuizQuestion | ShortAnswerQuizQuestion;

export interface QuizDetail extends QuizSummary {
  questions: QuizQuestion[];
}

export interface AnswerResult {
  question_id: string;
  type: QuizQuestionType;
  prompt: string;
  user_answer: string;
  standard_answer: string;
  explanation: string;
  score: number;
  is_correct: boolean;
  feedback: string;
  missing_points: string[];
  knowledge_point: string;
  source_document_id: string;
  source_document_name: string;
  source_page: number;
}

export interface QuizAttempt {
  id: string;
  quiz_id: string;
  total_score: number;
  max_score: number;
  percentage: number;
  submitted_at: string;
  answers: AnswerResult[];
}

export interface Mistake extends Omit<AnswerResult, "is_correct"> {
  attempt_id: string;
  quiz_id: string;
  quiz_title: string;
  submitted_at: string;
}

export interface RecentAttempt {
  attempt_id: string;
  quiz_id: string;
  quiz_title: string;
  total_score: number;
  max_score: number;
  percentage: number;
  submitted_at: string;
}
