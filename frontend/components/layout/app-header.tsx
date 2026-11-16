"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { ChevronDown, CircleUserRound, LogOut } from "lucide-react";

import { AppNavigation } from "@/components/layout/app-navigation";
import { Button } from "@/components/ui/button";
import { AuthUser } from "@/services/api";

type AppHeaderProps = {
  adminUser: AuthUser | null;
  isCheckingSession: boolean;
  isLoggingOut: boolean;
  onLoginClick: () => void;
  onLogout: () => void;
};

export function AppHeader({
  adminUser,
  isCheckingSession,
  isLoggingOut,
  onLoginClick,
  onLogout,
}: AppHeaderProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    }

    if (!isMenuOpen) {
      return;
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [isMenuOpen]);

  return (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-[var(--border)] bg-[var(--surface)]">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-6 px-6 py-4">
        <Link href="/" className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center overflow-hidden">
            <Image
              src="/logo-header.png"
              alt="FredTamashiro"
              width={44}
              height={44}
              className="h-full w-full object-contain"
              unoptimized
            />
          </span>
          <span className="text-2xl font-semibold tracking-tight text-[var(--foreground)]">
            FredTamashiro
          </span>
        </Link>

        <AppNavigation />

        {adminUser ? (
          <div className="relative" ref={menuRef}>
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsMenuOpen((current) => !current)}
              className="h-12 rounded-md border-[#d9dde3] bg-white px-4"
            >
              <CircleUserRound className="h-4 w-4" />
              <span className="hidden max-w-36 truncate text-sm md:block">
                {adminUser.name || adminUser.email}
              </span>
              <ChevronDown className="h-4 w-4" />
            </Button>

            {isMenuOpen && (
              <div className="absolute right-0 mt-3 w-52 rounded-xl border border-[#d9dde3] bg-white p-2">
                <div className="border-b border-[#eceff2] px-3 py-2">
                  <p className="text-sm font-medium text-[#1A1A1A]">
                    {adminUser.name || "Admin"}
                  </p>
                  <p className="truncate text-xs text-[#666666]">
                    {adminUser.email}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setIsMenuOpen(false);
                    onLogout();
                  }}
                  disabled={isLoggingOut}
                  className="mt-2 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-alt)] disabled:opacity-60"
                >
                  <LogOut className="h-4 w-4" />
                  {isLoggingOut ? "Saindo..." : "Sair"}
                </button>
              </div>
            )}
          </div>
        ) : (
          <Button
            type="button"
            onClick={onLoginClick}
            disabled={isCheckingSession}
            className="h-12 rounded-md bg-[var(--accent)] px-6 text-[var(--accent-foreground)] hover:brightness-95"
          >
            {isCheckingSession ? "Verificando..." : "Login"}
          </Button>
        )}
      </div>
      <div className="mx-auto max-w-7xl md:hidden">
        <AppNavigation mobile />
      </div>
    </header>
  );
}
