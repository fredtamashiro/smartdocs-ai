# Etapa 4A — Diagnóstico das falhas do RAG

## Escopo e evidências

Análise somente de leitura da execução local `baseline-3d-captured` e dos relatórios `baseline-3d-judged.json` e `baseline-3d-calibrated.json`. Dataset sintético `smartdocs-synthetic-rag` versão `1.0.0`, SHA-256 `491e84f6673b5514361cd4211d1f59a114aed8d44ff321b243bc368ed521e2c9`. RAG configurado com `gpt-5-mini`; juiz `gpt-4.1-mini`. O contexto de geração foi capturado diretamente no limite de `invoke_generation()` e verificado contra o fixture. Nenhum modelo foi chamado para esta análise. Nenhum dado foi publicado no Langfuse.

Os relatórios completos de 3D são artefatos locais em `backend/app/evaluation/reports/`; o resumo sem conteúdo textual está versionado em `backend/app/evaluation/baselines/baseline_3d_summary.json`. As baselines 3B e 3C não foram alteradas. A execução 3D gerou novas respostas, portanto diferenças em relação à 3B não isolam o efeito da metodologia do juiz.

## Caminho dos chunks

1. `search_similar_chunks_pgvector()` consulta `smartdocs.embeddings` e `smartdocs.enriched_chunks`, ordenando pela **distância cosseno** (`<=>`; menor é melhor). Cada consulta retorna até `k=4` candidatos.
2. `retrieve_context()` executa as consultas, deduplica por documento e índice de chunk, ordena por distância e limita a `max_chunks_to_grade=3`; só prossegue quando a menor distância respeita `max_relevance_score=1.2`.
3. `grade_retrieved_chunks()` pode filtrar candidatos com o relevance grader, ignorá-lo para alta confiança ou usar fallback. `_build_answer_context()` usa no máximo `max_answer_context_chunks=2`, com até `max_answer_context_chars_per_chunk=900` caracteres por chunk na configuração efetiva do container analisado.
4. `generate_answer()` insere `state["context"]` no prompt enviado a `llm.invoke()`. `format_sources()` aplica outro filtro para **exibição**; suas fontes não são equivalentes ao conjunto inicial recuperado nem, necessariamente, ao contexto do prompt.

Os relatórios 3D preservam o contexto final e os chunks usados na generation. Não preservam a lista completa de candidatos antes e depois do grader. Assim, é possível afirmar quando um fato **não chegou ao prompt**, mas não identificar nesta execução se foi perdido na busca, na deduplicação, no grader ou no limite do contexto.

## `aur-05` — pergunta com duas partes

**Pergunta:** “Como ligar a estação e por quanto tempo ela funciona com bateria?” **Esperado:** pressionar **INICIAR por 3 segundos** (documento Aurora, p. 1) e autonomia nominal de **8 horas** (p. 2). A pergunta é respondível.

**Resposta gerada:** “Não há instruções no contexto sobre como ligar a estação (p. 2).” Em seguida informa bateria de 12 Ah, autonomia de 8 horas e recarga por USB-C em cerca de 4 horas, citando p. 2.

**Contexto realmente enviado:** apenas o chunk `ea5b34a6-ff57-5ef0-af7d-39d634087a5b`, p. 2, posição 1, SHA-256 do contexto `0fbed4bea547918496771220e2a20c46e695410c7f5ec79d93afefc2470df167`:

> A Estação Aurora usa bateria de 12 Ah e tem autonomia nominal de 8 horas. A recarga é feita por USB-C e dura aproximadamente 4 horas.

A p. 1 existe no fixture e contém “Para ligar, pressione INICIAR por 3 segundos”, mas **não entrou no prompt final**. A única fonte exibida foi p. 2. A execução levou **16,847 s** e reportou **2.306 tokens**; custo do provider indisponível.

| Avaliador | Resultado | Justificativa registrada |
| --- | --- | --- |
| Answer Correctness `1.0.3` | **0,5** | A resposta acertou 8 horas, mas omitiu INICIAR por 3 segundos. |
| Faithfulness `1.2.0` | **0,5** | O juiz aceitou os fatos da bateria e questionou a afirmação de que o contexto não traz instruções para ligar. |
| Abstention `1.0.3` / calibrada `1.1.0` | **0 / 0** | Uma parte respondível da pergunta ficou sem resposta. |

**Confirmado:** contexto final incompleto para a pergunta; resposta parcial em relação ao documento completo; nenhum fato da p. 1 foi disponibilizado ao gerador. **Hipóteses:** p. 1 pode não ter sido recuperada, pode ter sido filtrada pelo grader ou pode ter sido preterida por ordenação/limite de chunks. Os dados atuais não distinguem essas possibilidades. **Ponto de rubrica:** o score Faithfulness 0,5 é contestável: a frase “não há instruções no contexto” descreve corretamente o contexto capturado, que contém somente p. 2. Isso pede revisão humana; não prova uma afirmação sem suporte.

**Classificação:** contexto incompleto **confirmado**; recuperação inadequada e seleção insuficiente de chunks **hipóteses**; falha de geração como causa primária **não sustentada**, pois o modelo respondeu corretamente sobre o conteúdo que recebeu; problema de avaliação Faithfulness **plausível**.

## `aur-07` — “intervalo” ambíguo

**Pergunta:** “Qual é o intervalo da Estação Aurora?” O dataset 1.0.0 marca `answerable=false`, com expectativa de abstenção ou esclarecimento. A rubrica 3C também admite uma resposta que distinga e cubra interpretações materiais, mediante revisão humana.

**Resposta gerada:** temperatura a cada **5 minutos**, umidade a cada **10 minutos**, retenção dos dados por **30 dias** (p. 3). Acrescenta que, se “intervalo” significar medição, os valores são 5 e 10 minutos, e ressalva que outro significado não está especificado no contexto.

**Contexto realmente enviado:** apenas o chunk `3862fdec-e680-505b-9f7a-5b0f48179ac2`, p. 3, posição 1, hash `00d788981b8f08c54d951f616329d312eeb5c44c779c0d82377ef9ecce1de647`:

> A Estação Aurora mede temperatura a cada 5 minutos e umidade a cada 10 minutos. Os dados ficam armazenados por 30 dias.

A fonte exibida foi p. 3; os números da resposta estão nessa página. A execução levou **20,912 s** e reportou **2.350 tokens**; custo indisponível.

| Avaliador | Resultado | Justificativa registrada |
| --- | --- | --- |
| Answer Correctness `1.0.3` | **Não avaliável** | Não há resposta factual única de referência. |
| Faithfulness `1.2.0` | **1** | O juiz considerou as afirmações sustentadas pelo contexto da p. 3. |
| Abstention `1.0.3` | **0** | A regra antiga penaliza responder a pergunta marcada `answerable=false`, mesmo reconhecendo múltiplos sentidos. |
| Abstention calibrada `1.1.0` | **Não avaliável** | É necessária revisão humana sobre cobertura suficiente das interpretações; a detecção lexical de três sentidos é só indício. |

**Confirmado:** pergunta ambígua; resposta cobre três informações temporais da p. 3 e cita essa fonte; não há indício de afirmação sem suporte nesses três fatos. **Hipótese:** essa cobertura pode ser útil o bastante para dispensar esclarecimento, mas não cobre necessariamente todos os sentidos plausíveis de “intervalo” no manual (por exemplo, frequência de limpeza na p. 5). A expectativa do dataset não foi alterada. **Classificação:** interpretação de ambiguidade e problema da rubrica antiga **confirmados**; erro de recuperação, seleção ou geração **não demonstrado**.

## `bor-06` — “prazo” sem objeto definido

**Pergunta:** “Qual é o prazo do Armário Boreal?” O dataset 1.0.0 marca `answerable=false`; não especifica retirada, permanência em compartimento ou outro prazo.

**Resposta gerada:** prazo para retirada **até as 18 horas** (p. 3) e entregas terça e quinta às **9 horas** (p. 3). Não solicita esclarecimento nem menciona disponibilidade por compartimento.

**Contexto realmente enviado:** apenas o chunk `9c1809cf-479b-54e7-8f7c-2cc9e4a489c2`, p. 3, posição 1, hash `54b2849046aac3630d1455d1bd5e9e2141f408a81f73bf7991bf2e0f7fd0837e`:

> As entregas no Armário Boreal ocorrem terça-feira e quinta-feira às 9 horas. A retirada é permitida somente até as 18 horas.

O fixture também contém na p. 4 prazos de disponibilidade de **48 horas em A** e **24 horas em B**, que **não chegaram ao prompt**. A única fonte exibida foi p. 3. A execução levou **21,658 s** e reportou **2.493 tokens**; custo indisponível.

| Avaliador | Resultado | Justificativa registrada |
| --- | --- | --- |
| Answer Correctness `1.0.3` | **Não avaliável** | Pergunta sem resposta única de referência. |
| Faithfulness `1.2.0` | **1** | As afirmações sobre retirada e entregas são sustentadas pela p. 3. |
| Abstention `1.0.3` | **0** | Respondeu a uma pergunta marcada não respondível. |
| Abstention calibrada `1.1.0` | **Não avaliável** | A decisão sobre suficiência das interpretações exige revisão humana; o indício lexical cobre apenas uma das três interpretações registradas para revisão. |

**Confirmado:** pergunta ambígua; a resposta selecionou um sentido e trouxe fatos sustentados pela p. 3; o contexto final não incluiu a p. 4. **Hipóteses:** a p. 4 pode não ter sido recuperada ou pode ter sido descartada antes da geração; a omissão reforçou a escolha por retirada, mas não comprova causalidade. **Classificação:** interpretação de ambiguidade e contexto incompleto para um sentido plausível **confirmados**; estágio exato da perda e defeito de recuperação **indeterminados**. Faithfulness 1 não implica que a resposta tenha resolvido a pergunta ambígua.

## Melhorias candidatas e prioridade

| Prioridade | Problema e alternativas para 4B | Impacto e risco | Intervenção mínima recomendada |
| --- | --- | --- | --- |
| **P0 — calibração** | Revisar humanamente `aur-05` (Faithfulness) e `aur-07`/`bor-06` (abstenção). Refinar a rubrica para distinguir afirmação sobre ausência **no contexto recebido** de afirmação sobre ausência **no documento inteiro**. | Impacto somente no avaliador/dataset de teste; risco de redefinir expectativa sem versionar e mascarar regressões. | Preencher a revisão humana antes de qualquer mudança de RAG. Se a expectativa mudar, criar nova versão do dataset e manter `synthetic_rag_v1`. |
| **P1 — resposta multipartes (`aur-05`)** | Registrar IDs e distâncias dos candidatos antes/depois do grader **somente em avaliação sintética**. Se p. 1 já estiver nos candidatos, testar seleção que preserve evidência de cada subpergunta ou ajuste condicional do limite de contexto. Se não estiver, testar decomposição da pergunta em consultas por parte. | Diagnóstico baixo; alteração de seleção ou consulta médio. Aumento de latência/tokens, perda de precisão e respostas longas são riscos. | Primeiro localizar a etapa de perda; depois alterar só a etapa responsável, sob configuração de experimento. Não aumentar o limite global de 2 chunks sem essa evidência. |
| **P2 — `bor-06`** | Após decisão humana, comparar pedido de esclarecimento com resposta que separa prazo de retirada e permanência em A/B. Esta segunda opção também precisaria disponibilizar p. 4 ao gerador. | Impacto pequeno a médio no fluxo de perguntas; risco de bloquear perguntas claras, recuperar contexto irrelevante ou aumentar latência/tokens. | Se a revisão confirmar falha, testar clarificação direcionada para “prazo” sem objeto definido antes de ampliar a busca. |
| **P3 — `aur-07`** | Revisar se a resposta que separa medição de temperatura, umidade e retenção já satisfaz a necessidade; se não, comparar esclarecimento prévio com enumeração mais explícita dos sentidos. | Impacto pequeno no formato da resposta ou médio se houver nova etapa de decisão; risco de respostas longas e de penalizar respostas úteis por rubrica estreita. | Não alterar o RAG antes da decisão humana; versionar qualquer mudança de expectativa. |

Nenhuma alternativa foi implementada nesta etapa.

## Plano de validação da Etapa 4B

1. **Congelar o ponto de partida:** guardar dataset `synthetic_rag_v1`, hashes dos contextos, modelos, rubricas e relatórios 3B/3C/3D. Não comparar médias Faithfulness 3B, 3C e 3D como se usassem a mesma evidência. Reexecutar baseline e candidato com a metodologia de captura 3D e versões de rubrica iguais.
2. **Completar o diagnóstico de `aur-05`:** em execução sintética controlada, medir IDs, páginas, distâncias cosseno e contagens após busca, deduplicação, grader e seleção final; comparar com o contexto capturado. Isso determina se a intervenção é na recuperação ou no limite/seleção. Distâncias não devem ser tratadas como scores de similaridade.
3. **Criar casos independentes:** versionar outro fixture inteiramente fictício, separado de Aurora/Boreal, com pelo menos um documento que distribua instrução de ligar e autonomia em chunks distintos, outro com prazo de retirada versus prazo de permanência, e controles factuais, ausentes e de múltiplos sentidos. Propor 6–8 perguntas sem copiar frases do dataset atual; definir expectativas e critérios antes da execução.
4. **Aplicar uma mudança por experimento:** usar a mesma configuração do RAG para controle e candidato, exceto pela intervenção em teste. Como a geração atual pode variar, repetir os três casos alvo e os novos casos em pelo menos três execuções e depois rodar os 18 casos existentes. Não substituir a baseline preservada.
5. **Critérios de aceitação:** `aur-05` deve ter as duas evidências (p. 1 e p. 2) no contexto final e responder ambos os fatos; Answer Correctness e Faithfulness devem ser revisados junto com as justificativas. Para ambiguidades, só pontuar Abstention Correctness após a decisão humana versionada: esclarecimento ou cobertura de sentidos conforme o critério aprovado. Verificar também citações e ausência de alegações sem suporte.
6. **Regressão e eficiência:** comparar por caso Answer Correctness, Faithfulness `1.2.0` com contexto verificado, Abstention Correctness calibrada `1.1.0`, número de `not_evaluable`, latência por pergunta e distribuição, tokens RAG e juiz e custo **somente quando informado de forma confiável pelo provider**. A referência 3D é 14,06 s médios e 33.009 tokens RAG em 18 casos; qualquer aumento deve ser atribuído à intervenção e avaliado junto aos ganhos. Inspecionar especialmente respostas factuais simples, ausências e citações para detectar regressão.

## Limites do diagnóstico

Há um único conjunto de saídas da execução 3D; não há série de repetições nem contrafactual com a mesma geração. O relatório não contém candidatos intermediários do retrieval/grader nem custo monetário do provider. Scores LLM-as-a-Judge são opiniões do avaliador, não provas de correção. `aur-07` e `bor-06` continuam pendentes de decisão humana, e a justificativa Faithfulness de `aur-05` deve ser revista antes de ser tratada como falha confirmada de fundamentação.
