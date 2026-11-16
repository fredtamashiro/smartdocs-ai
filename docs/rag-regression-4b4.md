# Etapa 4B.4 — Regressão completa do RAG

## Preparação e metodologia

Uma única execução completa do RAG atual percorreu os **18 casos únicos** de `synthetic_rag_v1`, versão `1.0.0`, SHA-256 `491e84f6673b5514361cd4211d1f59a114aed8d44ff321b243bc368ed521e2c9`. Os dois documentos sintéticos estavam registrados como `evaluation` no ambiente `development`. A execução usou o backend Docker, chamou diretamente o grafo de produção e foi salva em `backend/app/evaluation/reports/regression-4b4-captured.json`. Nenhum caso foi repetido nesta etapa, nenhuma avaliação foi publicada no Langfuse e as baselines anteriores permaneceram intactas.

Configuração efetiva: RAG `gpt-5-mini`, temperatura `1`; o provider reportou `gpt-5-mini-2025-08-07` nas generations de reescrita, grader e resposta. Embeddings `text-embedding-3-small`; multi query habilitada, até 2 consultas; busca com `k=4` por consulta; `max_chunks_to_grade=3`; grader batch habilitado, com opção de pular em alta confiança (distância ≤0,25 em pelo menos 2 chunks); limite de contexto de 2 chunks e 900 caracteres por chunk; distância cosseno máxima configurada `1,2`. Juiz `gpt-4.1-mini`; SDK Langfuse `5.2.0`. A captura 3D `1.0.0` verificou **18/18 contextos efetivamente enviados à generation**, vinculados ao fixture sintético. Todos os 18 casos produziram resposta sem erro.

O relatório foi avaliado localmente em `regression-4b4-judged.json` com Answer Correctness **1.0.3**, Faithfulness **1.2.0** e a rubrica base de Abstention Correctness **1.0.3**. `regression-4b4-calibrated.json` aplica a calibração de abstenção **1.1.0**. O juiz atual também aplica a regra de decisão **2.0.0** separadamente e preserva `model_score`, `model_behavior`, `model_reason` e `deterministic_correction`. Não houve chamadas ao RAG na avaliação semântica nem uso de documentos reais.

## Resultado agregado

| Métrica | Baseline 3D | Regressão 4B.4 | Interpretação |
| --- | ---: | ---: | --- |
| Casos concluídos / contextos verificados | 18/18 / 18/18 | 18/18 / 18/18 | Sem falha de execução ou captura. |
| Cobertura lexical média dos 14 respondíveis | 0,9167 | 0,9524 | Subiu com `aur-05`; cobertura lexical não mede correção factual. |
| Citações exigidas presentes | 3/3 | 3/3 | Sem perda detectada. |
| Answer Correctness 1.0.3 | 0,9643 (14 avaliáveis) | 1,0 (14 avaliáveis) | Só `aur-05` passou de 0,5 para 1. |
| Faithfulness 1.2.0 | 0,9722 (18 avaliáveis) | 1,0 (18 avaliáveis) | Só `aur-05` passou de 0,5 para 1; a justificativa antiga de 0,5 já era contestável. |
| Abstention Correctness 1.1.0, visão calibrada | 0,9375 (16 avaliáveis) | 1,0 (15 avaliáveis) | **Não comparar as médias como ganho**: a execução nova inclui a regra 2.0.0 antes da calibração e tem um caso adicional sem score. |
| Abstenção sob a **mesma regra 2.0.0** | 0,9333 (15 avaliáveis, baseline 3D reprocessada offline) | 1,0 (15 avaliáveis) | `aur-05` mudou de 0 para 1; `aur-07`, `bor-05`, `bor-06` ficam sem score em ambas. |
| Abstenção lexical 3A nos 4 casos esperados | 2/4 | 1/4 | A formulação nova de `bor-05` não foi reconhecida; isso não comprova piora do RAG. |
| Latência média RAG | 14,060 s | 16,717 s | +2,657 s (+18,9%); uma execução por versão não isola a causa. |
| Tokens RAG reportados | 33.009 | 31.936 | −1.073 (−3,3%); variação por resposta e chamadas internas. |
| Tokens juiz reportados | 35.144 | 35.411 | +267, em 50 chamadas com usage disponível em cada execução. |
| Custo monetário informado pelo provider | `null` | `null` | Não há base confiável para comparar dólares. |

## Comparação dos 18 casos

As páginas abaixo são os **chunks do contexto real da generation**, em ordem. `AC` é Answer Correctness 1.0.3; `F` é Faithfulness 1.2.0. `∅` significa não avaliável. Δ de latência em milissegundos e Δ de tokens são **4B.4 menos 3D**. As respostas completas e os IDs técnicos estão nos dois JSON locais; esta coluna resume os fatos ou a mudança de comportamento.

| Caso | Resposta 3D → 4B.4 | Páginas 3D → 4B.4 | AC | F | Δ latência | Δ tokens |
| --- | --- | --- | --- | --- | ---: | ---: |
| `aur-01` | INICIAR por 3 s e LED azul → mesmos fatos | 1 → 1 | 1→1 | 1→1 | +6.726 | +77 |
| `aur-02` | LED azul → mesmo fato | 1 → 1 | 1→1 | 1→1 | −554 | −148 |
| `aur-03` | Autonomia de 8 h → mesmo fato | 2 → 2 | 1→1 | 1→1 | +3.363 | −8 |
| `aur-04` | Medições a cada 5/10 min → mesmos fatos | 3 → 3 | 1→1 | 1→1 | −83 | −251 |
| `aur-05` | Dizia faltar instrução para ligar; só 8 h → **INICIAR por 3 s e 8 h**, com citações p. 1/2 | **2 → 2,1** | **0,5→1** | **0,5→1** | +3.772 | +16 |
| `aur-06` | Abstenção sobre Bluetooth → mesma abstenção, com páginas citadas diferentes | **2,3 → 2,1** | ∅→∅ | 1→1 | +6.488 | +164 |
| `aur-07` | Intervalos 5/10 min, retenção 30 dias e ressalva da ambiguidade → mesmos números, **sem a ressalva** | 3 → 3 | ∅→∅ | 1→1 | +2.804 | −131 |
| `aur-08` | Limpeza a cada 14 dias, sem água → mesmos fatos e citação | 5 → 5 | 1→1 | 1→1 | +2.988 | +338 |
| `aur-09` | Armazenamento 30 dias e garantia 18 meses → mesmos fatos | 5,3 → 5,3 | 1→1 | 1→1 | +1.956 | −71 |
| `bor-01` | Capacidade A de 6 caixas → mesmo fato | 1 → 1 | 1→1 | 1→1 | +1.950 | −169 |
| `bor-02` | Cartão verde libera B → mesmo fato | 2 → 2 | 1→1 | 1→1 | +281 | +78 |
| `bor-03` | Entregas terça/quinta às 9 h → mesmos fatos | 3 → 3 | 1→1 | 1→1 | −3.993 | −425 |
| `bor-04` | Cartão azul e 48 h em A → mesmos fatos | 4,2 → 4,2 | 1→1 | 1→1 | +3.482 | −193 |
| `bor-05` | Ausência do e-mail **no contexto** → ausência **nos documentos fornecidos** | 1,3 → 1,3 | ∅→∅ | 1→1 | +2.394 | −114 |
| `bor-06` | Escolheu retirada até 18 h → mesma interpretação; p. 4 continua ausente | 3 → 3 | ∅→∅ | 1→1 | −91 | −369 |
| `bor-07` | Trava fechada na falta de energia → mesmo fato e citação | 5 → 5 | 1→1 | 1→1 | +6.113 | +59 |
| `bor-08` | Incidente no livro L-7 → mesmo fato e citação | 5 → 5 | 1→1 | 1→1 | +5.651 | +13 |
| `bor-09` | 4 caixas em B e retirada até 18 h → mesmos fatos | 3,1 → 3,1 | 1→1 | 1→1 | +4.574 | +61 |

A lista de **IDs dos chunks** mudou somente em `aur-05` (adicionou o ID da p. 1 `0e92fbec-fcdf-55a3-b670-464ae86febbb`) e `aur-06` (substituiu p. 3 por p. 1). Em `aur-01`, `aur-02`, `bor-01`, `bor-05` e `bor-09`, o hash do contexto mudou, mas os IDs, a ordem e os **textos** dos chunks são iguais: o rótulo de índice `0` passou de `Chunk: None` para `Chunk: 0`. Nos outros 11 casos, o hash do contexto permaneceu igual. A referência a p. 4 continua ausente de `bor-06`; esta etapa não alterou seu limite de candidatos.

## Regra 2.0.0, abstenção e casos prioritários

| Caso | Baseline 3D sob regra 2.0.0 | 4B.4: saída original do juiz → decisão final | Leitura |
| --- | --- | --- | --- |
| `aur-05` | 0, comportamento `answered` | `model_score=1`, `answered` → **1** | Resposta agora cobre as duas partes com p. 1 e 2. |
| `aur-06` | 1 | `model_score=1`, `abstained` → **1** | Abstenção mantida; o contexto mudou de p. 2/3 para p. 2/1. |
| `bor-05` | `not_evaluable`, `null` | `model_score=1`, `answered` → **`not_evaluable`, `null`** | O juiz descreve ausência, mas etiqueta o comportamento como resposta. Regra 2.0.0 preserva a contradição para revisão humana. |
| `aur-07` | `not_evaluable`, `null` | `model_score=0`, `answered` → **`not_evaluable`, `null`** | Ambiguidade precisa de revisão humana; a resposta atual deixou de explicitar a ressalva. |
| `bor-06` | `not_evaluable`, `null` | `model_score=0`, `answered` → **`not_evaluable`, `null`** | Continua escolhendo o horário de retirada sem esclarecer “prazo” nem receber a p. 4. |

O **aumento de 2 para 3 casos não avaliáveis** em abstenção calibrada 1.1.0 decorre de `bor-05` sob a regra 2.0.0, não de falta de contexto para Faithfulness. A baseline 3D auditada offline e a 4B.4 sob a **mesma** regra 2.0.0 têm três casos sem score cada. Nos novos vereditos, `semantic.abstention_correctness` conserva os campos do juiz e registra `deterministic_correction`; não é necessário reaplicar `audit-decisions` sobre esse relatório já processado. O utilitário offline 4B.3 não é idempotente para esse caso: sua contagem de revisões sobre um relatório já marcado `not_evaluable` pode ser enganosa. Nenhum avaliador foi alterado nesta etapa.

## Ganhos, riscos e limites

**Ganho confirmado no mecanismo:** a p. 1 passou a entrar no prompt de `aur-05` e a resposta cobriu inicialização e autonomia. A comparação da única execução completa também mostrou scores maiores para esse caso. Não há outra mudança de AC ou F entre os 18 casos. As citações obrigatórias permaneceram presentes.

**Possíveis regressões que exigem revisão:** `aur-07` não explicita mais que “intervalo” é ambíguo; o score de abstenção continua `null` e uma decisão humana é necessária. Em `bor-05`, a nova frase sobre ausência **nos documentos** é mais abrangente que a ausência **no contexto** da baseline; o juiz deu Faithfulness 1, mas sua justificativa não prova que todos os documentos foram vistos pela generation. `aur-06` também usa linguagem sobre o documento inteiro com contexto parcial. A queda da métrica lexical de abstenção em `bor-05` é um falso negativo conhecido da regra 3A, não evidência isolada de piora da resposta. Não foram identificadas outras afirmações sem suporte pelos juízes; isso não substitui revisão humana.

**Limites estatísticos:** há um único run completo antes e um depois, ambos com LLM e latência sujeitos a variação. Não é possível atribuir o aumento médio de 2,657 s à correção de deduplicação nem declarar ausência global de regressões. Tokens do RAG caíram 3,3% apesar de `aur-05` ganhar contexto; as chamadas internas e respostas variam. O provider não informou custo monetário. Faithfulness 0,5 de `aur-05` na 3D já tinha justificativa contestada na Etapa 4A; a passagem a 1 não deve ser tomada isoladamente como prova de melhora de fundamentação.

## Artefatos e próxima validação

Relatórios completos locais, ignorados pelo Git: `baseline-3d-captured.json`, `baseline-3d-judged.json`, `baseline-3d-calibrated.json`, `baseline-3d.decision-audit.json`, `regression-4b4-captured.json`, `regression-4b4-judged.json` e `regression-4b4-calibrated.json` em `backend/app/evaluation/reports/`. A baseline 3B versionada e o resumo 3D também foram preservados. Nenhum prompt, embedding, modelo, limite, estratégia de busca, grafo ou avaliador foi modificado.

Próximo experimento recomendado: **revisão humana cega** de `aur-07`, `bor-05` e `bor-06`, incluindo se as afirmações de ausência são sustentadas pelo contexto efetivo; depois testar intervenções específicas para ambiguidade e seleção de evidências de `bor-06`, com dataset sintético independente e comparação controlada de latência/tokens. Não ampliar limites globalmente com base neste run.
