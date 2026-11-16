# Etapa 4B.2 — Correção da deduplicação e avaliação dirigida

## Mudança realizada

Em `manual_graph.py`, a normalização usava `chunk.get("chunk_index") or ...`. O índice inteiro `0` é falso em Python e virava `None`; a chave de deduplicação caía para a página `1` e colidia com a chave do chunk de índice `1` da página 2. Agora o fallback aos metadados ocorre **somente quando o índice é `None` ou está ausente**. A chave permanece `(document_id, chunk_index)` quando há índice e `(document_id, page)` quando não há. A busca por outras ocorrências de `get("chunk_index") or` no backend encontrou apenas esse ponto. Há um `page or ...` na mesma normalização, mas as páginas do dataset começam em 1; ele não foi alterado para manter o escopo da correção.

A ordenação crescente por **distância cosseno**, a regra de manter a duplicata de menor distância, os prompts, modelos, grafo, configurações e limites `k=4`, `max_chunks_to_grade=3`, `max_answer_context_chunks=2` e `max_answer_context_chars_per_chunk=900` permaneceram iguais. O caso `bor-06` não foi executado nem modificado nesta etapa.

## `aur-05`: antes e depois

Pergunta: “Como ligar a estação e por quanto tempo ela funciona com bateria?” Esperado: INICIAR por 3 segundos (p. 1) e autonomia de 8 horas (p. 2). A comparação usa a execução local 4B.1 **antes** da mudança e duas execuções locais 4B.2 **depois**, todas com a captura 3D do prompt e a trilha 4B.1. Os resultados novos são execuções independentes; as distâncias variaram ligeiramente com o embedding, mas a ordem das quatro páginas foi a mesma.

| Estágio | 4B.1, antes | 4B.2, depois, nas duas execuções |
| --- | --- | --- |
| A. Busca vetorial | p. 2 (índice 1, rank 1), p. 1 (índice 0, rank 2), p. 5 (4, rank 3), p. 3 (2, rank 4) | Mesmas quatro páginas e posições; na primeira execução nova, distâncias cosseno 0,3710, 0,4657, 0,5436 e 0,5567. |
| B. Deduplicação | p. 1 descartada por colisão de chave; restam p. 2, 5 e 3. | **p. 1 preservada** com índice `0`; restam p. 2, 1, 5 e 3. |
| C. Limite do grader | p. 2, 5 e 3 enviados. | p. 2, 1 e 5 enviados; p. 3 descartada pelo limite de 3. |
| D. Relevance grader | p. 2 selecionada; p. 5 e 3 rejeitadas. | p. 2 e 1 selecionadas; p. 5 rejeitada. |
| E. Contexto final | p. 2. | p. 2 e 1; o limite de 2 chunks é atingido, sem truncamento de texto. |
| F. Prompt do LLM | p. 2 apenas; hash `0fbed4bea547918496771220e2a20c46e695410c7f5ec79d93afefc2470df167`. | **p. 2 e p. 1**, captura verificada em ambas; mesmo hash `b88cfba94774f04e77e1fa6148f461e097c5864ee9b62712b6f6acf5ab19fc9a`. |

O contexto real novo inclui a instrução sintética “Para ligar, pressione INICIAR por 3 segundos” da p. 1 e a autonomia de 8 horas da p. 2. A primeira resposta nova apresentou ambos os fatos e citou as páginas 1 e 2. A segunda também apresentou ambos e citou as mesmas páginas. Portanto, a evidência necessária **chegou ao prompt**; não houve nova perda nos estágios C–F destas duas execuções. O primeiro ponto de perda observado em 4B.1 foi eliminado.

| Execução `aur-05` | Cobertura lexical | Answer Correctness | Faithfulness | Abstention Correctness | Latência RAG | Tokens RAG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline 3D, antes | 0,5 | 0,5 | 0,5 | 0 | 16,847 s | 2.306 |
| Diagnóstico 4B.1, antes | 0,5 | não reavaliado | não reavaliado | não reavaliado | 27,486 s | 2.468 |
| 4B.2, execução 1 | 1,0 | 1,0 | 1,0 | 1,0 | 26,662 s | 2.293 |
| 4B.2, execução 2 | 1,0 | 1,0 | 1,0 | 1,0 | 23,069 s | 2.108 |

Os scores semânticos novos foram produzidos localmente com `gpt-4.1-mini`, rubricas Answer Correctness `1.0.3`, Faithfulness `1.2.0` e Abstention Correctness `1.0.3`. O juiz usou somente o dataset sintético e o contexto exato capturado; nenhuma avaliação foi publicada. A melhora de score em duas respostas é **indício**, não prova estatística de ganho geral. A correção do defeito específico de deduplicação é sustentada pelo código, pelo teste e pela presença consistente da p. 1 nos estágios B–F.

## Controles e possível regressão de avaliação

Foram executados separadamente dois controles factuais (`aur-01`, `aur-03`) e dois casos simples de informação ausente (`aur-06`, `bor-05`), todos com captura local. O custo monetário do provider foi `null` em todos os relatórios.

| Caso | Contexto no prompt | Resposta e resultado | Answer Correctness | Faithfulness | Abstention Correctness | Latência | Tokens RAG |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `aur-01` | p. 1 | INICIAR por 3 segundos; fato coberto. | 1 | 1 | 1 | 44,322 s | 2.639 |
| `aur-03` | p. 2 | Autonomia de 8 horas; fato coberto. | 1 | 1 | 1 | 20,998 s | 1.868 |
| `aur-06` | p. 2 e 1 | Informa ausência da versão Bluetooth. | não avaliável | 1 | 1 | 14,035 s | 1.659 |
| `bor-05` | p. 1 e 3 | Informa ausência de endereço de e-mail de suporte. | não avaliável | 1 | **0 final; 1 do juiz** | 30,662 s | 1.803 |

Em `bor-05`, a resposta “Não há endereço de e-mail ... no contexto fornecido” é uma abstenção em linguagem natural. O detector determinístico `metrics.py` não reconhece essa formulação; a decisão estruturada do juiz registrou `model_score=1`, mas `model_behavior=answered`. A regra de pós-processamento `judge.py` manteve a classificação `answered` e converteu o score final em 0. A baseline 3D tinha uma resposta equivalente (“não está presente”), reconhecida pelo detector e com score final 1. **Isso aponta para uma divergência da avaliação, não confirma regressão do RAG.** Nenhum avaliador ou rubrica foi alterado nesta etapa. Answer Correctness é não avaliável nos dois casos sem resposta factual de referência; Faithfulness usa o contexto real verificado e ficou em 1 nos quatro controles.

Os cinco casos distintos executaram sem erro. Para o RAG, os controles reportaram 7.969 tokens; as duas execuções novas de `aur-05`, 4.401 tokens. O juiz reportou 7.251 tokens nos controles e 5.193 tokens nas duas execuções de `aur-05`. Esses valores vêm dos metadados do provider e não incluem custo em dólares, que não foi informado.

## Testes, privacidade e limites

`python -m unittest discover -s tests -p 'test_*.py' -q` passou com **25 testes**. Os novos testes cobrem índice `0` no resultado e nos metadados, índice `1`, índice ausente, `None`, documentos distintos, duplicatas reais com menor distância, ordenação, descartes e preservação da resposta. `compileall` e `git diff --check` também passaram. Os testes de API existentes continuaram passando.

As execuções usaram `--case-id`, `--capture-context` e `--diagnose-retrieval` apenas no dataset sintético preparado com status `evaluation`. O endpoint `/chat/ask` não ativou captura textual; o Langfuse ficou desabilitado nos experimentos locais. Os JSON completos em `backend/app/evaluation/reports/` continuam ignorados pelo Git. Baselines 3B, 3C, 3D e o relatório 4B.1 foram preservados.

O próximo experimento deve tratar separadamente a divergência de abstenção de `bor-05`, com revisão humana e versionamento do avaliador, e investigar `bor-06` sem aumentar limites por padrão. É preciso ampliar a amostra antes de afirmar melhora global de qualidade, latência ou custo.
