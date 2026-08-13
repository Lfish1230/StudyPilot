import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { useAuth } from "./AuthProvider";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
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
      await login({ email, password });
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? "/courses", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "登录失败，请稍后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-card" aria-labelledby="login-title">
        <Link className="brand" to="/">StudyPilot</Link>
        <p className="eyebrow">WELCOME BACK</p>
        <h1 id="login-title">登录继续学习</h1>
        <p className="muted">你的课程资料、问答和测验都在这里。</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="login-email">邮箱</label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <label htmlFor="login-password">密码</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "正在登录…" : "登录"}
          </button>
        </form>
        <p className="auth-switch">还没有账号？ <Link to="/register">立即注册</Link></p>
      </section>
    </main>
  );
}
