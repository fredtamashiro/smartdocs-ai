# Etapa 4B.3 — Auditoria das regras de avaliação

## Fontes e método

Esta auditoria reprocessou **somente dados salvos**: baseline 3B versionada (`baseline_3b_v103.json`), baseline 3D local (`baseline-3d-judged.json`) e controles locais 4B.2 (`dedup-controls-4b2.judged.json`). Nenhum RAG, juiz ou serviço Cloud foi chamado. Os relatórios originais e os scores históricos permanecem intactos. Os novos resultados locais têm sufixo `.decision-audit.json` e acrescentam `decision_audit`; não substituem `semantic` nem `calibrated_semantic`.

Versões: rubrica do juiz para Answer Correctness **1.0.3**, Faithfulness com evidência real **1.2.0**, Abstention Correctness **1.0.3**; calibração 3C de abstenção **1.1.0**; regra de decisão auditada **2.0.0**. A rubrica textual do juiz não mudou. A versão 2.0.0 identifica apenas o pós-processamento, inclusive em futuros scores explicitamente publicados.

## Inventário das regras que alteravam resultados

| Camada | Regra anterior | Efeito |
| --- | --- | --- |
| Métricas 3A, `metrics.py` 1.0.1 | Procura frases literais normalizadas para `abstention_detected`; calcula `abstention_pass`, cobertura lexical e citação. | Não modifica diretamente `model_score`, mas alimentava a correção no juiz. Pode não reconhecer uma abstenção sem frase catalogada. Cobertura lexical não é correção factual. |
| Juiz, `judge.py` 1.0.3 | Para abstenção, transformava `model_behavior` em score 0, 0,5 ou 1; se o juiz dissesse `answered` com `model_score=1` em caso não respondível, o detector lexical podia mudar o comportamento para `abstained`. | Substituía `model_score` automaticamente. A mesma resposta podia receber 1 ou 0 conforme sua formulação lexical. `model_score`, `model_behavior` e `model_reason` eram mantidos, mas não havia versão separada da regra. |
| Calibração 3C, `calibration.py` 1.1.0 | Marca Faithfulness como não avaliável se a evidência é reconstruída/incompleta; em pergunta ambígua respondida, marca Abstention Correctness como não avaliável; mantém Answer Correctness; registra correções separadamente. | Preserva `semantic` original e escreve `calibrated_semantic`. A Etapa 3D considera completa apenas a evidência capturada na chamada de geração (Faithfulness 1.2.0). |

A rubrica 1.0.3 já diz que afirmar que o fato solicitado não está disponível é **abstenção**, mesmo com citação. O problema observado é de **classificação do comportamento pelo juiz**, agravado por **pós-processamento que atribuía 0 ou 1 diante de campos contraditórios**. A rubrica textual não precisa ser redefinida para estes exemplos. O detector lexical tem um falso negativo em `bor-05`; acrescentar apenas mais uma frase não resolveria o risco de respostas parciais ou de outras paráfrases.

## Casos principais

| Caso e execução | Pergunta, resposta e esperado | Saída original do juiz | Regra anterior e score final | Regra 2.0.0 |
| --- | --- | --- | --- | --- |
| `aur-06`, 3B | Pergunta sobre versão Bluetooth. Resposta: “Não há informação sobre a versão de Bluetooth ... nos documentos fornecidos”. Esperado: abstenção. | `model_score=1`, `model_behavior=answered`; justificativa afirma que a informação está ausente. | Detector lexical `true`; mudou comportamento para `abstained`, score final **1**. | Conflito entre score e comportamento; **not_evaluable**, score `null`, revisão humana. |
| `aur-06`, 3D e controle 4B.2 | Respostas novas também afirmam ausência de versão Bluetooth. Esperado: abstenção. | Juiz classificou `abstained`, `model_score=1`. | Detector `true`, sem correção necessária; score **1**. | **1**, sem correção. |
| `bor-05`, 3D | Pergunta pelo e-mail de suporte. Resposta: “O endereço ... não está presente no contexto fornecido”. Esperado: abstenção. | `model_score=1`, `model_behavior=answered`; justificativa reconhece ausência. | Detector `true`; mudou comportamento para `abstained`, score final **1**. | Conflito; **not_evaluable**, score `null`, revisão humana. |
| `bor-05`, controle 4B.2 | Mesma pergunta. Resposta: “Não há endereço de e-mail ... no contexto fornecido”. Esperado: abstenção. | `model_score=1`, `model_behavior=answered`; justificativa reconhece ausência. | Detector `false`; comportamento ficou `answered`, score final **0**. | Conflito; **not_evaluable**, score `null`, revisão humana. |

As respostas dos dois casos são sintéticas e indicam falta da informação solicitada. Ainda assim, a regra nova **não converte automaticamente** os conflitos em nota 1: a decisão do juiz também pode errar na justificativa, e frases de ausência podem aparecer em respostas parciais. O revisor humano deve confirmar se a resposta realmente se absteve, forneceu um fato inventado ou misturou os dois. Se concordar com a abstenção, pode registrar 1 na revisão humana; o score histórico continua visível.

## Nova regra de decisão 2.0.0

O pós-processamento calcula a pontuação que a rubrica exigiria para o comportamento informado, **sem tratá-la como verdade**. Quando `model_score` e esse comportamento concordam, mantém a decisão original. Quando discordam, produz `status=not_evaluable`, `score=null`, `human_review_required=true`, guarda os campos originais e registra o sinal lexical apenas como evidência de auditoria. Uma pergunta ambígua respondida ou parcialmente respondida também exige revisão humana, seguindo a calibração 1.1.0. `answered` em pergunta não respondível e score 0, `abstained`/`asked_clarification` e score 1, ou `mixed` e score 0,5 permanecem válidos quando os campos concordam. Ausência de resposta avaliável continua com score `null`.

Para respostas sintéticas de teste, foram cobertas recusa explícita, ausência no contexto, ausência no documento, fato inventado, pedido de esclarecimento, resposta parcial, campos contraditórios e resultado não avaliável. O detector lexical antigo permanece em `metrics.py` 1.0.1 para preservar comparabilidade histórica; ele não decide a nova nota semântica. O fluxo RAG de produção não foi alterado.

## Comparação offline com os mesmos dados

| Relatório | Casos | Decisões alteradas na visão auditada | IDs enviados à revisão humana |
| --- | ---: | ---: | --- |
| Baseline 3B | 18 | 4 | `aur-05`, `aur-06`, `aur-07`, `bor-06` |
| Baseline 3D | 18 | 3 | `aur-07`, `bor-05`, `bor-06` |
| Controles 4B.2 | 4 | 1 | `bor-05` |

`aur-05` da 3B tem `model_score=0` e `model_behavior=answered` para Abstention Correctness; essa contradição também passa a exigir revisão. `aur-07` e `bor-06` são ambíguos: a nova regra não infere nota 0 só porque houve resposta, em consonância com a 3C. As notas de Answer Correctness e Faithfulness não foram recalculadas. A lista acima **não muda as baselines**; é uma comparação de metodologia.

## Uso e revisão humana

```bash
docker compose exec -T backend python -m app.evaluation.cli audit-decisions /app/app/evaluation/baselines/baseline_3b_v103.json
docker compose exec -T backend python -m app.evaluation.cli audit-decisions /app/app/evaluation/reports/baseline-3d-judged.json
docker compose exec -T backend python -m app.evaluation.cli audit-decisions /app/app/evaluation/reports/dedup-controls-4b2.judged.json
```

Cada comando cria um `.audited.json` local. Compare `semantic.abstention_correctness` com `decision_audit.abstention_correctness`, leia `model_reason` e `deterministic_correction`, e registre para cada caso marcado `case_id`, decisão humana (`scored` com nota de 0 a 1, ou `not_evaluable` com nota `null`) e observações. O formulário e a comparação humana da Etapa 3C continuam disponíveis para **relatórios calibrados 3C**; eles ainda não comparam automaticamente a decisão humana com `decision_audit`. Não preencha decisões humanas com outro modelo.

**Limites:** a nova regra detecta **inconsistência**, não determina sozinha a verdade semântica. Pode aumentar o número de casos sem score até revisão humana. O detector lexical ainda pode ter falsos positivos e negativos nas métricas 3A, mas não controla mais o score semântico novo. Relatórios de versões diferentes não devem ser comparados como se usassem a mesma regra. Nenhum dado foi publicado no Langfuse nesta auditoria.
