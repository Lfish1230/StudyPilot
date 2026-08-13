import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "../../api/client";
import type { Course } from "../../api/contracts";
import { useAuth } from "../auth/AuthProvider";
import { CourseCard } from "./CourseCard";

export function CoursesPage() {
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [formError, setFormError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const coursesQuery = useQuery({
    queryKey: ["courses"],
    queryFn: () => api.request<Course[]>("/courses"),
  });
  const createMutation = useMutation({
    mutationFn: (courseName: string) =>
      api.request<Course>("/courses", {
        method: "POST",
        body: { name: courseName },
      }),
    onSuccess: async () => {
      setName("");
      await queryClient.invalidateQueries({ queryKey: ["courses"] });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (courseId: string) =>
      api.request<void>(`/courses/${courseId}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["courses"] });
    },
    onError: (caught) => {
      setDeleteError(
        caught instanceof ApiError ? caught.message : "删除课程失败，请重试。",
      );
    },
  });

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError("课程名称不能为空。");
      return;
    }
    setFormError("");
    try {
      await createMutation.mutateAsync(trimmedName);
    } catch (caught) {
      setFormError(
        caught instanceof ApiError ? caught.message : "创建课程失败，请重试。",
      );
    }
  }

  function handleDelete(course: Course) {
    if (window.confirm(`确定删除“${course.name}”吗？相关资料也会被删除。`)) {
      setDeleteError("");
      deleteMutation.mutate(course.id);
    }
  }

  const courses = [...(coursesQuery.data ?? [])].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div><span className="brand-mark">S</span><strong>StudyPilot</strong></div>
        <div className="account-actions">
          <span>{user?.email}</span>
          <button className="text-button" onClick={logout} type="button">退出登录</button>
        </div>
      </header>
      <section className="courses-section" aria-labelledby="courses-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">MY COURSES</p>
            <h1 id="courses-title">我的课程</h1>
            <p className="muted">为每门课程建立独立的资料库、问答和测验。</p>
          </div>
          <form className="course-form" onSubmit={handleCreate}>
            <label htmlFor="course-name">新课程名称</label>
            <div>
              <input
                id="course-name"
                maxLength={80}
                placeholder="例如：计算机网络"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <button className="primary-button" disabled={createMutation.isPending} type="submit">
                {createMutation.isPending ? "创建中…" : "创建课程"}
              </button>
            </div>
            {formError && <p className="form-error" role="alert">{formError}</p>}
          </form>
        </div>

        {coursesQuery.isPending && <p className="state-card">正在加载课程…</p>}
        {coursesQuery.isError && (
          <div className="state-card" role="alert">
            <p>课程加载失败，请检查网络后重试。</p>
            <button onClick={() => coursesQuery.refetch()} type="button">重新加载</button>
          </div>
        )}
        {deleteError && <p className="form-error" role="alert">{deleteError}</p>}
        {!coursesQuery.isPending && !coursesQuery.isError && courses.length === 0 && (
          <div className="state-card empty-state">
            <span aria-hidden="true">📚</span>
            <h2>还没有课程</h2>
            <p>先创建一门课程，再上传你的第一份 PDF。</p>
          </div>
        )}
        {courses.length > 0 && (
          <div className="course-grid">
            {courses.map((course) => (
              <CourseCard
                key={course.id}
                course={course}
                deleting={deleteMutation.isPending && deleteMutation.variables === course.id}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
