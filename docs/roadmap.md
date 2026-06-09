# Roadmap — SmartDocs AI

O SmartDocs AI já está funcional em produção como uma aplicação full stack de IA para consulta inteligente de PDFs. Este roadmap registra melhorias futuras planejadas para o projeto, com foco em performance, experiência de uso, observabilidade, administração e evolução da IA.

## 1. Performance e qualidade das respostas

- Melhorar o tempo de resposta do `/chat/ask` sem perder qualidade.
- Continuar analisando `usage_logs` para identificar gargalos entre cache, geração de queries, retrieval, relevance grader e geração da resposta final.
- Calibrar `SKIP_GRADER_FOR_HIGH_CONFIDENCE_RETRIEVAL`.
- Reduzir contexto enviado ao modelo em perguntas objetivas.
- Avaliar respostas mais curtas para perguntas diretas.
- Melhorar uso de cache exato e semântico por documento.
- Avaliar streaming de resposta para melhorar a percepção de velocidade.

## 2. Contexto conversacional

- Aplicar contexto entre perguntas, inicialmente considerando pelo menos a pergunta anterior.
- Permitir perguntas de continuação como “explique melhor”, “resuma isso”, “me dê um exemplo”, “e quais são as exceções?”.
- Manter o contexto limitado ao documento selecionado.
- Evitar respostas fora das fontes do documento.
- Registrar nos logs quando uma resposta usar contexto anterior.

## 3. Painel administrativo de logs

- Criar uma página admin para visualizar `shared.usage_logs`.
- Exibir eventos como `page_view`, `chat_question`, `chat_question_blocked`, `rate_limit_blocked`, `smart_ingest_started`, `smart_ingest_completed`, `smart_ingest_failed`, `admin_login` e `document_deleted`.
- Permitir filtros por tipo de evento, documento, período, status de cache e tempo de resposta.
- Exibir métricas simples:
- total de acessos;
- total de perguntas;
- perguntas bloqueadas;
- cache hit/cache miss;
- média de tempo de resposta;
- documentos mais consultados.

## 4. Página de últimas atualizações

- Criar uma área pública ou seção na Home com as últimas melhorias do projeto.
- Exibir melhorias de performance, UX, segurança, arquitetura e novos recursos.
- Avaliar criação de um `CHANGELOG.md` para registrar versões e mudanças relevantes.

## 5. Monitoramento simples de acessos

- Criar evento interno `page_view` em `shared.usage_logs`.
- Registrar acessos à Home e ao Workspace de documentos.
- Evitar uso de ferramentas externas de analytics neste primeiro momento.
- Não registrar dados sensíveis ou conteúdo das perguntas em eventos de acesso.

## 6. Experiência do usuário

- Refinar estados de loading durante a geração da resposta.
- Melhorar feedback visual para cache hit/cache miss, se fizer sentido.
- Melhorar responsividade mobile.
- Adicionar botão para copiar resposta.
- Adicionar botão para limpar histórico local do documento.
- Avaliar modo compacto para documentos com muitos metadados.

## 7. Segurança e privacidade

- Continuar evoluindo a sanitização de perguntas.
- Revisar bloqueio de dados sensíveis como CPF, telefone, e-mail, tokens e senhas.
- Garantir que perguntas bloqueadas não sejam salvas em cache, embeddings ou logs com conteúdo bruto.
- Avaliar criação de uma página simples de privacidade explicando o uso da demo.

## 8. Evoluções futuras de IA

- Avaliar busca híbrida combinando pgvector com full-text search.
- Melhorar reranking sem depender sempre de LLM.
- Avaliar pré-processamento mais rico no Smart Ingest.
- Gerar respostas pré-cacheadas para perguntas sugeridas.
- Avaliar avaliação automática de qualidade das respostas.
- Comparar abordagens com QA extrativo como experimento, sem substituir o RAG principal.

## 9. Operação e deploy

- Revisar variáveis de produção periodicamente.
- Documentar processo de reset de senha admin.
- Melhorar checklist pós-deploy.
- Avaliar alertas simples para falha de worker ou Smart Ingest.
- Avaliar limpeza automática de caches antigos.
