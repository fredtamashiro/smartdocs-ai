import { caseStudy } from "@/lib/observability-data";

export function CaseCodeComparison() {
  return (
    <figure className="min-w-0 rounded-[24px] border border-[var(--border)] bg-[var(--surface-soft)] p-5 sm:p-7">
      <figcaption className="text-sm leading-7 text-[var(--foreground)]">
        <strong>Por que o chunk desaparecia?</strong> Em Python, o índice <code className="font-mono">0</code> é válido, mas é tratado como falso pela expressão <code className="font-mono">or</code>. O fallback criava uma chave igual à de outro chunk, causando a colisão na deduplicação.
      </figcaption>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <div className="min-w-0 rounded-xl border border-[var(--border)] bg-white p-4">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--muted-foreground)]">Antes · índice 0 perdido</p>
          <pre className="mt-3 max-w-full whitespace-pre-wrap break-words font-mono text-xs leading-6 text-[var(--foreground)]"><code>{caseStudy.beforeCode}</code></pre>
        </div>
        <div className="min-w-0 rounded-xl border border-[var(--accent-border)] bg-white p-4">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--accent-secondary)]">Depois · fallback só para None</p>
          <pre className="mt-3 max-w-full whitespace-pre-wrap break-words font-mono text-xs leading-6 text-[var(--foreground)]"><code>{caseStudy.afterCode}</code></pre>
        </div>
      </div>
      <p className="mt-4 text-xs leading-6 text-[var(--muted-foreground)]">Representação didática da correção. A implementação real também considera os metadados do chunk.</p>
    </figure>
  );
}
