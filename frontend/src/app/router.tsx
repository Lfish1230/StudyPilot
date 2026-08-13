import {
  Navigate,
  Outlet,
  createBrowserRouter,
  useLocation,
} from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { CoursesPage } from "../features/courses/CoursesPage";
import {
  CourseWorkspace,
  WorkspacePlaceholder,
} from "../features/courses/CourseWorkspace";
import { DocumentsPage } from "../features/documents/DocumentsPage";

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
          { path: "chat", element: <WorkspacePlaceholder title="课程问答" /> },
          { path: "documents", element: <DocumentsPage /> },
          { path: "quizzes", element: <WorkspacePlaceholder title="课程测验" /> },
          { path: "mistakes", element: <WorkspacePlaceholder title="错题本" /> },
          { path: "analytics", element: <WorkspacePlaceholder title="学习分析" /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/courses" replace /> },
]);
