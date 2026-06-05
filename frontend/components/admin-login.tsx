"use client";

import { FormEvent, useState } from "react";
import { LockKeyhole, LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { AuthUser, loginAdmin } from "@/services/api";

type AdminLoginProps = {
  onLoggedIn: (user: AuthUser) => void;
};

export function AdminLogin({ onLoggedIn }: AdminLoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setIsSubmitting(true);
      setErrorMessage("");

      const result = await loginAdmin({
        email,
        password,
      });

      setPassword("");
      onLoggedIn(result.user);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Nao foi possivel fazer login.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="border-slate-200 bg-white/90">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LockKeyhole className="h-5 w-5 text-blue-600" />
          Acesso administrativo
        </CardTitle>
        <CardDescription>
          Upload, exclusao de documentos e logs ficam disponiveis apenas para admin autenticado.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-[1.3fr_1fr_auto] md:items-end">
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Email
            </label>
            <Input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="admin@empresa.com"
              autoComplete="username"
              disabled={isSubmitting}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Senha
            </label>
            <Input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Sua senha"
              autoComplete="current-password"
              disabled={isSubmitting}
            />
          </div>

          <Button type="submit" disabled={isSubmitting} className="md:self-end">
            <LogIn className="h-4 w-4" />
            {isSubmitting ? "Entrando..." : "Entrar"}
          </Button>
        </form>

        {errorMessage && (
          <p className="mt-3 text-sm text-red-700">{errorMessage}</p>
        )}
      </CardContent>
    </Card>
  );
}
