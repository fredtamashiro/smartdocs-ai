"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

export const appNavItems = [
  { label: "Início", href: "/" },
  { label: "Ver Demo", href: "/documentos" },
  { label: "Observabilidade", href: "/observabilidade" },
] as const;

function isActiveItem(href: string, pathname: string): boolean {
  return pathname === href;
}

export function AppNavigation({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();

  return (
    <nav aria-label={mobile ? "Navegação móvel" : "Navegação principal"} className={mobile ? "flex items-center gap-5 overflow-x-auto px-6 pb-3 md:hidden" : "hidden items-center gap-8 md:flex"}>
      {appNavItems.map((item) => {
        const isActive = isActiveItem(item.href, pathname);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "shrink-0 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-secondary)]",
              isActive
                ? "text-[var(--accent-secondary)]"
                : "text-[var(--foreground)] hover:text-[var(--accent-secondary)]",
            )}
            aria-current={isActive ? "page" : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
