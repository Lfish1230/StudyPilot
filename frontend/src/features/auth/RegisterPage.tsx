import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { useAuth } from "./AuthProvider";

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/courses" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await register({ email, password });
      navigate("/login", {
        replace: true,
        state: { notice: "注册成功，请登录。" },
      });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "注册失败，请稍后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-card" aria-labelledby="register-title">
        <Link className="brand" to="/">StudyPilot</Link>
        <p className="eyebrow">START LEARNING</p>
        <h1 id="register-title">创建学习账号</h1>
        <p className="muted">上传课程 PDF，用可靠引用辅助学习。</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="register-email">邮箱</label>
          <input
            id="register-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <label htmlFor="register-password">密码</label>
          <input
            id="register-password"
            type="password"
            autoComplete="new-password"
            minLength={10}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p className="field-hint">至少 10 个字符。</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "正在创建…" : "注册"}
          </button>
        </form>
        <p className="auth-switch">已有账号？ <Link to="/login">返回登录</Link></p>
      </section>
    </main>
  );
}
