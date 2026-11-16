/**
 * Public, synthetic examples selected from docs/rag-regression-4b4.md and
 * docs/rag-dedup-evaluation-4b2.md. Keep production traces and local reports
 * out of the frontend bundle. These figures describe one experiment only.
 */

export type PipelineKind = "root" | "span" | "generation" | "result";

export type PipelineStep = {
  title: string;
  detail: string;
  kind: PipelineKind;
  observation: string;
};

export const experiment = {
  name: "Regressão 4B.4",
  dataset: "synthetic_rag_v1 · versão 1.0.0",
  cases: 18,
  verifiedContexts: 18,
  answerCorrectness: "1,0",
  answerCorrectnessEvaluable: 14,
  faithfulness: "1,0",
  faithfulnessEvaluable: 18,
  requiredCitations: "3/3",
  meanLatency: "16,717 s",
  ragTokens: "31.936",
  providerModel: "gpt-5-mini-2025-08-07",
  cost: "Não informado pelo provider",
} as const;

export const pipelineSteps: readonly PipelineStep[] = [
  {
    title: "Pergunta do usuário",
    detail: "Uma execução do fluxo de consulta inicia o trace raiz.",
    kind: "root",
    observation: "smartdocs.rag.query",
  },
  {
    title: "Reescrita da consulta",
    detail: "Quando aplicável, o modelo amplia a busca sem responder à pergunta.",
    kind: "generation",
    observation: "Generation · query rewrite",
  },
  {
    title: "Busca vetorial",
    detail: "O pgvector retorna candidatos ordenados por distância cosseno.",
    kind: "span",
    observation: "Span · retrieve / vector search",
  },
  {
    title: "Seleção de contexto",
    detail: "Deduplicação, limite de candidatos e relevance grader escolhem os trechos.",
    kind: "generation",
    observation: "Span + generation · relevance grader",
  },
  {
    title: "Geração da resposta",
    detail: "O LLM responde usando o contexto selecionado.",
    kind: "generation",
    observation: "Generation · answer",
  },
  {
    title: "Resposta com referências",
    detail: "A resposta é entregue com as páginas de origem disponíveis.",
    kind: "result",
    observation: "Resultado · status e duração total",
  },
];

export const operationalSignals = [
  {
    title: "Tempo de execução",
    detail: "Duração total e tempos de recuperação, grader e geração quando disponíveis.",
    value: experiment.meanLatency,
    label: "Média da execução 4B.4",
  },
  {
    title: "Recuperação",
    detail: "Quantidade de chunks recuperados, preservados e enviados ao contexto.",
    value: "Por etapa",
    label: "Contagens registradas nos spans",
  },
  {
    title: "Distância cosseno",
    detail: "Distância vetorial dos candidatos: valores menores indicam maior proximidade.",
    value: "Menor é melhor",
    label: "Não é score de similaridade",
  },
  {
    title: "Modelo e uso",
    detail: "Modelo reportado pelo provider e tokens de entrada, saída e total quando retornados.",
    value: experiment.ragTokens,
    label: "Tokens totais do RAG na 4B.4",
  },
  {
    title: "Custo",
    detail: "Exibido apenas quando o provider fornece um valor confiável.",
    value: experiment.cost,
    label: "Execução 4B.4",
  },
  {
    title: "Status e falhas",
    detail: "Sucesso ou falha da execução, com categorias técnicas de erro e correlação.",
    value: "18/18",
    label: "Casos concluídos na 4B.4",
  },
] as const;

export const qualityCriteria = [
  {
    title: "Answer Correctness",
    detail: "Compara semanticamente a resposta aos fatos esperados do documento sintético.",
  },
  {
    title: "Faithfulness",
    detail: "Verifica se as afirmações têm suporte no contexto efetivamente enviado ao LLM.",
  },
  {
    title: "Abstention Correctness",
    detail: "Avalia quando responder, reconhecer ausência de informação ou pedir esclarecimento.",
  },
] as const;

export const caseStudy = {
  caseId: "aur-05",
  initialAnswer: "A autonomia de 8 horas era informada, mas faltava como ligar a estação.",
  lostEvidence: "A instrução da página 1 não chegava ao contexto do modelo.",
  cause: "O índice válido 0 era tratado como ausente por uma expressão Python com “or”.",
  correction: "O fallback agora ocorre somente quando chunk_index está ausente ou é None.",
  validation: "A página 1 passou pela deduplicação e chegou ao prompt junto da página 2.",
  beforeScore: "0,5",
  afterScore: "1,0",
} as const;
