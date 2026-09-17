import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Constellation } from "@/components/Mark";
import { Wordmark } from "@/components/Wordmark";
import { Button, Field, Input } from "@/components/ui";
import { homePath, useAuth } from "@/lib/auth-context";

import styles from "./LoginPage.module.css";

export function LoginPage() {
  const { isAuthenticated, me, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? homePath(me);
    return <Navigate to={from} replace />;
  }

  const submit = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      // Three surfaces, one form: where they land is what /api/me says they are.
      void navigate(homePath(await login(email, password)), { replace: true });
    } catch {
      setError("Could not sign in. Check the email and password.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submit();
  };

  return (
    <div className={styles.page}>
      <section className={styles.brand}>
        <Constellation size={420} className={styles.sky} />
        <div className={styles.brandInner}>
          <Wordmark size="lg" className={styles.wordmark} />
          <p className={styles.tagline}>
            Of the stars — a quiet study for your students and their work.
          </p>
        </div>
      </section>

      <div className={styles.formSide}>
        <form className={styles.form} onSubmit={handleSubmit}>
          <h1 className={styles.title}>Sign in</h1>

          <Field label="Email">
            <Input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
              }}
            />
          </Field>

          <Field label="Password" error={error}>
            <Input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
              }}
            />
          </Field>

          <Button type="submit" variant="primary" loading={isSubmitting} className={styles.submit}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
