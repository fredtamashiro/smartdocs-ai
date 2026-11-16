"use client";

import { useState } from "react";

import { AdminLogin } from "@/components/admin-login";
import { AppFooter } from "@/components/layout/app-footer";
import { AppHeader } from "@/components/layout/app-header";
import { ArchitectureFlow } from "@/components/home/architecture-flow";
import { ArchitectureSummary } from "@/components/home/architecture-summary";
import { CapabilityCards } from "@/components/home/capability-cards";
import { DeploySection } from "@/components/home/deploy-section";
import { HeroSection } from "@/components/home/hero-section";
import { MvpHighlights } from "@/components/home/mvp-highlights";
import { ObservabilityHighlight } from "@/components/home/observability-highlight";
import { PageContainer } from "@/components/layout/page-container";
import { Card, CardContent } from "@/components/ui/card";
import { useAdminSession } from "@/hooks/use-admin-session";

export default function Home() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const {
    adminUser,
    isCheckingSession,
    authErrorMessage,
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

      <main className="min-h-screen bg-[var(--background)] pt-32 text-[var(--foreground)] md:pt-28">
        <section id="home" className="scroll-mt-28 bg-[var(--background)] py-10">
          <PageContainer className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
            <HeroSection />
            <ArchitectureSummary />
          </PageContainer>
        </section>

        <div className="pb-8">
          <PageContainer className="grid gap-8">
            {authErrorMessage && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="p-4 text-sm text-red-700">
                  {authErrorMessage}
                </CardContent>
              </Card>
            )}
          </PageContainer>
        </div>

        <CapabilityCards />
        <section id="arquitetura">
          <ArchitectureFlow />
        </section>
        <MvpHighlights />
        <ObservabilityHighlight />
        <DeploySection />
      </main>

      <AppFooter />
    </>
  );
}
