# SmartDocs AI Frontend

Interface web em Next.js para upload, processamento e consulta de documentos PDF usando o backend SmartDocs AI.

O frontend permite enviar PDFs para o Smart Ingest, acompanhar jobs de processamento, listar documentos cadastrados e conversar com cada documento por meio do endpoint `/chat/ask`.

## Funcionalidades

- Upload de documentos em PDF
- Selecao de tema para o Smart Ingest
- Acompanhamento de jobs de processamento
- Listagem dos documentos cadastrados
- Chat por documento
- Exibicao de fontes usadas na resposta
- Mensagens de erro retornadas pela API, incluindo bloqueios por rate limit
- Historico local de perguntas e respostas na tela

## Stack utilizada

- Next.js
- React
- TypeScript
- Tailwind CSS
- Docker

## Arquitetura

```text
Frontend Next.js
      ->
API FastAPI
      ->
Smart Ingest
      ->
PostgreSQL + pgvector
      ->
LangGraph RAG Flow
      ->
Resposta com fontes
```

## Fluxo principal

```text
1. Usuario envia um PDF
2. Backend salva o arquivo localmente
3. Texto e extraido pagina por pagina
4. Texto e limpo e dividido em chunks
5. Chunks sao persistidos no PostgreSQL
6. Chunks sao enriquecidos com IA
7. Embeddings sao gerados com OpenAI
8. Embeddings sao armazenados no PostgreSQL com pgvector
9. Usuario faz uma pergunta
10. Sistema busca chunks semanticamente relevantes via pgvector
11. LangGraph avalia se o contexto e relevante
12. LLM gera resposta usando somente o contexto recuperado
13. Frontend exibe resposta e fontes
```

## Endpoints principais usados

### Upload e processamento de PDF

```http
POST /documents/ingest
```

Recebe um arquivo PDF, processa o conteudo e persiste chunks, enriched chunks e embeddings no PostgreSQL.

### Listagem de documentos

```http
GET /documents
```

Retorna os documentos ja ingeridos.

### Pergunta sobre um documento

```http
POST /chat/ask
```

Exemplo de payload:

```json
{
  "document_id": "uuid-do-documento",
  "question": "Como ligo o farol?",
  "k": 4
}
```

Exemplo de resposta:

```json
{
  "question": "Como ligo o farol?",
  "answer": "Para ligar o farol baixo, coloque o interruptor de iluminacao na posicao correspondente...",
  "sources": [
    {
      "page": 33,
      "chunk_index": 77,
      "score": 0.7294,
      "preview": "Coloque o interruptor de iluminacao na posicao para ligar o farol baixo..."
    }
  ]
}
```

## Como rodar

Na raiz do projeto:

```bash
docker compose up --build
```

Acesse:

```text
Frontend:
http://localhost:2000

Backend Swagger:
http://localhost:8000/docs
```

## Observacao sobre custos

Este projeto usa a OpenAI API para gerar embeddings e respostas com LLM. O backend possui rate limit com Redis para proteger a demo publica e controlar custo de uso.
