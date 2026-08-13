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

function CoursePlaceholder() {
  return (
    <main className="loading-screen">
      <h1>课程工作区</h1>
      <p>文档与问答界面将在下一阶段接入。</p>
    </main>
  );
}

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/courses" replace /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/courses", element: <CoursesPage /> },
      { path: "/courses/:courseId/chat", element: <CoursePlaceholder /> },
    ],
  },
  { path: "*", element: <Navigate to="/courses" replace /> },
]);
