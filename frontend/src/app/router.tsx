import {
  Navigate,
  Outlet,
  createBrowserRouter,
  useLocation,
} from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { ChatPage } from "../features/chat/ChatPage";
import { CoursesPage } from "../features/courses/CoursesPage";
import { CourseWorkspace } from "../features/courses/CourseWorkspace";
import { DocumentsPage } from "../features/documents/DocumentsPage";
import { AnalyticsPage } from "../features/analytics/AnalyticsPage";
import { MistakesPage } from "../features/quizzes/MistakesPage";
import { QuizAttemptPage } from "../features/quizzes/QuizAttemptPage";
import { QuizListPage } from "../features/quizzes/QuizListPage";

function ProtectedRoute() {
  const { user, isChecking } = useAuth();
  const currentLocation = useLocation();
  if (isChecking) {
    return <main className="loading-screen" aria-live="polite">正在验证登录状态…</main>;
  }
  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: currentLocation.pathname }}
      />
    );
  }
  return <Outlet />;
}

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/courses" replace /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/courses", element: <CoursesPage /> },
      {
        path: "/courses/:courseId",
        element: <CourseWorkspace />,
        children: [
          { index: true, element: <Navigate to="chat" replace /> },
          { path: "chat", element: <ChatPage /> },
          { path: "documents", element: <DocumentsPage /> },
          { path: "quizzes", element: <QuizListPage /> },
          { path: "quizzes/:quizId", element: <QuizAttemptPage /> },
          { path: "mistakes", element: <MistakesPage /> },
          { path: "analytics", element: <AnalyticsPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/courses" replace /> },
]);
