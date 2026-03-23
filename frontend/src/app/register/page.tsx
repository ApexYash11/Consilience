"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button, Card, Input } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

export default function RegisterPage() {
  const router = useRouter();
  const { register, error, isAuthenticated } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      await register(email, password, fullName || undefined);
    } catch (err) {
      // Error is handled and displayed by AuthContext
      console.error(err);
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
          Create your account
        </h1>
        <p className="mb-4 text-[var(--text-secondary)]">
          Start standard research immediately with your free tier.
        </p>

        <form className="space-y-3" onSubmit={handleSubmit}>
          <Input
            label="Full Name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
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
            helperText="Minimum 8 characters"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            required
          />
          {error ? <p className="text-xs text-[var(--text-danger)]">{error}</p> : null}
          <Button type="submit" className="w-full" loading={isSubmitting}>
            Create Account
          </Button>
        </form>

        <p className="mt-4 text-xs text-[var(--text-secondary)]">
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--text-brand)]">
            Sign in
          </Link>
        </p>
      </Card>
    </main>
  );
}
