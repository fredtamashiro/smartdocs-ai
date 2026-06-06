# Railway Deploy Checklist — SmartDocs AI

## Documentos relacionados

- [Deploy Railway](C:/IA/auto-manual-ai/docs/deploy-railway.md:1)
- [Serviços Railway](C:/IA/auto-manual-ai/docs/railway-services.md:1)
- [Checklist de Pré-Deploy](C:/IA/auto-manual-ai/docs/pre-deploy-checklist.md:1)

## Serviços

- [ ] criar `smartdocs-api`
- [ ] criar `smartdocs-worker`
- [ ] criar `smartdocs-frontend`
- [ ] criar PostgreSQL com pgvector
- [ ] criar Redis

## Root directory

- [ ] API: `/backend`
- [ ] Worker: `/backend`
- [ ] Frontend: `/frontend`

## Start commands

- [ ] API: `sh scripts/start_api.sh`
- [ ] Worker: `sh scripts/start_worker.sh`
- [ ] Frontend: `npm run start`

## Variáveis da API

- [ ] `APP_ENV=production`
- [ ] `DATABASE_URL`
- [ ] `REDIS_URL`
- [ ] `OPENAI_API_KEY`
- [ ] `OPENAI_CHAT_MODEL`
- [ ] `OPENAI_CHAT_TEMPERATURE`
- [ ] `OPENAI_EMBEDDING_MODEL`
- [ ] `MAX_UPLOAD_FILE_SIZE_MB`
- [ ] `CHAT_RATE_LIMIT_PER_IP_DAILY`
- [ ] `CHAT_RATE_LIMIT_GLOBAL_DAILY`
- [ ] `JWT_SECRET_KEY`
- [ ] `JWT_ALGORITHM`
- [ ] `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
- [ ] `ADMIN_COOKIE_NAME`
- [ ] `COOKIE_SECURE=true`
- [ ] `COOKIE_SAMESITE=lax`
- [ ] `COOKIE_DOMAIN=.fredtamashiro.com.br`
- [ ] `FRONTEND_ORIGINS=https://smartdocs.fredtamashiro.com.br`
- [ ] `MAX_RELEVANCE_SCORE`
- [ ] `MAX_DISPLAY_SOURCE_SCORE`
- [ ] `DISPLAY_SOURCE_SCORE_MARGIN`
- [ ] `MIN_ENRICHED_CHUNK_QUALITY_SCORE`
- [ ] `ADMIN_SEED_EMAIL`
- [ ] `ADMIN_SEED_PASSWORD`
- [ ] `ADMIN_SEED_NAME`

## Variáveis do Worker

- [ ] `APP_ENV=production`
- [ ] `DATABASE_URL`
- [ ] `REDIS_URL`
- [ ] `OPENAI_API_KEY`
- [ ] `OPENAI_CHAT_MODEL`
- [ ] `OPENAI_CHAT_TEMPERATURE`
- [ ] `OPENAI_EMBEDDING_MODEL`
- [ ] `MAX_UPLOAD_FILE_SIZE_MB`
- [ ] `MIN_ENRICHED_CHUNK_QUALITY_SCORE`
- [ ] `JWT_SECRET_KEY`

## Variáveis do Frontend

- [ ] `NEXT_PUBLIC_API_URL=https://api-smartdocs.fredtamashiro.com.br`
- [ ] `INTERNAL_API_URL=https://api-smartdocs.fredtamashiro.com.br`

## Domínios

- [ ] `smartdocs.fredtamashiro.com.br`
- [ ] `api-smartdocs.fredtamashiro.com.br`

## Bootstrap

- [ ] rodar `python app/database/bootstrap.py`

## Checklist de validação

- [ ] health database
- [ ] health redis
- [ ] login admin
- [ ] logout admin
- [ ] Smart Ingest
- [ ] worker processando job
- [ ] chat público
- [ ] rate limit
- [ ] usage logs
