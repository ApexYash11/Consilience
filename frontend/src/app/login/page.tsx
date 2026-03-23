"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button, Input } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { GoogleIcon, GitHubIcon } from "@/components/ui/icons";
import { Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [nextPath, setNextPath] = useState("/");
  const { login, error, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const fromQuery = new URLSearchParams(window.location.search).get("next");
    
    function isValidRedirectPath(path: string): boolean {
      try {
        const url = new URL(path, window.location.origin);
        return url.origin === window.location.origin;
      } catch {
        return false;
      }
    }

    if (fromQuery && isValidRedirectPath(fromQuery)) {
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
    } catch {
      // Login error handled by useAuth context
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <div className="flex flex-col mb-8">
        <h1
          className="mb-2 text-2xl"
          style={{ fontFamily: "var(--font-display)", fontWeight: 500, letterSpacing: "-0.01em" }}
        >
          Welcome back
        </h1>
        <p className="text-sm text-[var(--text-secondary)]">
          Sign in to continue your research workflows.
        </p>
      </div>

      <div className="flex flex-col gap-3 mb-6">
        <Button variant="secondary" className="w-full flex items-center justify-center gap-2.5 h-10 border border-[var(--border-default)]">
          <GoogleIcon className="w-5 h-5 flex-shrink-0" />
          <span className="whitespace-nowrap">Sign in with Google</span>
        </Button>
        <Button variant="secondary" className="w-full flex items-center justify-center gap-2.5 h-10 border border-[var(--border-default)]">
          <GitHubIcon className="w-5 h-5 flex-shrink-0 text-[var(--text-primary)]" />
          <span className="whitespace-nowrap">Sign in with GitHub</span>
        </Button>
      </div>

      <div className="relative flex items-center py-4 mb-2">
        <div className="flex-grow border-t border-[var(--border-default)]"></div>
        <span className="flex-shrink-0 mx-4 text-xs text-[var(--text-tertiary)] uppercase tracking-wider">
          Or continue with email
        </span>
        <div className="flex-grow border-t border-[var(--border-default)]"></div>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit}>
        <Input
          label="Email address"
          type="email"
          placeholder="name@company.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        
        <div>
          <Input
            label="Password"
            type={showPassword ? "text" : "password"}
            value={password}
            placeholder="••••••••"
            onChange={(event) => setPassword(event.target.value)}
            required
            rightElement={
              <button 
                type="button" 
                onClick={() => setShowPassword(!showPassword)}
                className="focus:outline-none hover:text-[var(--text-primary)] transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            }
          />
        </div>
        
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 cursor-pointer">
            <input 
              type="checkbox" 
              className="w-4 h-4 rounded border-[var(--border-default)] text-[var(--accent-primary)] focus:ring-[var(--accent-primary)] bg-[var(--bg-surface)]"
            />
            <span className="text-sm border-transparent text-[var(--text-secondary)]">Remember me</span>
          </label>
          <Link href="/login" className="text-sm font-medium text-[var(--accent-primary)] hover:underline">
            Forgot password?
          </Link>
        </div>

        {error ? <p className="text-sm text-[var(--text-danger)] mt-2">{error}</p> : null}
        
        <Button type="submit" className="w-full h-11 text-[15px] mt-2" loading={isSubmitting}>
          Sign in
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-[var(--text-secondary)]">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="font-medium text-[var(--accent-primary)] hover:underline">
          Sign up
        </Link>
      </p>
    </AuthLayout>
  );
}
