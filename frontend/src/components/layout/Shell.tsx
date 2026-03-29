"use client";

import { useState, useEffect, ReactNode } from "react";
import { Topbar } from "./Topbar";
import { Sidebar } from "./Sidebar";
import { MobileBottomNav } from "./MobileBottomNav";

type ShellProps = {
  children: ReactNode;
};

export function Shell({ children }: ShellProps) {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Initialize dark mode from documentElement's data-theme attribute
  useEffect(() => {
    const htmlElement = document.documentElement;
    const currentTheme = htmlElement.getAttribute("data-theme") || "light";
    setIsDarkMode(currentTheme === "dark");
  }, []);

  const handleThemeToggle = () => {
    const htmlElement = document.documentElement;
    const newTheme = isDarkMode ? "light" : "dark";
    htmlElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
    setIsDarkMode(!isDarkMode);
  };

  const closeMobileSidebar = () => {
    setMobileSidebarOpen(false);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-base)] text-[var(--text-primary)]">
      {/* Topbar */}
      <Topbar
        mobileSidebarOpen={mobileSidebarOpen}
        onMobileSidebarToggle={() => setMobileSidebarOpen(!mobileSidebarOpen)}
        isDarkMode={isDarkMode}
        onThemeToggle={handleThemeToggle}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Desktop Sidebar */}
        <Sidebar open={true} onClose={closeMobileSidebar} />

        {/* Mobile Sidebar Overlay */}
        {mobileSidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 md:hidden"
            onClick={closeMobileSidebar}
            aria-hidden
          />
        )}
        {mobileSidebarOpen && (
          <div className="fixed inset-y-0 left-0 z-40 w-[200px] md:hidden">
            <Sidebar open={mobileSidebarOpen} onClose={closeMobileSidebar} />
          </div>
        )}

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0">
          <div className="p-4 md:p-6">{children}</div>
        </main>
      </div>

      {/* Mobile Bottom Navigation */}
      <MobileBottomNav />
    </div>
  );
}

