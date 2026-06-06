# Pré-Deploy Checklist — SmartDocs AI

## Documentos relacionados

- [Deploy Railway](C:/IA/auto-manual-ai/docs/deploy-railway.md:1)
- [Serviços Railway](C:/IA/auto-manual-ai/docs/railway-services.md:1)
- [Checklist Operacional Railway](C:/IA/auto-manual-ai/docs/railway-deploy-checklist.md:1)

## Segurança

- [ ] confirmar que `.env` não está versionado
- [ ] confirmar que `OPENAI_API_KEY` não aparece no repositório
- [ ] confirmar `JWT_SECRET_KEY` forte em produção
- [ ] confirmar `COOKIE_SECURE=true` em produção
- [ ] confirmar `COOKIE_DOMAIN` correto
- [ ] confirmar endpoint `/auth/admin/seed` removido
- [ ] confirmar upload e delete protegidos por admin

## Banco e bootstrap

- [ ] rodar `python app/database/bootstrap.py`
- [ ] confirmar migrations aplicadas
- [ ] confirmar temas carregados
- [ ] confirmar admin seed criado
- [ ] confirmar pgvector habilitado

## Redis e worker

- [ ] confirmar Redis conectado
- [ ] confirmar worker rodando
- [ ] confirmar Smart Ingest processa jobs da fila
- [ ] confirmar job `failed` registra erro

## Frontend

- [ ] confirmar `NEXT_PUBLIC_API_URL` correto
- [ ] confirmar `INTERNAL_API_URL` correto
- [ ] confirmar login e logout admin
- [ ] confirmar chat público sem login
- [ ] confirmar upload aparece apenas para admin

## Rate limit e logs

- [ ] confirmar `/chat/ask` aplica rate limit
- [ ] confirmar `rate_limit_blocked` em `usage_logs`
- [ ] confirmar `chat_question` em `usage_logs`
- [ ] confirmar `smart_ingest_started`, `smart_ingest_completed` e `smart_ingest_failed`
- [ ] confirmar `document_deleted`

## Testes finais

- [ ] `GET /health/database`
- [ ] `GET /health/redis`
- [ ] `GET /documents`
- [ ] `POST /chat/ask`
- [ ] login admin
- [ ] upload de PDF pequeno
- [ ] acompanhar job
- [ ] perguntar sobre documento
- [ ] apagar documento
