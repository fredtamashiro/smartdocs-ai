# SmartDocs AI

Plataforma inteligente para consulta de documentos PDF usando IA generativa, RAG, LangGraph, PostgreSQL + pgvector, Redis Queue e Next.js.

## Objetivo do projeto

O SmartDocs AI demonstra uma aplicação real de IA aplicada à ingestão, enriquecimento, indexação semântica e consulta de documentos PDF com respostas contextualizadas e rastreáveis por fontes.

O projeto foi estruturado como uma base de produto real, com separação entre API, worker assíncrono, banco vetorial, autenticação administrativa, rate limit, auditoria operacional e fluxo de deploy reproduzível.

## Principais funcionalidades

- Upload de PDFs por admin
- Smart Ingest assíncrono
- Extração de texto
- Chunking
- Enriquecimento semântico com LLM
- Geração de embeddings
- Armazenamento em PostgreSQL + pgvector
- Consulta via chat
- Multi-query retrieval
- Relevance grader
- Respostas com fontes
- Resumo automático do documento
- Perguntas sugeridas
- Temas configuráveis
- Rate limit com Redis
- Login admin via cookie HttpOnly
- Worker RQ para processamento assíncrono
- Usage logs / auditoria

## Arquitetura

- Frontend: Next.js / React / TypeScript
- Backend: FastAPI
- Worker: RQ + Redis
- Banco: PostgreSQL + pgvector
- IA: OpenAI, LangChain, LangGraph
- Redis: fila e rate limit

Documentação visual:

- [docs/architecture.md](C:/IA/auto-manual-ai/docs/architecture.md:1)

## Experiência web

- `/`: landing page do projeto, com foco em apresentação, arquitetura e deploy
- `/documentos`: workspace de consulta, com seleção de documento, resumo, tópicos, histórico local de perguntas, respostas com fontes e ações administrativas para upload e delete
- `/observabilidade`: página pública de portfólio sobre tracing do RAG, avaliação semântica, regressão sintética 4B.4 e o diagnóstico do caso `aur-05`; usa somente dados históricos selecionados, sem conexão do navegador ao Langfuse

## Documentação

- [Avaliação sintética do RAG](docs/evaluation.md): 18 casos versionados, juízes semânticos, captura local controlada do contexto real, calibração auditável e revisão humana; publicação explícita no Langfuse.
- [Diagnóstico RAG 4A](docs/rag-diagnosis-4a.md): análise de `aur-05`, `aur-07` e `bor-06`, causas prováveis e plano de validação da 4B.
- [Diagnóstico da recuperação 4B.1](docs/rag-retrieval-diagnosis-4b1.md): rastreamento dirigido de `aur-05` e `bor-06`, perda de chunks e parâmetros de seleção.
- [Correção da deduplicação 4B.2](docs/rag-dedup-evaluation-4b2.md): índice `0` preservado, contexto verificado e avaliação dirigida com controles.
- [Auditoria da avaliação 4B.3](docs/evaluation-audit-4b3.md): divergências de abstenção auditadas offline, decisões originais preservadas e revisão humana.
- [Regressão completa 4B.4](docs/rag-regression-4b4.md): comparação dos 18 casos com a baseline 3D, contextos reais, scores, latência e tokens.
- [Revisão humana 4C](docs/human-review-4c.md): evidências e opções de política para `aur-07`, `bor-05` e `bor-06`, com formulário de decisões em branco.
- [Observabilidade Langfuse](docs/langfuse.md): trace opcional do fluxo de perguntas, busca vetorial e generations, sem enviar conteúdo de perguntas, chunks ou respostas.

- [docs/architecture.md](C:/IA/auto-manual-ai/docs/architecture.md:1)
- [docs/deploy-railway.md](C:/IA/auto-manual-ai/docs/deploy-railway.md:1)
- [docs/railway-services.md](C:/IA/auto-manual-ai/docs/railway-services.md:1)
- [docs/railway-deploy-checklist.md](C:/IA/auto-manual-ai/docs/railway-deploy-checklist.md:1)
- [docs/pre-deploy-checklist.md](C:/IA/auto-manual-ai/docs/pre-deploy-checklist.md:1)

## Fluxo Smart Ingest

- Upload PDF
- API salva o PDF temporariamente em `smartdocs.uploaded_files`
- cria `processing_job`
- envia job para Redis Queue
- worker recupera o arquivo pelo banco
- worker processa o PDF
- worker extrai texto
- gera chunks
- enriquece chunks com IA
- gera `embedding_content`
- cria embeddings
- grava no PostgreSQL/pgvector
- gera resumo automático
- registra documento
- worker remove o arquivo temporário após sucesso/falha
- libera consulta

## Fluxo de pergunta

- Pergunta do usuário
- geração de queries alternativas
- busca vetorial com pgvector
- relevance grader
- montagem de contexto
- geração da resposta final
- retorno com fontes, páginas e motivos de relevância

## Segurança e controle de uso

- Upload e delete disponíveis apenas para admin
- Login admin via cookie HttpOnly
- `COOKIE_SECURE=true` em produção
- Chat público com rate limit por IP e limite global diário
- Usage logs em PostgreSQL
- PDF removido após processamento
- O PDF original é armazenado apenas temporariamente para processamento e removido após o Smart Ingest

## Como rodar localmente

1. Configure os arquivos de ambiente com base em:
   - [backend/.env.example](C:/IA/auto-manual-ai/backend/.env.example:1)
   - [frontend/.env.example](C:/IA/auto-manual-ai/frontend/.env.example:1)

2. Suba os serviços:

```bash
docker compose up -d --build
```

3. Execute o bootstrap do banco:

```bash
docker compose exec backend python app/database/bootstrap.py
```

4. Acesse:

- Frontend: `http://localhost:2000`
- API Docs: `http://localhost:8000/docs`

## Variáveis de ambiente

Os exemplos de configuração estão em:

- [backend/.env.example](C:/IA/auto-manual-ai/backend/.env.example:1)
- [frontend/.env.example](C:/IA/auto-manual-ai/frontend/.env.example:1)

## Deploy

O guia inicial de deploy está em:

- [docs/deploy-railway.md](C:/IA/auto-manual-ai/docs/deploy-railway.md:1)

## Roadmap

As próximas melhorias planejadas para o SmartDocs AI estão documentadas em [docs/roadmap.md](docs/roadmap.md).

## Status

Projeto em fase MVP / demo pública.
