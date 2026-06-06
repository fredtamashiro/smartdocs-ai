# Deploy Railway — SmartDocs AI

## Documentos relacionados

- [Serviços Railway](C:/IA/auto-manual-ai/docs/railway-services.md:1)
- [Checklist de Pré-Deploy](C:/IA/auto-manual-ai/docs/pre-deploy-checklist.md:1)
- [Checklist Operacional Railway](C:/IA/auto-manual-ai/docs/railway-deploy-checklist.md:1)

## Visão geral da arquitetura

- `smartdocs-frontend`: Next.js
- `smartdocs-api`: FastAPI
- `smartdocs-worker`: RQ worker
- PostgreSQL com pgvector
- Redis

## Serviços necessários no Railway

- Frontend
- API
- Worker
- PostgreSQL/pgvector
- Redis

## Comandos de start

API:

```sh
sh scripts/start_api.sh
```

Worker:

```sh
sh scripts/start_worker.sh
```

Bootstrap:

```sh
python app/database/bootstrap.py
```

Frontend:

```sh
npm run start
```

## Variáveis de ambiente da API/Worker

- `APP_ENV=production`
- `DATABASE_URL`
- `REDIS_URL`
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `OPENAI_CHAT_TEMPERATURE`
- `OPENAI_EMBEDDING_MODEL`
- `MAX_UPLOAD_FILE_SIZE_MB`
- `CHAT_RATE_LIMIT_PER_IP_DAILY`
- `CHAT_RATE_LIMIT_GLOBAL_DAILY`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
- `ADMIN_SEED_EMAIL`
- `ADMIN_SEED_PASSWORD`
- `ADMIN_SEED_NAME`
- `ADMIN_COOKIE_NAME`
- `COOKIE_SECURE=true`
- `COOKIE_SAMESITE=lax`
- `COOKIE_DOMAIN=.fredtamashiro.com.br`
- `FRONTEND_ORIGINS=https://smartdocs.fredtamashiro.com.br`
- `MAX_RELEVANCE_SCORE`
- `MAX_DISPLAY_SOURCE_SCORE`
- `DISPLAY_SOURCE_SCORE_MARGIN`
- `MIN_ENRICHED_CHUNK_QUALITY_SCORE`

## Variáveis de ambiente do frontend

- `INTERNAL_API_URL`
- `NEXT_PUBLIC_API_URL`

## Domínios sugeridos

- `smartdocs.fredtamashiro.com.br` para frontend
- `api-smartdocs.fredtamashiro.com.br` para API

## Ordem de deploy

- criar PostgreSQL/pgvector
- criar Redis
- configurar API
- rodar bootstrap
- configurar worker
- configurar frontend
- configurar domínios
- testar login admin
- testar upload
- testar chat público

## Observações de segurança

- não expor endpoint de seed admin
- usar `COOKIE_SECURE=true` em produção
- usar `JWT_SECRET_KEY` forte
- manter upload apenas admin
- chat público protegido por rate limit

## Checklist final de teste

- `GET /health/database`
- `GET /health/redis`
- login admin
- Smart Ingest
- worker processando job
- chat público
- usage logs
