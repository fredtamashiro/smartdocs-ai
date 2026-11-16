# Avaliação sintética do RAG: etapa 3A

O diagnóstico de falhas e o plano de validação da próxima etapa estão em [Etapa 4A — Diagnóstico das falhas do RAG](rag-diagnosis-4a.md).

## Dataset e preparação

`backend/app/evaluation/synthetic_rag_v1.json` contém dois documentos inteiramente fictícios, com cinco trechos cada, e 18 casos com ID estável, pergunta, documento, categoria, resposta possível ou abstenção, expressões de fatos esperados e exigência de citação. As categorias incluem perguntas factuais, distribuídas, com múltiplos trechos, inexistentes, ambíguas e com citação. A versão `1.0.0` e o SHA-256 do arquivo identificam exatamente o conteúdo usado.

O comando abaixo registra os documentos com status `evaluation` no PostgreSQL local e gera embeddings com o modelo real configurado. Ele usa o schema e a rotina de indexação existentes; uma segunda execução com o mesmo dataset reutiliza os embeddings. Não execute a preparação contra um banco de produção. O comando recusa `APP_ENV` fora de `local`, `development` e `test`.

```powershell
docker compose exec -T backend python -m app.evaluation.cli prepare
```

## Experimento local

```powershell
docker compose exec -T backend python -m app.evaluation.cli run --run-name baseline-v1
```

O executor chama `answer_question_with_manual_graph()` diretamente e usa o Experiment Runner do Langfuse 5.2.0 com tracing desligado. O modelo e o pgvector são reais; o frontend, cache e rate limit do endpoint não participam. **Dados locais não são enviados ao Langfuse nesse modo**, embora as chamadas ao provider OpenAI ocorram normalmente. O relatório JSON é salvo em `backend/app/evaluation/reports/` no host e contém respostas apenas dos documentos sintéticos. Para um teste rápido, adicione `--limit 1`; essa execução não substitui a avaliação completa.

Cada caso registra sucesso de execução, comportamento de abstenção, presença da citação `(p. N)` quando exigida, cobertura lexical dos fatos esperados, latência, páginas das fontes, generations e tokens retornados pelo provider. O custo fica `null` quando o provider não o retorna. Tokens ausentes não são estimados; `usage_complete=false` indica total parcial. Não há uma nota geral de qualidade.

O relatório registra `metrics_version`. Se as regras determinísticas forem corrigidas, recalcule um relatório salvo sem repetir chamadas ao modelo. O comando cria outro arquivo e preserva o original:

```powershell
docker compose exec -T backend python -m app.evaluation.cli rescore /app/app/evaluation/reports/primeiro.json
```

**Interpretação:** cobertura lexical indica apenas que expressões esperadas apareceram; ela não prova correção factual nem que a resposta está fundamentada nos trechos. Presença de citação não verifica se a página sustenta a afirmação. A detecção de abstenção reconhece um conjunto restrito de frases. Casos ambíguos foram definidos para abstenção e podem expor limitações do comportamento atual. Revise os relatórios ao interpretar diferenças.

## Publicação explícita no Langfuse

Use somente depois de preparar os documentos sintéticos e configurar Langfuse com `LANGFUSE_TRACING_ENABLED=true` e `LANGFUSE_SAMPLE_RATE=1.0` no container. A opção `--publish` envia **apenas** o dataset sintético e os resultados dessas perguntas. O dataset Cloud recebe nome com versão e hash; IDs determinísticos e comparação dos itens evitam duplicações em preparações repetidas.

```powershell
docker compose exec -T backend python -m app.evaluation.cli run --publish --run-name baseline-v1-cloud
```

O Experiment Runner associa cada resultado a um trace; `smartdocs.rag.query` e suas observações internas aparecem como filhos da execução do item. O processo curto chama `flush()` ao terminar. No Langfuse Cloud, abra **Datasets** e procure `smartdocs-synthetic-rag-1.0.0-<hash>`; em **Experiments**, abra o nome da execução para comparar casos e acessar seus traces. Publicar uma nova execução exige um novo `--run-name`. A publicação não é necessária para relatórios locais.

## Comparar duas execuções

```powershell
docker compose exec -T backend python -m app.evaluation.cli compare /app/app/evaluation/reports/primeiro.json /app/app/evaluation/reports/segundo.json
```

O comparador exige o mesmo SHA-256 do dataset e a mesma versão das métricas. Ele mostra diferenças de taxa de execução, abstenção, citações, cobertura lexical e latência média. Mantenha os dois relatórios completos para examinar cada caso.

## Avaliação semântica: etapa 3B

O comando `judge` avalia um relatório RAG **já salvo**, sem executar novamente o grafo nem alterar prompts de produção. Aceita apenas casos cujos IDs, perguntas, documentos, critérios e hash correspondam ao dataset sintético versionado. O modelo avaliador OpenAI é configurado por `EVALUATION_JUDGE_MODEL` (padrão `gpt-4.1-mini`) e `EVALUATION_JUDGE_TIMEOUT_SECONDS` (padrão `60`). Use `--model` para uma execução específica. A temperatura é 0, com saída estruturada validada por Pydantic. `--concurrency` controla as chamadas simultâneas (padrão 2). O modelo avaliador recebe perguntas, respostas e documentos **sintéticos**; não use relatórios de produção.

```powershell
docker compose exec -T backend python -m app.evaluation.cli judge /app/app/evaluation/reports/primeiro.json --concurrency 2
```

Por padrão, o resultado fica em `primeiro.judged.json` e **nenhum score é publicado**. O relatório conserva as métricas RAG, registra score, justificativa, versão da rubrica, latência e tokens do avaliador separadamente por critério. Custo é `null` quando não informado pelo provider; não há estimativa. Um resultado `not_evaluable` tem score `null` e não entra na média. Falhas e timeouts do juiz seguem essa regra e aparecem em `errors`.

Todas as rubricas estão na versão `1.0.3`:

| Critério | Escala e regra |
| --- | --- |
| `answer_correctness` | 1 para fatos completos e semanticamente corretos, 0,5 para resposta parcial, 0 para erro material. Usa o documento sintético inteiro como referência. Perguntas sem resposta esperada ficam não avaliáveis neste critério. |
| `faithfulness` | 1 quando todas as afirmações materiais são sustentadas pela evidência recuperada, 0,5 quando só parte é sustentada, 0 quando a afirmação central não é sustentada ou contradiz a evidência. Sem evidência suficiente, fica não avaliável. |
| `abstention_correctness` | O juiz classifica o comportamento como resposta, abstenção, pedido de esclarecimento ou misto. A escala aplica 1 quando responde a pergunta respondível ou se abstém/pede esclarecimento em pergunta impossível ou ambígua, 0 no comportamento oposto, 0,5 em comportamento misto. O relatório preserva `model_score`, `model_behavior` e `model_reason`; `reason` acrescenta a regra aplicada quando há divergência. Quando o juiz chama de resposta uma recusa explícita já detectada pela métrica conservadora da 3A, a classificação é corrigida e aparece em `judge_behavior_disagreements`. |

O relatório traz `semantic_summary` e `error_analysis`: erros factuais, respostas parciais, falta de fundamentação, falhas de abstenção e divergências entre cobertura lexical e julgamento semântico. Os casos ambíguos `aur-07` e `bor-06` são destacados. A classificação de erros usa o limiar operacional de 0,8; examine as justificativas antes de concluir que houve regressão.

**Evidência da baseline 3A:** relatórios antigos guardam apenas as páginas das fontes. Como cada página do fixture corresponde a um único chunk sintético, o avaliador reconstrói essas páginas e marca `evidence_origin=synthetic_pages_reconstructed`. Relatórios novos guardam as prévias das fontes retornadas pelo grafo e marcam `displayed_sources`. Essas fontes podem ser um subconjunto do contexto realmente passado ao modelo; portanto, um score de fundamentação baixo exige revisão do trace. O juiz também pode errar, variar entre execuções e sofrer viés da rubrica. Uma citação presente não comprova que sua página sustenta a resposta.

Para publicar scores, primeiro gere um **novo experimento RAG publicado** com `run --publish`. Depois avalie esse relatório com `judge --publish`. O comando exige `experiment_id` e `trace_id` para todos os casos, associa cada score ao trace original e usa IDs estáveis para reenvios. Resultados `not_evaluable` não são publicados como zero. O processo curto chama `flush()` após os scores. A execução local anterior não pode receber scores no Cloud porque não possui traces publicados.

```powershell
docker compose exec -T backend python -m app.evaluation.cli run --publish --run-name baseline-3b-cloud
docker compose exec -T backend python -m app.evaluation.cli judge /app/app/evaluation/reports/RELATORIO_PUBLICADO.json --publish
```

Abra **Experiments** no Langfuse Cloud, selecione `baseline-3b-cloud`, abra um item e confira os três scores `smartdocs.*`, a justificativa e a versão da rubrica no trace correspondente. Compare dois relatórios avaliados com `compare`; o comparador exige o mesmo dataset, versão das métricas, versões das rubricas e modelo avaliador:

```powershell
docker compose exec -T backend python -m app.evaluation.cli compare /app/app/evaluation/reports/antes.judged.json /app/app/evaluation/reports/depois.judged.json
```

## Calibração e revisão humana: etapa 3C

`calibrate` lê o relatório 3B da rubrica `1.0.3` e produz outro JSON **sem chamar o RAG ou o juiz**. Uma cópia integral da baseline sintética está versionada em `backend/app/evaluation/baselines/baseline_3b_v103.json`; o SHA-256 dessa cópia corresponde ao relatório local original. O bloco `semantic`, incluindo `model_score`, `model_behavior` e `model_reason`, permanece intacto; `calibrated_semantic` contém a nova decisão e `deterministic_correction` documenta cada regra aplicada. O dataset `synthetic_rag_v1.json` e seus critérios esperados permanecem iguais. O novo relatório registra dataset e hash, modelo RAG configurado, modelo avaliador, versões das rubricas, datas, IDs, origem da evidência e campos de revisão humana.

As regras da calibração têm versão `1.1.0` para faithfulness e abstenção; answer correctness mantém `1.0.3`:

| Situação | Critério calibrado |
| --- | --- |
| Informação ausente | Recusa explícita sem inventar o fato: 1; recusa misturada com afirmação não sustentada: 0,5; fato inventado: 0. Contexto insuficiente: `not_evaluable`. |
| Pedido de esclarecimento | Para pergunta ambígua, solicitar o sentido pretendido antes de responder: 1; esclarecimento parcial com suposição: 0,5; escolher um sentido sem solicitar esclarecimento: 0. |
| Resposta a múltiplas interpretações | Pode ser válida quando distingue e cobre as interpretações materiais com apoio nas fontes. Cobertura completa: 1; parcial: 0,5; escolha de um único sentido sem alternativas: 0. Sem julgamento humano ou evidência suficiente, `not_evaluable`. Indícios lexicais servem apenas para priorizar revisão. |
| Faithfulness | Exige os chunks completos efetivamente incluídos no contexto de geração. Fontes exibidas, páginas reconstruídas e ausência de evidência não comprovam esse contexto: `not_evaluable`, score `null`. |

**Diagnóstico da baseline:** `aur-06` e `bor-05` tratam informação ausente e se abstiveram. Em `aur-06`, a classificação bruta do juiz foi `answered`, enquanto sua justificativa descreveu recusa; a correção determinística da 3B permanece visível. `aur-07` e `bor-06` são ambíguos. `aur-07` cobre lexicalmente vários intervalos; isso é apenas candidato a resposta de múltiplas interpretações e depende de revisão humana. `bor-06` escolhe o horário limite de retirada e não cobre os prazos de disponibilidade dos compartimentos. `aur-05` é uma resposta parcial: informa a autonomia, mas não explica como ligar. Não há prova suficiente para afirmar que qualquer uma dessas respostas foi fundamentada no **contexto usado na geração**. Os 18 scores de faithfulness da 3B são preservados como histórico, e a decisão calibrada fica não avaliável. As duas respostas ambíguas também ficam não avaliáveis até revisão humana; a média dos demais casos de abstenção não deve ser lida como melhora do RAG.

```powershell
docker compose exec -T backend python -m app.evaluation.cli calibrate /app/app/evaluation/baselines/baseline_3b_v103.json --output /app/app/evaluation/reports/baseline-3c-v110.json
docker compose exec -T backend python -m app.evaluation.cli compare-rubrics /app/app/evaluation/baselines/baseline_3b_v103.json /app/app/evaluation/reports/baseline-3c-v110.json
```

O arquivo versionado `backend/app/evaluation/human_review_baseline_v1.json` contém os 18 casos, perguntas e respostas sintéticas, decisões originais e calibradas, justificativas, campo `human` e `observations`. **Todas as decisões humanas estão em branco.** Um revisor preenche, para cada critério que revisar, `status="scored"` e `score` entre 0 e 1, ou `status="not_evaluable"` e `score=null`; adiciona o motivo em `observations`. Um campo em branco é ignorado. Para produzir novo formulário para outra execução:

```powershell
docker compose exec -T backend python -m app.evaluation.cli review-template /app/app/evaluation/reports/baseline-3c-v110.json
```

Depois da edição humana, compare com as decisões calibradas:

```powershell
docker compose exec -T backend python -m app.evaluation.cli review-compare /app/app/evaluation/reports/baseline-3c-v110.json /app/app/evaluation/human_review_baseline_v1.json
```

O relatório comparado guarda as decisões humanas por caso e compara sua concordância com **ambas** as versões automáticas: `original_summary` (3B) e `summary` (3C). Cada bloco traz concordância de status, concordância de score com tolerância de 0,1, divergências e contagens `both_not_evaluable`. Campos não revisados não entram no denominador; quando ambos são não avaliáveis, há concordância de status, mas nenhuma comparação numérica. Não há publicação automática no Langfuse. Para comparar duas execuções avaliadas pela mesma rubrica, use `compare`; para comparar a rubrica 3B com a calibração 3C **da mesma execução**, use `compare-rubrics` e examine as mudanças de avaliabilidade caso a caso.

## Contexto real da generation: etapa 3D

Na busca vetorial, `search_similar_chunks_pgvector()` retorna candidatos por distância cosseno. `retrieve_context()` deduplica e limita candidatos; `grade_retrieved_chunks()` pode filtrá-los ou aplicar fallback. `_build_answer_context()` limita quantidade e tamanho dos chunks e formata o campo `state["context"]`. `generate_answer()` insere esse campo no prompt e chama `invoke_generation()` imediatamente antes de `llm.invoke()`. Fontes formatadas para a resposta podem ter um filtro de exibição adicional e **não** provam quais trechos entraram no prompt.

A captura opcional atua nesse limite de chamada, dentro de `invoke_generation()`. Extrai do **prompt efetivamente enviado** o bloco `Contexto`, sem reconstruir texto a partir de páginas. Cada registro contém ID do caso e documento, nome e índice da generation, ordem e IDs dos chunks, página, conteúdo após truncamento, texto exato do contexto, SHA-256 do contexto e hash do prompt. O conteúdo é validado contra o fixture sintético versionado antes de ser disponibilizado ao juiz. Chamadas de reescrita ou classificação têm registros separados, sem contexto de resposta. Se faltar contexto, a captura falhar, o hash divergir ou não houver vínculo com a generation concluída, Faithfulness é `not_evaluable` com score `null`.

**Privacidade:** `--capture-context` está desligado por padrão, exige documento registrado com status `evaluation` e caso do dataset sintético, e é recusado junto com `--publish`. O endpoint `/chat/ask` não entra no escopo de captura. O resultado exportado pelo Experiment Runner em `--publish` omite prévias textuais de fontes e qualquer registro de contexto. O relatório local com textos sintéticos fica em `backend/app/evaluation/reports/`, ignorado pelo Git. Não envie esse relatório ao Cloud manualmente.

```powershell
docker compose exec -T backend python -m app.evaluation.cli run --capture-context --run-name baseline-3d-captured --report /app/app/evaluation/reports/baseline-3d-captured.json
docker compose exec -T backend python -m app.evaluation.cli judge /app/app/evaluation/reports/baseline-3d-captured.json --output /app/app/evaluation/reports/baseline-3d-judged.json
docker compose exec -T backend python -m app.evaluation.cli calibrate /app/app/evaluation/reports/baseline-3d-judged.json --output /app/app/evaluation/reports/baseline-3d-calibrated.json
```

A rubrica Faithfulness `1.2.0` usa apenas o contexto capturado e seus identificadores; answer correctness segue `1.0.3`. A calibração da abstenção continua `1.1.0`, produzindo relatório de calibração `1.2.0` para essa nova metodologia. As baselines 3B e 3C continuam intactas. **Não compare numericamente a média Faithfulness 3B (fontes reconstruídas), 3C (`null`) e 3D (contexto real) como se medissem a mesma evidência.** Compare cobertura de casos avaliáveis, proveniência, decisões por caso e revisões humanas. Custo permanece `null` se o provider não o informar; latência e tokens de RAG e juiz ficam separados nos relatórios.

Na execução local `baseline-3d-captured`, 18/18 casos concluíram e 18/18 contextos foram verificados (13 com um chunk e 5 com dois). O RAG teve latência média de 14,06 s e reportou 33.009 tokens. O juiz realizou 50 chamadas, com latência média de 1,305 s por chamada, e reportou 35.144 tokens. Custo informado pelo provider: `null`. Faithfulness `1.2.0` avaliou 18 casos, média 0,972: `aur-05` recebeu 0,5 e os demais 17 receberam 1. O resumo **sem conteúdo textual** está versionado em `backend/app/evaluation/baselines/baseline_3d_summary.json`; os relatórios completos com contexto sintético ficam apenas no diretório local ignorado pelo Git. Esses scores continuam sujeitos a erro do juiz e devem ser examinados caso a caso.

A publicação continua disponível com `run --publish` e `judge --publish`, mas essa execução não contém texto de contexto e Faithfulness permanece não avaliável. Scores locais de Faithfulness com contexto capturado não têm trace remoto para associação e não são publicados automaticamente.

## Diagnóstico dirigido da recuperação (Etapa 4B.1)

O [relatório técnico 4B.1](rag-retrieval-diagnosis-4b1.md) localiza a primeira perda de evidência em `aur-05` e `bor-06`. Para repetir apenas esses casos sintéticos, sem juiz e sem publicação:

```bash
docker compose exec -T backend python -m app.evaluation.cli run --case-id aur-05 --case-id bor-06 --capture-context --diagnose-retrieval --run-name diagnosis-4b1 --report /app/app/evaluation/reports/diagnosis-4b1.json
```

`--case-id` é repetível e não altera o padrão da CLI. `--diagnose-retrieval` exige `--capture-context` e recusa `--publish`. A trilha A–F só é ativada para casos do dataset sintético com documento registrado como `evaluation`; o endpoint normal não captura texto. `retrieval_diagnostics` contém apenas identificadores, páginas, distâncias cosseno, decisões e parâmetros. O contexto sintético exato permanece em `generation_evidence` no relatório local ignorado pelo Git.

## Correção dirigida da deduplicação (Etapa 4B.2)

O [relatório 4B.2](rag-dedup-evaluation-4b2.md) compara `aur-05` antes e depois da correção do índice `0`, incluindo duas execuções novas com contexto exato, controles factuais e de abstenção, scores semânticos, latência e tokens. Para reproduzir apenas o caso principal localmente:

```bash
docker compose exec -T backend python -m app.evaluation.cli run --case-id aur-05 --capture-context --diagnose-retrieval --report /app/app/evaluation/reports/aur-05-local.json
docker compose exec -T backend python -m app.evaluation.cli judge /app/app/evaluation/reports/aur-05-local.json --concurrency 1
```

Os comandos não publicam dados no Langfuse. As baselines e os relatórios anteriores permanecem intactos.

## Auditoria offline das decisões de abstenção (Etapa 4B.3)

O [relatório técnico 4B.3](evaluation-audit-4b3.md) descreve os conflitos entre `model_score`, `model_behavior`, detector lexical e score final, com foco em `aur-06` e `bor-05`. A regra de decisão `2.0.0` preserva a decisão original e encaminha conflitos para revisão humana com `score=null`. Para auditar um relatório sintético já julgado, sem chamadas pagas:

```bash
docker compose exec -T backend python -m app.evaluation.cli audit-decisions /app/app/evaluation/reports/baseline-3d-judged.json
```

O arquivo `.audited.json` é local e acrescenta `decision_audit`; os campos `semantic` e `calibrated_semantic` históricos permanecem intactos. A rubrica do juiz não foi alterada, e nenhuma avaliação é publicada automaticamente.

## Regressão completa pós-deduplicação (Etapa 4B.4)

O [relatório de regressão 4B.4](rag-regression-4b4.md) compara os 18 casos da baseline 3D com uma única execução completa após a correção do índice `0`. Ele separa as rubricas equivalentes da calibração 1.1.0 e da regra de decisão 2.0.0, lista mudanças de contexto, respostas, latência e tokens por caso, e mantém os JSON completos apenas no diretório local ignorado pelo Git. Nenhum dado foi publicado no Langfuse.

## Revisão humana preparada (Etapa 4C)

O [relatório de revisão 4C](human-review-4c.md) reúne `aur-07`, `bor-05` e `bor-06` com resposta 4B.4, contexto exato, saída original do juiz, calibração e opções de política. O formulário local `backend/app/evaluation/reports/regression-4b4.review.json` foi gerado a partir da execução 4B.4 com **todas as decisões humanas em branco**. Consulte o relatório antes de preencher `human.abstention_correctness` e compare depois com `review-compare`. Nenhuma chamada paga ou publicação é necessária.
