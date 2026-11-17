# Langfuse: etapas 1 e 2

## Objetivo e arquitetura

O Langfuse registra a duração e o resultado de cada execução de `POST /chat/ask` para ajudar a investigar falhas e latência do RAG. O endpoint abre uma observação raiz `smartdocs.rag.query` antes da lógica existente, abrangendo validação, cache e grafo LangGraph. O serviço `backend/app/services/langfuse_observability.py` inicializa o cliente uma vez por processo e fecha a observação tanto em sucesso quanto em erro. Falhas de telemetria não alteram a resposta da API.

O SDK oficial Python 5.2.0 usa OpenTelemetry e é compatível com Python 3.12. A aplicação lê `backend/.env` por `pydantic-settings`; por isso as configurações são passadas ao construtor do SDK, cujo cliente é reutilizado. Não é necessário executar Langfuse em Docker.
O exportador aceita apenas spans criados explicitamente pelo SDK Langfuse, evitando a inclusão incidental de spans de outras bibliotecas.
O recurso OpenTelemetry recebe `service.name=smartdocs-backend` por padrão no script de inicialização da API. O nome pode ser alterado por `OTEL_SERVICE_NAME` no ambiente do processo antes da criação do cliente; ele não é derivado de `APP_NAME` nem de `pydantic-settings`.

## Fluxo observado

```text
smartdocs.rag.query                         raiz, inclusive respostas por cache
├── smartdocs.rag.query_rewrite             generation, se houver reescrita
├── smartdocs.rag.retrieve                 span de recuperação
│   └── smartdocs.rag.vector_search         um span por consulta ao pgvector
├── smartdocs.rag.classify_batch            generation, se o grader em lote executar
│   ou smartdocs.rag.classify_chunk         uma generation por chunk classificado
└── smartdocs.rag.generate_answer           generation, somente se houver contexto
```

O grafo pode pular reescrita, classificação ou geração conforme suas regras atuais. Resposta por cache não cria spans de busca ou LLM. Sem documentos relevantes, o grafo segue para a resposta de ausência de contexto, sem generation de resposta.

Os spans de recuperação registram duração, limites, contagens, presença de contexto e distâncias cosseno. No SQL, [`<=>` é distância cosseno](https://github.com/pgvector/pgvector#vector-operators): valores menores indicam vetores mais próximos. Não há métrica de similaridade calculada. Falhas de busca recebem categoria operacional; o fluxo mantém o fallback já existente.

As generations registram nome do modelo retornado pelo provider quando disponível (senão o modelo configurado), duração, status, identificador local da versão do prompt e `usage_details` de entrada, saída e total apenas quando esses números vierem da resposta. Tokens de cache e raciocínio são subconjuntos desses totais e não são somados novamente. O código não envia custo estimado; o Langfuse pode inferir custo quando tiver preço cadastrado para o modelo.

Foi escolhida instrumentação manual com context managers. O `CallbackHandler` do Langfuse v5 requer `langchain-core>=1`, enquanto o projeto usa `langchain-core 0.3.x`; callbacks também exigiriam cuidado adicional para impedir captura automática de prompts e respostas.

## Configuração

| Variável | Padrão | Uso |
| --- | --- | --- |
| `LANGFUSE_TRACING_ENABLED` | `false` | Ativa a integração somente quando também há duas chaves. |
| `LANGFUSE_PUBLIC_KEY` | vazio | Chave pública do projeto. |
| `LANGFUSE_SECRET_KEY` | vazio | Chave secreta do projeto. |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` | URL da região do projeto. |
| `LANGFUSE_SAMPLE_RATE` | `1.0` | Fração de traces enviada, entre `0.0` e `1.0`. |
| `OTEL_SERVICE_NAME` | `smartdocs-backend` | Nome do serviço no recurso OpenTelemetry exibido nos traces. O script de inicialização fornece esse padrão se a variável estiver ausente. |

1. Crie uma conta e um projeto em [Langfuse Cloud](https://cloud.langfuse.com/). Nas configurações do projeto, crie uma chave de API e copie as chaves pública e secreta. Use a URL da região em que criou o projeto.
2. Copie `backend/.env.example` para `backend/.env` e preencha as chaves apenas nesse arquivo local ou em variáveis de ambiente do deploy. Defina `LANGFUSE_TRACING_ENABLED=true`. Não versione as chaves.
3. Inicie a API normalmente e faça uma pergunta em `POST /chat/ask` com um documento válido. No projeto Langfuse, abra **Traces** e procure `smartdocs.rag.query`. A exportação é assíncrona e pode levar alguns segundos. Abra o trace para ver a hierarquia acima.
4. No trace novo, confira `resourceAttributes.service.name` em **Metadata**. Ele deve ser `smartdocs-backend` (ou o valor definido em `OTEL_SERVICE_NAME`). Traces antigos mantêm o nome registrado na época; reinicie o processo da API depois de mudar essa variável.

### Se os traces não aparecerem

O Compose monta `backend/app` no container, mas instala dependências durante o build da imagem. Depois de adicionar ou atualizar `langfuse` em `requirements.txt`, execute `docker compose build backend` e `docker compose up -d --no-deps backend`. Alterações em `backend/.env` também exigem recriar o container para atualizar o ambiente do processo. O `.dockerignore` impede a inclusão do `.env` na imagem; o Compose fornece as variáveis por `env_file`. No container da API, confirme a versão com `docker compose exec backend python -m pip show langfuse`; não imprima chaves ou o ambiente completo. Para autenticação, use `auth_check()` apenas em diagnóstico, conforme a [documentação oficial](https://langfuse.com/docs/observability/sdk/troubleshooting-and-faq). Em scripts curtos, finalize o span e chame `flush()`; não chame `flush()` por requisição. A API de observações pode demorar para refletir uma exportação.

Para investigar uma resposta incorreta, verifique primeiro `retrieved_chunks_count`, `has_context`, `best_cosine_distance` e as distâncias por busca. Depois veja se o grader executou e compare latência, modelo e tokens das generations. O trace não contém o texto da pergunta, dos chunks ou da resposta; use os dados operacionais do aplicativo, conforme a política local, para uma investigação de conteúdo.

## Dados e próximos passos

O payload enviado contém somente metadados numéricos e operacionais. Perguntas completas, respostas, documentos, chunks, IPs, IDs de documento e mensagens de exceção não são enviados. A integração não usa captura automática de LangChain ou OpenAI. Os usage logs existentes são independentes e continuam com sua política atual.

Limitações: embeddings da busca e do cache não trazem uso de tokens neste fluxo; custos não são calculados pela aplicação; ausência de usage do provider resulta em generation sem contagem; prompts são construídos diretamente no código e seus identificadores são versões locais. Datasets, avaliações e scores de qualidade ficam para a etapa 3.
