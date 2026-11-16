import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CheckCircle2, LockKeyhole, Microscope } from "lucide-react";

import { AppFooter } from "@/components/layout/app-footer";
import { PageContainer } from "@/components/layout/page-container";
import { ObservabilityHeader } from "@/components/observability/observability-header";
import { PipelineDiagram } from "@/components/observability/pipeline-diagram";
import { Card } from "@/components/ui/card";
import { caseStudy, experiment, operationalSignals, qualityCriteria } from "@/lib/observability-data";

export const metadata: Metadata = {
  title: "Observabilidade e Qualidade de IA | SmartDocs AI",
  description: "Como o SmartDocs monitora o RAG com Langfuse e avalia respostas em um dataset sintético versionado.",
};

const experimentStats = [
  { value: String(experiment.cases), label: "casos sintéticos" },
  { value: String(experiment.verifiedContexts), label: "contextos verificados" },
  { value: experiment.answerCorrectness, label: `Answer Correctness médio · ${experiment.answerCorrectnessEvaluable} avaliáveis` },
  { value: experiment.faithfulness, label: `Faithfulness médio · ${experiment.faithfulnessEvaluable} avaliáveis` },
  { value: experiment.requiredCitations, label: "citações exigidas presentes" },
] as const;

export default function ObservabilidadePage() {
  return (
    <>
      <ObservabilityHeader />
      <main className="min-h-screen bg-[var(--background)] pt-32 text-[var(--foreground)] md:pt-28">
        <section className="pb-14 pt-12 sm:pt-16">
          <PageContainer className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-end">
            <div>
              <p className="mb-5 text-sm font-bold uppercase tracking-[0.16em] text-[var(--accent-secondary)]">Engenharia de IA · SmartDocs</p>
              <h1 className="heading-1 max-w-3xl">Observabilidade e <span className="text-[var(--accent-secondary)]">Qualidade de IA</span></h1>
              <p className="mt-7 max-w-2xl text-lg leading-8 text-[var(--muted-foreground)]">
                Como o SmartDocs monitora execuções, avalia respostas e melhora continuamente seu pipeline RAG.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="#fluxo" className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[var(--accent-foreground)] transition hover:brightness-95">
                  Explorar o fluxo <ArrowRight aria-hidden="true" className="h-4 w-4" />
                </a>
                <a href="#experimento" className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-5 py-3 text-sm font-semibold transition hover:border-[var(--accent-secondary)]">
                  Ver experimento
                </a>
              </div>
            </div>
            <div className="rounded-[28px] border border-[var(--border)] bg-white p-7 shadow-sm">
              <p className="text-sm font-semibold text-[var(--accent-secondary)]">Do comportamento à evidência</p>
              <div className="mt-5 grid gap-4">
                <p className="border-l-4 border-[var(--accent)] pl-4 text-sm leading-7"><strong>Observar:</strong> onde o fluxo gastou tempo e quais etapas ocorreram.</p>
                <p className="border-l-4 border-[var(--accent)] pl-4 text-sm leading-7"><strong>Avaliar:</strong> se a resposta está correta e apoiada no contexto.</p>
                <p className="border-l-4 border-[var(--accent)] pl-4 text-sm leading-7"><strong>Revisar:</strong> investigar divergências e comparar regressões.</p>
              </div>
            </div>
          </PageContainer>
        </section>

        <section id="fluxo" className="scroll-mt-32 bg-[var(--surface-soft)] py-16">
          <PageContainer>
            <div className="mb-8 max-w-3xl">
              <p className="text-sm font-bold uppercase tracking-[0.14em] text-[var(--accent-secondary)]">Arquitetura observável</p>
              <h2 className="heading-2 mt-3">Uma execução, várias etapas rastreáveis</h2>
              <p className="mt-4 leading-7 text-[var(--muted-foreground)]">O Langfuse acompanha o fluxo de ponta a ponta. Etapas condicionais só aparecem quando realmente são executadas.</p>
            </div>
            <PipelineDiagram />
          </PageContainer>
        </section>

        <section id="metricas" className="scroll-mt-32 py-16">
          <PageContainer>
            <div className="max-w-3xl">
              <p className="text-sm font-bold uppercase tracking-[0.14em] text-[var(--accent-secondary)]">Observabilidade operacional</p>
              <h2 className="heading-2 mt-3">O que medimos em cada execução</h2>
              <p className="mt-4 leading-7 text-[var(--muted-foreground)]">Os spans e generations registram sinais técnicos sem publicar perguntas, respostas ou trechos de documentos.</p>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {operationalSignals.map((signal) => (
                <Card key={signal.title} className="rounded-[20px] border-[var(--border)] bg-white p-6">
                  <p className="text-sm font-semibold text-[var(--accent-secondary)]">{signal.title}</p>
                  <p className="mt-4 text-xl font-bold text-[var(--foreground)]">{signal.value}</p>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">{signal.label}</p>
                  <p className="mt-4 text-sm leading-6 text-[var(--muted-foreground)]">{signal.detail}</p>
                </Card>
              ))}
            </div>
            <p className="mt-5 text-sm text-[var(--muted-foreground)]">Modelo reportado na regressão 4B.4: <span className="font-mono text-[var(--foreground)]">{experiment.providerModel}</span>. Os {experiment.ragTokens} tokens representam o total do RAG; entrada e saída são registradas por chamada quando o provider informa.</p>
          </PageContainer>
        </section>

        <section id="experimento" className="scroll-mt-32 bg-[var(--surface-soft)] py-16">
          <PageContainer>
            <div className="max-w-3xl">
              <p className="text-sm font-bold uppercase tracking-[0.14em] text-[var(--accent-secondary)]">Avaliação de qualidade</p>
              <h2 className="heading-2 mt-3">Qualidade medida com casos controlados</h2>
              <p className="mt-4 leading-7 text-[var(--muted-foreground)]">Um dataset de documentos sintéticos permite repetir perguntas, comparar respostas e investigar falhas sem usar dados de usuários.</p>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {experimentStats.map((stat) => (
                <Card key={stat.label} className="rounded-[20px] border-[var(--border)] bg-white p-5">
                  <p className="text-3xl font-bold text-[var(--accent-secondary)]">{stat.value}</p>
                  <p className="mt-2 text-sm leading-5 text-[var(--muted-foreground)]">{stat.label}</p>
                </Card>
              ))}
            </div>
            <p className="mt-4 text-sm text-[var(--muted-foreground)]">Resultado de uma execução específica: {experiment.name}, dataset {experiment.dataset}. Esses scores não representam a acurácia geral do SmartDocs.</p>
            <div className="mt-9 grid gap-4 md:grid-cols-3">
              {qualityCriteria.map((criterion) => (
                <Card key={criterion.title} className="rounded-[20px] border-[var(--border)] bg-white p-6">
                  <h3 className="heading-4">{criterion.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">{criterion.detail}</p>
                </Card>
              ))}
            </div>
            <div className="mt-6 grid gap-5 rounded-[24px] border border-[var(--accent-border)] bg-[var(--accent-soft)] p-6 md:grid-cols-3">
              <p className="text-sm leading-7"><strong>LLM-as-a-Judge</strong> aplica rubricas versionadas e pode marcar um caso como não avaliável.</p>
              <p className="text-sm leading-7"><strong>Revisão humana</strong> examina ambiguidades e divergências sem substituir silenciosamente a decisão original do juiz.</p>
              <p className="text-sm leading-7"><strong>Regressão</strong> compara resultados caso a caso, preservando baselines e a metodologia usada.</p>
            </div>
          </PageContainer>
        </section>

        <section id="caso" className="scroll-mt-32 py-16">
          <PageContainer>
            <div className="mb-8 max-w-3xl">
              <p className="text-sm font-bold uppercase tracking-[0.14em] text-[var(--accent-secondary)]">Estudo de caso · {caseStudy.caseId}</p>
              <h2 className="heading-2 mt-3">Como identificamos uma falha no RAG</h2>
            </div>
            <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
              <Card className="rounded-[24px] border-[var(--border)] bg-white p-7">
                <div className="flex items-center gap-3"><Microscope aria-hidden="true" className="h-6 w-6 text-[var(--accent-secondary)]" /><h3 className="heading-3">A investigação</h3></div>
                <ol className="mt-6 grid gap-5 text-sm leading-7">
                  <li><strong>Situação inicial.</strong> {caseStudy.initialAnswer}</li>
                  <li><strong>Evidência.</strong> {caseStudy.lostEvidence}</li>
                  <li><strong>Causa.</strong> {caseStudy.cause}</li>
                </ol>
              </Card>
              <Card className="rounded-[24px] border-[var(--accent-border)] bg-[var(--accent-soft)] p-7">
                <div className="flex items-center gap-3"><CheckCircle2 aria-hidden="true" className="h-6 w-6 text-[var(--accent-secondary)]" /><h3 className="heading-3">A validação</h3></div>
                <p className="mt-6 text-sm leading-7"><strong>Correção.</strong> {caseStudy.correction}</p>
                <p className="mt-4 text-sm leading-7"><strong>Contexto.</strong> {caseStudy.validation}</p>
                <div className="mt-6 flex items-center gap-3 rounded-xl bg-white px-5 py-4">
                  <span className="text-sm text-[var(--muted-foreground)]">Answer Correctness</span>
                  <span className="ml-auto font-semibold">{caseStudy.beforeScore} → {caseStudy.afterScore}</span>
                </div>
                <p className="mt-4 text-xs leading-6 text-[var(--muted-foreground)]">Resultado das execuções dirigidas de validação do caso aur-05. Isoladamente, não comprova melhoria global do RAG.</p>
              </Card>
            </div>
          </PageContainer>
        </section>

        <section className="bg-[var(--surface-soft)] py-16">
          <PageContainer className="grid gap-7 md:grid-cols-[auto_1fr] md:items-start">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent-secondary)]"><LockKeyhole aria-hidden="true" className="h-6 w-6" /></span>
            <div className="max-w-3xl">
              <h2 className="heading-3">Privacidade por projeto</h2>
              <p className="mt-4 leading-7 text-[var(--muted-foreground)]">Esta página usa somente números selecionados de experimentos sintéticos. O navegador não se conecta ao Langfuse Cloud. Credenciais, prompts internos, documentos reais, respostas de usuários e identificadores privados de traces não são publicados aqui.</p>
              <Link href="/documentos" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[var(--accent-secondary)] hover:underline">Conhecer o Workspace <ArrowRight aria-hidden="true" className="h-4 w-4" /></Link>
            </div>
          </PageContainer>
        </section>
      </main>
      <AppFooter />
    </>
  );
}
