import { Link } from "react-router-dom";

import type { Course } from "../../api/contracts";

interface CourseCardProps {
  course: Course;
  deleting: boolean;
  onDelete(course: Course): void;
}

export function CourseCard({ course, deleting, onDelete }: CourseCardProps) {
  return (
    <article className="course-card">
      <div>
        <span className="course-icon" aria-hidden="true">📘</span>
        <p className="course-date">
          创建于 {new Intl.DateTimeFormat("zh-CN").format(new Date(course.created_at))}
        </p>
        <h2>{course.name}</h2>
      </div>
      <div className="course-actions">
        <Link className="primary-link" to={`/courses/${course.id}/chat`}>
          进入课程
        </Link>
        <button
          className="danger-button"
          disabled={deleting}
          onClick={() => onDelete(course)}
          type="button"
        >
          {deleting ? "删除中…" : "删除"}
        </button>
      </div>
    </article>
  );
}
