import { Activity, ArrowDown, GitBranch, Layers3, Sparkles } from "lucide-react";

import { pipelineSteps, type PipelineKind } from "@/lib/observability-data";

const kindStyles: Record<PipelineKind, string> = {
  root: "border-[#a4df69] bg-[var(--accent-soft)] text-[#355b22]",
  span: "border-[#b9d8d7] bg-[#eff8f7] text-[var(--accent-secondary)]",
  generation: "border-[#d5d0e8] bg-[#f6f4fc] text-[#625482]",
  result: "border-[var(--border)] bg-[var(--surface-soft)] text-[var(--muted-foreground)]",
};

const kindLabels: Record<PipelineKind, string> = {
  root: "Trace raiz",
  span: "Span de recuperação",
  generation: "Generation",
  result: "Resultado e métricas",
};

export function PipelineDiagram() {
  return (
    <div className="rounded-[28px] border border-[var(--accent-border)] bg-white p-5 shadow-sm sm:p-8">
      <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-[var(--accent-soft)] px-5 py-4 text-[#355b22]">
        <Activity aria-hidden="true" className="h-6 w-6 shrink-0" />
        <div>
          <p className="font-semibold">Langfuse observa toda a execução</p>
          <p className="text-sm leading-6">Trace, spans e generations formam uma hierarquia; a coleta é opcional e controlada.</p>
        </div>
      </div>

      <ol className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {pipelineSteps.map((step, index) => (
          <li key={step.title} className="min-w-0">
            <div className="h-full rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold tracking-[0.12em] text-[var(--muted-foreground)]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${kindStyles[step.kind]}`}>
                  {kindLabels[step.kind]}
                </span>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-[var(--foreground)]">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{step.detail}</p>
              <p className="mt-4 break-words font-mono text-xs text-[var(--accent-secondary)]">{step.observation}</p>
            </div>
            {index < pipelineSteps.length - 1 && (
              <ArrowDown aria-hidden="true" className="mx-auto mt-2 h-4 w-4 text-[var(--accent-secondary)] md:hidden" />
            )}
          </li>
        ))}
      </ol>

      <div className="mt-6 flex flex-wrap gap-x-5 gap-y-2 border-t border-[var(--border)] pt-5 text-xs text-[var(--muted-foreground)]">
        <span className="inline-flex items-center gap-2"><GitBranch aria-hidden="true" className="h-4 w-4" /> Trace raiz: execução inteira</span>
        <span className="inline-flex items-center gap-2"><Layers3 aria-hidden="true" className="h-4 w-4" /> Span: etapa de recuperação</span>
        <span className="inline-flex items-center gap-2"><Sparkles aria-hidden="true" className="h-4 w-4" /> Generation: chamada ao LLM</span>
        <span className="inline-flex items-center gap-2"><Activity aria-hidden="true" className="h-4 w-4" /> Métricas: latência, status e uso</span>
      </div>
    </div>
  );
}
