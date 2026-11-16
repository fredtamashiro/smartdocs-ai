"use client";

import { useState } from "react";
import Link from "next/link";

import { AdminLogin } from "@/components/admin-login";
import { DocumentWorkspace } from "@/components/documents/document-workspace";
import { AppFooter } from "@/components/layout/app-footer";
import { AppHeader } from "@/components/layout/app-header";
import { PageContainer } from "@/components/layout/page-container";
import { useAdminSession } from "@/hooks/use-admin-session";

export default function DocumentosPage() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const {
    adminUser,
    isCheckingSession,
    isLoggingOut,
    handleLoggedIn,
    handleLogout,
  } = useAdminSession();

  return (
    <>
      <AppHeader
        adminUser={adminUser}
        isCheckingSession={isCheckingSession}
        isLoggingOut={isLoggingOut}
        onLoginClick={() => setIsLoginModalOpen(true)}
        onLogout={handleLogout}
      />

      <AdminLogin
        isOpen={isLoginModalOpen}
        onOpenChange={setIsLoginModalOpen}
        onLoggedIn={handleLoggedIn}
      />

      <main className="min-h-screen bg-[#fafafa] pb-16 pt-32 text-[#1A1A1A] md:pt-28">
        <PageContainer className="pt-6 text-right">
          <Link href="/observabilidade" className="text-sm font-medium text-[var(--accent-secondary)] underline-offset-4 hover:underline">
            Como avaliamos as respostas
          </Link>
        </PageContainer>
        <section className="bg-[#fafafa] py-10">
          <DocumentWorkspace adminUser={adminUser} />
        </section>
      </main>

      <AppFooter />
    </>
  );
}
