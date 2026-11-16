import Link from "next/link";
import { ArrowRight, Activity } from "lucide-react";

import { PageContainer } from "@/components/layout/page-container";

export function ObservabilityHighlight() {
  return (
    <section className="bg-[var(--surface-soft)] py-16">
      <PageContainer>
        <div className="grid gap-7 rounded-[28px] border border-[var(--accent-border)] bg-white p-7 shadow-sm md:grid-cols-[1fr_auto] md:items-center md:p-10">
          <div>
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--accent-secondary)]"><Activity aria-hidden="true" className="h-5 w-5" /> Engenharia de IA</p>
            <h2 className="heading-2 mt-4">Observabilidade e Qualidade</h2>
            <p className="mt-4 max-w-2xl leading-7 text-[var(--muted-foreground)]">Tracing com Langfuse, datasets sintéticos, LLM-as-a-Judge e testes de regressão ajudam a entender cada resposta e acompanhar a qualidade do RAG.</p>
          </div>
          <Link href="/observabilidade" className="inline-flex w-fit items-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[var(--accent-foreground)] transition hover:brightness-95">
            Ver observabilidade <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
      </PageContainer>
    </section>
  );
}
