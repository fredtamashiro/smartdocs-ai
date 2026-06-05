"use client";

import { useEffect, useState } from "react";
import { LogOut, ShieldCheck } from "lucide-react";

import { AdminLogin } from "@/components/admin-login";
import { DocumentsPanel } from "@/components/documents-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AuthUser, getCurrentAdmin, logoutAdmin } from "@/services/api";

export default function Home() {
  const [adminUser, setAdminUser] = useState<AuthUser | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [authErrorMessage, setAuthErrorMessage] = useState("");
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    async function loadCurrentAdmin() {
      try {
        setIsCheckingSession(true);
        const user = await getCurrentAdmin();
        setAdminUser(user);
        setAuthErrorMessage("");
      } catch {
        setAdminUser(null);
      } finally {
        setIsCheckingSession(false);
      }
    }

    void loadCurrentAdmin();
  }, []);

  async function handleLogout() {
    try {
      setIsLoggingOut(true);
      await logoutAdmin();
      setAdminUser(null);
      setAuthErrorMessage("");
    } catch (error) {
      setAuthErrorMessage(
        error instanceof Error
          ? error.message
          : "Nao foi possivel encerrar a sessao.",
      );
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10 text-slate-950">
      <div className="mx-auto grid max-w-6xl gap-6">
        {isCheckingSession ? (
          <Card>
            <CardContent className="p-6 text-sm text-slate-500">
              Verificando sessao administrativa...
            </CardContent>
          </Card>
        ) : adminUser ? (
          <Card className="border-emerald-200 bg-emerald-50">
            <CardHeader className="mb-0">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-emerald-900">
                    <ShieldCheck className="h-5 w-5" />
                    Admin autenticado
                  </CardTitle>
                  <CardDescription className="text-emerald-800">
                    {adminUser.name || adminUser.email}
                  </CardDescription>
                </div>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                  className="border-emerald-300 bg-white text-emerald-900 hover:bg-emerald-100"
                >
                  <LogOut className="h-4 w-4" />
                  {isLoggingOut ? "Saindo..." : "Sair"}
                </Button>
              </div>
            </CardHeader>
          </Card>
        ) : (
          <AdminLogin
            onLoggedIn={(user) => {
              setAdminUser(user);
              setAuthErrorMessage("");
            }}
          />
        )}

        {authErrorMessage && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="p-4 text-sm text-red-700">
              {authErrorMessage}
            </CardContent>
          </Card>
        )}

        <DocumentsPanel adminUser={adminUser} />
      </div>
    </main>
  );
}
