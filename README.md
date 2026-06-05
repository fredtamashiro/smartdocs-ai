# SmartDocs AI

Plataforma inteligente para consulta de documentos PDF com IA generativa, RAG, embeddings, LangGraph, temas configuraveis e processamento assincrono.

## Principais funcionalidades

- Upload de PDFs
- Smart Ingest assincrono
- Extracao de texto
- Chunking
- Enriquecimento semantico de chunks com LLM
- Geracao de `embedding_content`
- Persistencia em PostgreSQL
- Busca vetorial com pgvector
- Consulta via chat com fontes
- Multi-query retrieval
- Relevance grading
- Temas configuraveis
- Resumo automatico do documento
- Perguntas sugeridas
- Rate limit com Redis para proteger o chat
- Logs de uso para auditoria
- Exclusao de documentos e dados relacionados
- Frontend em Next.js

## Arquitetura em alto nivel

- Frontend Next.js
- Backend FastAPI
- PostgreSQL com pgvector
- Redis para rate limit
- OpenAI LLM/Embeddings
- LangChain/LangGraph
- Storage local para uploads de PDFs

## Fluxo Smart Ingest

```text
Upload PDF
-> escolher tema
-> criar job
-> extrair texto
-> gerar chunks
-> persistir chunks no PostgreSQL
-> enriquecer chunks com IA
-> persistir enriched chunks no PostgreSQL
-> gerar embeddings
-> persistir embeddings no pgvector
-> gerar resumo automatico
-> registrar documento
-> liberar consulta no chat
```

## Pipeline de pergunta

```text
Pergunta do usuario
-> geracao de queries alternativas
-> embedding da pergunta
-> busca vetorial no PostgreSQL + pgvector
-> avaliacao de relevancia dos chunks
-> geracao de resposta com base no contexto
-> retorno com fontes, paginas e motivos de relevancia
```

## Tecnologias

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- pgvector
- Redis
- LangChain
- LangGraph
- OpenAI
- Next.js
- React
- TypeScript
- Docker

## Como rodar localmente

1. Copie o arquivo `.env.example` para `.env`.
2. Configure a variavel `OPENAI_API_KEY`.
3. Suba os servicos:

```bash
docker compose up --build
```

4. Acesse o frontend:

```text
http://localhost:2000
```

5. Acesse a documentacao do backend:

```text
http://localhost:8000/docs
```

## Exemplos de uso

- Consultar manual automotivo
- Consultar documentacao tecnica
- Consultar norma/regulamento
- Consultar politica interna ou contrato

## Roadmap

- Melhorar UX final
- Autenticacao
- Painel admin para logs de uso
- Avaliacao automatizada de respostas
- Deploy
- Experimento futuro com QA extrativo usando Hugging Face
