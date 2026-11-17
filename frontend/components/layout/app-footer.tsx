import Link from "next/link";

import { GithubIcon } from "@/components/icons/github-icon";
import { LinkedinIcon } from "@/components/icons/linkedin-icon";
import { PageContainer } from "@/components/layout/page-container";

type FooterLink = {
  label: string;
  href: string;
};

type AppFooterProps = {
  links?: FooterLink[];
};

export function AppFooter({ links = [] }: AppFooterProps) {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="border-t border-[var(--border)] bg-[var(--surface)] py-10">
      <PageContainer className="grid gap-8 md:grid-cols-[1.2fr_0.8fr] md:items-end">
        <div>
          <p className="heading-4 text-[var(--foreground)]">FredTamashiro</p>
          <p className="mt-3 max-w-xl text-sm leading-7 text-[var(--muted-foreground)]">
            SmartDocs AI é uma demonstração técnica de ingestão inteligente,
            busca semântica e consulta de documentos com IA aplicada a um fluxo
            real de produto.
          </p>
          <p className="mt-4 text-xs text-[var(--muted-foreground)]">
            © {currentYear} Fred Tamashiro. Projeto em evolução contínua.
          </p>
        </div>

        <div className="grid gap-6 md:justify-items-end">
          {links.length > 0 && (
            <nav aria-label="Links do rodapé" className="flex flex-wrap gap-4 text-sm">
              {links.map((link) => {
                const isInternalRoute = link.href.startsWith("/");

                if (isInternalRoute) {
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className="text-[var(--accent-secondary)] transition hover:text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-secondary)]"
                    >
                      {link.label}
                    </Link>
                  );
                }

                return (
                  <a
                    key={link.href}
                    href={link.href}
                    className="text-[var(--accent-secondary)] transition hover:text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-secondary)]"
                  >
                    {link.label}
                  </a>
                );
              })}
            </nav>
          )}

          <div className="flex items-center gap-3">
            <a
              href="https://github.com/fredtamashiro"
              target="_blank"
              rel="noreferrer"
              aria-label="GitHub de Fred Tamashiro"
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-soft)] px-4 py-2 text-sm font-medium text-[var(--foreground)] transition hover:border-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-secondary)]"
            >
              <GithubIcon className="h-4 w-4" />
              GitHub
            </a>
            <a
              href="https://www.linkedin.com/in/fredtamashiro/"
              target="_blank"
              rel="noreferrer"
              aria-label="LinkedIn de Fred Tamashiro"
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-soft)] px-4 py-2 text-sm font-medium text-[var(--foreground)] transition hover:border-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-secondary)]"
            >
              <LinkedinIcon className="h-4 w-4" />
              LinkedIn
            </a>
          </div>
        </div>
      </PageContainer>
    </footer>
  );
}
