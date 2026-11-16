# Etapa 4C — Revisão humana e política proposta para ambiguidades

**Estado:** material preparado para decisão humana; **nenhuma decisão humana foi preenchida**. Todos os trechos abaixo pertencem aos dois documentos sintéticos do dataset `synthetic_rag_v1` 1.0.0 (SHA-256 `491e84f6673b5514361cd4211d1f59a114aed8d44ff321b243bc368ed521e2c9`). Esta revisão usa a **única execução 4B.4** (`regression-4b4-captured`) e seus relatórios `regression-4b4-judged.json` e `regression-4b4-calibrated.json`. O contexto é o capturado na chamada de geração, versão 3D `1.0.0`, e foi verificado contra o fixture. A rubrica de Faithfulness é `1.2.0`, a calibração de abstenção é `1.1.0` e a regra de decisão é `2.0.0`.

## O que o revisor deve decidir

Para cada caso, leia a pergunta, a resposta e **somente o contexto que chegou ao LLM** antes de julgar a fundamentação. Depois consulte o documento sintético completo quando a decisão envolver suficiência da recuperação ou cobertura de interpretações. Registre separadamente (a) comportamento da resposta, (b) adequação ao pedido e (c) se uma afirmação sobre o **documento inteiro** é justificável a partir da evidência. O score do juiz é uma opinião registrada, não uma decisão humana. Os campos de decisão abaixo permanecem deliberadamente vazios.

### `aur-07` — “intervalo” da Estação Aurora

**Pergunta:** “Qual é o intervalo da Estação Aurora?”

**Resposta efetiva 4B.4:**

> A Estação Aurora mede temperatura a cada 5 minutos e umidade a cada 10 minutos (p. 3).
>
> Os dados ficam armazenados por 30 dias (p. 3).

**Esperado no dataset:** `answerable=false`, sem resposta factual única. O termo “intervalo” pode se referir a períodos de medição ou a outros períodos no manual. A baseline 3D explicitava a possibilidade de outro significado; a resposta 4B.4 apresenta três períodos sem ressalva. O dataset **não foi alterado**.

**Contexto efetivamente enviado ao LLM:** um chunk, p. 3, índice 2, ID `3862fdec-e680-505b-9f7a-5b0f48179ac2`; SHA-256 do contexto `00d788981b8f08c54d951f616329d312eeb5c44c779c0d82377ef9ecce1de647`.

> A Estação Aurora mede temperatura a cada 5 minutos e umidade a cada 10 minutos. Os dados ficam armazenados por 30 dias.

**Juiz e calibração:** Answer Correctness `not_evaluable` porque não há resposta factual única de referência. Faithfulness: `model_score=1`, score final e calibrado **1**; justificativa: os três períodos afirmados constam no chunk da p. 3. Abstention Correctness: `model_score=0`, `model_behavior=answered`; o juiz justificou que a resposta não esclarece qual “intervalo” foi solicitado. A regra 2.0.0 produziu `not_evaluable`, score `null`, motivo `ambiguous_answer_requires_human_review`; a calibração 1.1.0 também manteve `not_evaluable`. O score de Faithfulness **não decide** se a ambiguidade foi tratada adequadamente. O documento sintético contém ainda outros períodos fora deste contexto, como manutenção na p. 5; sua relevância para esta pergunta precisa de julgamento humano.

**Opções de política para a pergunta ambígua — selecionar uma após revisão:**

- [ ] Solicitar esclarecimento antes de responder.
- [ ] Responder todas as interpretações materiais relevantes, distinguindo cada sentido e citando a fonte.
- [ ] Responder uma interpretação **explicitada como hipótese**, convidando o usuário a especificar outro sentido.
- [ ] Considerar a resposta inadequada.

**Questões para o revisor:** os três períodos da p. 3 cobrem as interpretações materiais? A falta de ressalva torna a resposta inadequada? Um pedido de esclarecimento seria necessário ou excessivo?

**Decisão humana:** `status` ______ · `score` ______ · comportamento ______ · observações ____________________________________

### `bor-05` — e-mail de suporte ausente

**Pergunta:** “Qual é o endereço de e-mail do suporte do Armário Boreal?”

**Resposta efetiva 4B.4:**

> Não há endereço de e‑mail do suporte do Armário Boreal nos documentos fornecidos (p. 1 e 3).

**Esperado no dataset:** `answerable=false`; não inventar um endereço. Uma abstenção limitada ao contexto disponível é suficiente para não alucinar. A frase “nos documentos fornecidos” tem alcance maior que “no contexto recuperado”; o revisor deve julgar se esse alcance é justificável. A resposta da baseline 3D dizia que o endereço não estava **no contexto**.

**Contexto efetivamente enviado ao LLM:** dois chunks, nessa ordem; SHA-256 `1864686504ac9da9cc86283907fcef4a049dd0c2a3220eeeb16197d91ce1e2c9`.

1. P. 1, índice 0, ID `ce125b0e-cb8d-57b3-a016-c23ca360d832`: “O Armário Boreal é um equipamento fictício com dois compartimentos. O compartimento A comporta 6 caixas; o compartimento B comporta 4 caixas.”
2. P. 3, índice 2, ID `9c1809cf-479b-54e7-8f7c-2cc9e4a489c2`: “As entregas no Armário Boreal ocorrem terça-feira e quinta-feira às 9 horas. A retirada é permitida somente até as 18 horas.”

O relatório também lista p. 5 entre as **fontes exibidas**, mas essa página **não estava no contexto da generation**. Não a use como prova de fundamentação da resposta.

**Juiz e calibração:** Answer Correctness `not_evaluable`, pois não há endereço esperado. Faithfulness: `model_score=1`, score final e calibrado **1**; a justificativa observa corretamente que os dois chunks não trazem e-mail, mas extrapola ao aceitar a frase “nos documentos fornecidos”. Abstention Correctness: o juiz devolveu **`model_score=1` e `model_behavior=answered`**, apesar de justificar que a resposta reconhece a ausência. A regra 2.0.0 registrou `judge_score_behavior_conflict_requires_human_review` e produziu `not_evaluable`, score `null`; a calibração 1.1.0 manteve `not_evaluable`. O detector lexical 3A também não reconheceu esta formulação; isso não prova que houve resposta factual.

**Questões para o revisor:** a resposta efetivamente se absteve? O alcance “nos documentos fornecidos” deve ser aceito, restringido a “no contexto”, ou marcado como afirmação sem suporte? A citação de p. 1 e 3 sustenta uma ausência no documento inteiro?

**Decisão humana:** `status` ______ · `score` ______ · comportamento ______ · observações ____________________________________

### `bor-06` — “prazo” do Armário Boreal

**Pergunta:** “Qual é o prazo do Armário Boreal?”

**Resposta efetiva 4B.4:**

> A retirada no Armário Boreal é permitida somente até as 18 horas (p. 3).
>
> - Entregas ocorrem terça-feira e quinta-feira às 9 horas (p. 3).

**Esperado no dataset:** `answerable=false` por ambiguidade do objeto de “prazo”. O usuário pode querer horário limite de retirada ou duração da disponibilidade no compartimento. O fixture contém 48 horas em A e 24 horas em B na p. 4, mas essa página **não chegou ao LLM**; a Etapa 4B.1 a localizou em quarto lugar, abaixo de `max_chunks_to_grade=3`. A resposta atual assume o sentido de retirada sem explicitar essa escolha nem pedir esclarecimento.

**Contexto efetivamente enviado ao LLM:** um chunk, p. 3, índice 2, ID `9c1809cf-479b-54e7-8f7c-2cc9e4a489c2`; SHA-256 `54b2849046aac3630d1455d1bd5e9e2141f408a81f73bf7991bf2e0f7fd0837e`.

> As entregas no Armário Boreal ocorrem terça-feira e quinta-feira às 9 horas. A retirada é permitida somente até as 18 horas.

**Juiz e calibração:** Answer Correctness `not_evaluable`, sem resposta única de referência. Faithfulness: `model_score=1`, score final e calibrado **1**; os horários citados constam no chunk da p. 3. Abstention Correctness: `model_score=0`, `model_behavior=answered`; o juiz disse que a resposta informa horários relacionados, mas não resolve o prazo sem objeto definido. A regra 2.0.0 produziu `not_evaluable`, score `null`, motivo `ambiguous_answer_requires_human_review`; a calibração 1.1.0 também manteve `not_evaluable`. Fundamentação dos horários não equivale à cobertura dos sentidos plausíveis de “prazo”.

**Opções de política para a pergunta ambígua — selecionar uma após revisão:**

- [ ] Solicitar esclarecimento antes de responder.
- [ ] Responder todas as interpretações materiais relevantes, distinguindo horário de retirada de disponibilidade em A/B e citando as fontes.
- [ ] Responder uma interpretação **explicitada como hipótese**, convidando o usuário a especificar outro sentido.
- [ ] Considerar a resposta inadequada.

**Questões para o revisor:** uma resposta sobre retirada, se explicitamente condicionada, seria aceitável? A resposta atual escolhe o sentido com transparência suficiente? A ausência da p. 4 impede considerar a resposta abrangente?

**Decisão humana:** `status` ______ · `score` ______ · comportamento ______ · observações ____________________________________

## Política geral proposta — pendente de aprovação humana

1. **Informação ausente:** quando o fato solicitado não aparece no contexto confiável, declarar a limitação sem inventar o fato. Distinguir “não encontrei no contexto usado” de “não existe no documento inteiro”; a segunda afirmação exige verificação abrangente. Citação de páginas isoladas não comprova ausência global. Se a resposta trouxer ao mesmo tempo uma recusa e um fato não sustentado, tratar como mista e revisar.
2. **Pergunta ambígua:** identificar sentidos materialmente diferentes. Preferir pedir esclarecimento quando a escolha muda a resposta e não há contexto suficiente para cobrir os sentidos com segurança. Uma resposta que cubra todos os sentidos relevantes pode ser útil se nomear cada um e citar sua evidência. Responder apenas um sentido exige explicitar a hipótese e oferecer correção; a aceitabilidade desse caminho deve ser decidida antes de converter a política em score automático. Sem essa decisão, manter `not_evaluable`.
3. **Pergunta com múltiplas partes:** verificar cada parte separadamente, com evidência própria. Se uma parte não puder ser respondida, entregar a parte sustentada e indicar claramente a lacuna, sem declarar a informação inexistente em todo o documento. Não atribuir correção completa a uma resposta parcial.
4. **Contexto insuficiente:** não reconstruir páginas depois da geração como se tivessem sido fornecidas ao modelo. Restringir afirmações ao contexto real, solicitar esclarecimento ou abster-se conforme a pergunta. Para Faithfulness, evidência ausente ou incompleta implica `not_evaluable` e score `null`, não zero automático.

Esta proposta **não altera** a rubrica, o RAG nem os critérios `answerable` do dataset 1.0.0. Qualquer adoção posterior como regra automática deve ser versionada e testada contra casos sintéticos independentes e as baselines preservadas.

## Como registrar a decisão no formulário JSON atual

Foi gerado um formulário **novo e inteiramente em branco** para o run 4B.4: `backend/app/evaluation/reports/regression-4b4.review.json`. Ele contém os 18 casos porque `review-compare` exige o mesmo conjunto de IDs do relatório calibrado. **Preencha somente `aur-07`, `bor-05` e `bor-06`**; deixe os outros campos `human` com `status: null`, `score: null` e `observations: ""`. Não reutilize `human_review_baseline_v1.json`, que pertence a outro run.

Para cada um dos três casos, encontre `cases[]` pelo `case_id` e edite `human.abstention_correctness`:

```json
"human": {
  "abstention_correctness": {
    "status": null,
    "score": null,
    "observations": ""
  }
}
```

**Após a revisão humana**, use `status: "scored"` com `score` numérico entre 0 e 1, ou `status: "not_evaluable"` com `score: null`; descreva em `observations` a interpretação escolhida e o motivo. O trecho acima mostra os valores **ainda vazios** e não representa uma decisão. Para questões de fundamentação em `bor-05`, o revisor também pode preencher `human.faithfulness` separadamente. O campo geral `cases[].observations` pode registrar a opção de política escolhida (esclarecimento, múltiplos sentidos, um sentido explicitado ou resposta inadequada). Não altere `automatic`, `question`, `answer`, IDs ou metadados do formulário.

Depois de preencher, compare com o relatório calibrado correspondente, sem chamadas pagas:

```bash
docker compose exec -T backend python -m app.evaluation.cli review-compare /app/app/evaluation/reports/regression-4b4-calibrated.json /app/app/evaluation/reports/regression-4b4.review.json --output /app/app/evaluation/reports/regression-4b4.reviewed.json
```

O comando compara a decisão humana com `calibrated_semantic` e `semantic` do mesmo run, preservando ambos. No formulário atual, a chave `automatic.stage3b` contém o veredito semântico **deste run 4B.4**, já sob a regra 2.0.0; o nome da chave é histórico e não significa que o relatório 3B foi reutilizado. A saída original do juiz está em `automatic.original_judge`. Os JSON com textos sintéticos permanecem locais e ignorados pelo Git; não os publique no Langfuse.
