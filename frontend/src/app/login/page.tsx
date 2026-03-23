"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button, Card, Input } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const [nextPath, setNextPath] = useState("/");
  const { login, error, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const fromQuery = new URLSearchParams(window.location.search).get("next");
    if (fromQuery) {
      setNextPath(fromQuery);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace(nextPath);
    }
  }, [isAuthenticated, nextPath, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      await login(email, password);
      router.replace(nextPath);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--bg-base)] p-4">
      <Card className="w-full max-w-[480px]">
        <h1
          className="mb-1 text-[28px]"
          style={{ fontFamily: "var(--font-display)", fontWeight: 400, lineHeight: 1.2 }}
        >
          Welcome back
        </h1>
        <p className="mb-4 text-[var(--text-secondary)]">
          Sign in to continue your research workflows.
        </p>

        <form className="space-y-3" onSubmit={handleSubmit}>
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          {error ? <p className="text-xs text-[var(--text-danger)]">{error}</p> : null}
          <Button type="submit" className="w-full" loading={isSubmitting}>
            Sign In
          </Button>
        </form>

        <p className="mt-4 text-xs text-[var(--text-secondary)]">
          New here?{" "}
          <Link href="/register" className="text-[var(--text-brand)]">
            Create an account
          </Link>
        </p>
      </Card>
    </main>
  );
}
