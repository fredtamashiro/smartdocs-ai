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

## Documentação

- [docs/architecture.md](C:/IA/auto-manual-ai/docs/architecture.md:1)
- [docs/deploy-railway.md](C:/IA/auto-manual-ai/docs/deploy-railway.md:1)
- [docs/railway-services.md](C:/IA/auto-manual-ai/docs/railway-services.md:1)
- [docs/railway-deploy-checklist.md](C:/IA/auto-manual-ai/docs/railway-deploy-checklist.md:1)
- [docs/pre-deploy-checklist.md](C:/IA/auto-manual-ai/docs/pre-deploy-checklist.md:1)

## Fluxo Smart Ingest

- Upload PDF
- cria `processing_job`
- envia job para Redis Queue
- worker extrai texto
- gera chunks
- enriquece chunks com IA
- gera `embedding_content`
- cria embeddings
- grava no PostgreSQL/pgvector
- gera resumo automático
- registra documento
- remove PDF temporário
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

- Painel admin de métricas
- Melhorias de UX
- Exportação de respostas
- Suporte a múltiplos projetos / demos
- Storage externo opcional
- Avaliação automatizada de respostas
- Experimento futuro com QA extrativo Hugging Face

## Status

Projeto em fase MVP / demo pública.
