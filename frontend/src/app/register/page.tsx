"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button, Input } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { GoogleIcon, GitHubIcon } from "@/components/ui/icons";
import { Eye, EyeOff } from "lucide-react";
import { useOAuth } from "@/hooks/useOAuth";

export default function RegisterPage() {
  const router = useRouter();
  const { register, error, isAuthenticated } = useAuth();
  const { startOAuthFlow } = useOAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
      const fullName = [firstName, lastName].filter(Boolean).join(" ");
      await register(email, password, fullName || undefined);
    } catch {
      // Error is handled and displayed by AuthContext
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
          Create an account
        </h1>
        <p className="text-sm text-[var(--text-secondary)]">
          Start standard research immediately with your free tier.
        </p>
      </div>

      <div className="flex flex-col gap-3 mb-6">
        <Button 
          onClick={() => startOAuthFlow('google')}
          variant="secondary" 
          className="w-full flex items-center justify-center gap-2.5 h-10 border border-[var(--border-default)]"
          aria-label="Sign up with Google"
        >
          <GoogleIcon className="w-5 h-5 flex-shrink-0" />
          <span className="whitespace-nowrap">Sign up with Google</span>
        </Button>
        <Button 
          onClick={() => startOAuthFlow('github')}
          variant="secondary" 
          className="w-full flex items-center justify-center gap-2.5 h-10 border border-[var(--border-default)]"
          aria-label="Sign up with GitHub"
        >
          <GitHubIcon className="w-5 h-5 flex-shrink-0 text-[var(--text-primary)]" />
          <span className="whitespace-nowrap">Sign up with GitHub</span>
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
        <div className="grid grid-cols-2 gap-4">
          <Input
            label="First Name"
            placeholder="Jane"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
          />
          <Input
            label="Last Name"
            placeholder="Doe"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
          />
        </div>

        <Input
          label="Email address"
          type="email"
          placeholder="name@company.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        
        <Input
          label="Password"
          type={showPassword ? "text" : "password"}
          placeholder="••••••••"
          helperText="Must be at least 8 characters"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
          required
          rightElement={
            <button 
              type="button" 
              onClick={() => setShowPassword(!showPassword)}
              className="focus-visible:ring-2 focus-visible:ring-[var(--blue-400)] focus-visible:ring-offset-0 focus-visible:rounded-sm hover:text-[var(--text-primary)] transition-colors"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          }
        />
        
        {error ? <p className="text-sm text-[var(--text-danger)] mt-2">{error}</p> : null}
        
        <Button type="submit" className="w-full h-11 text-[15px] mt-2 leading-none" loading={isSubmitting}>
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-[var(--text-secondary)] leading-relaxed">
        By continuing, you agree to our{" "}
        <Link href="/terms" className="text-[var(--text-primary)] hover:underline">
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link href="/privacy" className="text-[var(--text-primary)] hover:underline">
          Privacy Policy
        </Link>.
      </p>

      <p className="mt-6 text-center text-sm text-[var(--text-secondary)]">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-[var(--accent-primary)] hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
