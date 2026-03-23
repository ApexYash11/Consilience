"use client";

import { BrainCircuit } from "lucide-react";
import Link from "next/link";
import { ReactNode } from "react";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[var(--bg-base)]">
      {/* Left Pane - Branding & Quote */}
      <div className="hidden lg:flex w-1/2 flex-col justify-between p-12 bg-gradient-to-br from-[var(--bg-surface-hover)] to-[var(--bg-base)] border-r border-[var(--border-default)]">
        <div>
          <Link href="/" className="flex items-center gap-2 w-max">
            <div className="p-2 bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-[var(--r-md)] shadow-sm">
              <BrainCircuit className="w-[18px] h-[18px] text-[var(--accent-primary)]" />
            </div>
            <span className="font-semibold tracking-[0.02em] text-base text-[var(--text-primary)]">Consilience</span>
          </Link>
        </div>
        
        <div className="max-w-md">
          <blockquote className="space-y-4">
            <p className="text-2xl font-light leading-relaxed text-[var(--text-primary)]">
              &quot;This platform has transformed how our team approaches deep technical research. The speed and depth of analysis are unprecedented.&quot;
            </p>
            <footer className="flex flex-col gap-1">
              <cite className="text-sm font-medium text-[var(--text-primary)] not-italic">
                Sarah Jenkins
              </cite>
              <span className="text-sm text-[var(--text-secondary)]">
                Lead Scientist, Acme Corp
              </span>
            </footer>
          </blockquote>
        </div>
      </div>

      {/* Right Pane - Form Card */}
      <div className="flex w-full lg:w-1/2 flex-col justify-center items-center p-6 md:p-12">
        {/* Mobile Header */}
        <div className="lg:hidden flex items-center justify-center w-full mb-8">
          <Link href="/" className="flex items-center gap-2 w-max">
            <div className="p-2 bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-[var(--r-md)] shadow-sm">
              <BrainCircuit className="w-[18px] h-[18px] text-[var(--accent-primary)]" />
            </div>
            <span className="font-semibold tracking-[0.02em] text-base text-[var(--text-primary)]">Consilience</span>
          </Link>
        </div>

        <div className="w-full max-w-[440px] bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-[var(--r-lg)] p-8 shadow-[var(--shadow-card)]">
          {children}
        </div>
      </div>
    </div>
  );
}