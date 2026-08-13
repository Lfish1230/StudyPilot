import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { Course } from "../../api/contracts";
import { useAuth } from "../auth/AuthProvider";

const navigation = [
  ["chat", "问答", "💬"],
  ["documents", "资料", "📄"],
  ["quizzes", "测验", "✏️"],
  ["mistakes", "错题", "🧩"],
  ["analytics", "分析", "📊"],
] as const;

export function CourseWorkspace() {
  const { courseId } = useParams();
  const { user, logout } = useAuth();
  const courseQuery = useQuery({
    queryKey: ["course", courseId],
    queryFn: () => api.request<Course>(`/courses/${courseId}`),
    enabled: Boolean(courseId),
  });

  if (!courseId) return <Navigate to="/courses" replace />;
  if (courseQuery.error instanceof ApiError && courseQuery.error.status === 404) {
    return <Navigate to="/courses" replace />;
  }
  if (courseQuery.isPending) {
    return <main className="loading-screen">正在加载课程…</main>;
  }
  if (courseQuery.isError || !courseQuery.data) {
    return (
      <main className="loading-screen" role="alert">
        <div>
          <h1>课程加载失败</h1>
          <button onClick={() => courseQuery.refetch()} type="button">重新加载</button>
        </div>
      </main>
    );
  }

  return (
    <div className="workspace-shell">
      <header className="topbar workspace-topbar">
        <NavLink className="workspace-brand" end to="/courses">
          <span className="brand-mark">S</span><strong>StudyPilot</strong>
        </NavLink>
        <div className="account-actions">
          <span>{user?.email}</span>
          <button className="text-button" onClick={logout} type="button">退出登录</button>
        </div>
      </header>
      <aside className="workspace-sidebar" aria-label="课程功能">
        <div className="course-identity">
          <span aria-hidden="true">📘</span>
          <div><small>当前课程</small><strong>{courseQuery.data.name}</strong></div>
        </div>
        <nav>
          {navigation.map(([path, label, icon]) => (
            <NavLink key={path} to={path}>
              <span aria-hidden="true">{icon}</span>{label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <section className="workspace-content">
        <Outlet context={{ course: courseQuery.data }} />
      </section>
    </div>
  );
}

export function WorkspacePlaceholder({ title }: { title: string }) {
  return (
    <div className="workspace-page state-card">
      <h1>{title}</h1>
      <p>该功能将在后续阶段接入。</p>
    </div>
  );
}
