# Etapa 4B.1 — Diagnóstico do pipeline de recuperação

## Escopo e execução

O relatório local `backend/app/evaluation/reports/diagnosis-4b1.json` foi gerado em 16/11/2026 com **somente `aur-05` e `bor-06`** do dataset sintético `synthetic_rag_v1` 1.0.0. A execução usou o grafo e os modelos configurados, sem juiz e sem publicação no Langfuse. Ambos os casos concluíram; latência média 26,14 s. O relatório completo contém as respostas e os contextos sintéticos capturados no limite da chamada de geração. Ele permanece ignorado pelo Git; as baselines 3B, 3C e 3D não foram modificadas.

`aur-05` levou 27,486 s e reportou 2.468 tokens; `bor-06` levou 24,787 s e reportou 2.528 tokens. Os valores vêm dos metadados do provider agregados pelo executor. O custo monetário não foi informado.

Sequência confirmada: `rewrite_query` → `generate_search_queries` → `retrieve_context` → `search_similar_chunks_pgvector` por consulta → deduplicação e ordenação por **distância cosseno crescente** → limite de candidatos → `grade_retrieved_chunks` → `generate_answer` → `invoke_generation` → `format_sources`. A distância cosseno é a métrica retornada por `embedding <=> query_embedding`; **menor é melhor**. A seleção de fontes exibidas ocorre depois da geração e não decide o contexto do LLM.

A coleta explícita `--capture-context --diagnose-retrieval` registra A) resultado bruto por consulta, B) deduplicação, C) candidatos ao grader, D) seleção do grader, E) limite final do contexto e F) contexto efetivamente presente no prompt. A trilha A–E contém somente IDs técnicos, página, índice, posição, distância, status, motivo de descarte identificável e parâmetros. F contém IDs, ordem e hash; o texto sintético exato fica no campo local `generation_evidence`, capturado pela Etapa 3D. Nenhum desses textos é enviado ao Langfuse.

## `aur-05`

Pergunta: **“Como ligar a estação e por quanto tempo ela funciona com bateria?”** Esperado: **INICIAR por 3 segundos** (p. 1) e **8 horas** (p. 2). A nova resposta informa 8 horas, mas afirma que o procedimento para ligar não consta no documento e faz inferências sobre acionamento. A afirmação sobre o documento inteiro é indevida: a instrução está na p. 1 do fixture. O contexto recebido pelo gerador, porém, continha só a p. 2:

> A Estação Aurora usa bateria de 12 Ah e tem autonomia nominal de 8 horas. A recarga é feita por USB-C e dura aproximadamente 4 horas.

| Estágio | Candidatos e decisão |
| --- | --- |
| A, busca vetorial, `k=4` | p. 2 / índice 1 / distância **0,3710** (rank 1); p. 1 / índice 0 / **0,4657** (rank 2); p. 5 / índice 4 / **0,5436** (rank 3); p. 3 / índice 2 / **0,5567** (rank 4). |
| B, deduplicação | **p. 1 descartada**; restam p. 2, p. 5 e p. 3. O código usa `chunk.get("chunk_index") or metadata.get("chunk_index")`; para índice `0`, o resultado vira `None` e a chave cai para `page=1`. Essa chave colide com o índice `1` da p. 2. Como a p. 2 tem distância menor, ela prevalece. |
| C, limite do grader | As três páginas restantes entram no grader; `max_chunks_to_grade=3`, distância máxima aceitável `1,2`. |
| D, grader batch | Seleciona p. 2; p. 5 e p. 3 são descartadas. O grader não recebeu a p. 1. |
| E, contexto | Somente p. 2; o limite de 2 chunks e 900 caracteres por chunk não foi atingido. |
| F, prompt do LLM | Apenas p. 2, captura verificada; SHA-256 `0fbed4bea547918496771220e2a20c46e695410c7f5ec79d93afefc2470df167`. |

IDs técnicos dos quatro resultados originais, na ordem: p. 2 `ea5b34a6-ff57-5ef0-af7d-39d634087a5b`, p. 1 `0e92fbec-fcdf-55a3-b670-464ae86febbb`, p. 5 `d60164c8-81c6-5526-88d4-9c4a76fb3b9a`, p. 3 `3862fdec-e680-505b-9f7a-5b0f48179ac2`.

**Primeira perda confirmada: B, deduplicação.** A causa é a colisão da chave provocada pelo índice `0` tratado como valor falso. A trilha emitida durante esta execução traz o motivo genérico `duplicate_replaced_or_not_better`; a classificação mais precisa, `dedup_key_collision_different_chunk`, foi adicionada à instrumentação depois da execução, ao confrontar os IDs e o código. Não houve uma segunda chamada paga para atualizar esse rótulo no JSON original. O teste automatizado reproduz a colisão. A resposta parcial é consequência provável da falta da p. 1 no prompt; a justificativa de Faithfulness 0,5 da baseline 3D continua sujeita a revisão humana, pois se referia a outra resposta.

**Intervenção mínima recomendada para a Etapa 4B:** usar comparação explícita com `None` para preservar o índice `0` na normalização e verificar que a chave de deduplicação distingue p. 1 e p. 2. Não foi implementada nesta etapa.

## `bor-06`

Pergunta: **“Qual é o prazo do Armário Boreal?”** O dataset marca `answerable=false` porque “prazo” não define o objeto. A nova resposta escolhe o sentido de retirada até as 18 horas (p. 3), sem pedir esclarecimento nem cobrir o prazo de disponibilidade dos compartimentos. O gerador recebeu só:

> As entregas no Armário Boreal ocorrem terça-feira e quinta-feira às 9 horas. A retirada é permitida somente até as 18 horas.

| Estágio | Candidatos e decisão |
| --- | --- |
| A, buscas vetoriais, `k=4` por consulta | Consulta original: p. 3 **0,3535** (rank 1), p. 1 **0,3783** (2), p. 5 **0,4800** (3), p. 4 **0,5237** (4). Consulta reescrita: p. 3 **0,4211**, p. 1 **0,4471**, p. 5 **0,5692**, p. 4 **0,5914**. |
| B, deduplicação | Mantém a menor distância de cada um dos quatro chunks: p. 3, p. 1, p. 5, p. 4. As quatro segundas ocorrências são descartadas como duplicatas. |
| C, limite do grader | Seleciona p. 3, p. 1 e p. 5; **descarta p. 4**, rank 4, por `max_chunks_to_grade=3`. A p. 4 contém disponibilidade por 48 horas em A e 24 horas em B. |
| D, grader batch | Entre os três candidatos recebidos, seleciona apenas p. 3. O grader não recebeu a p. 4. |
| E, contexto | Apenas p. 3; o limite de 2 chunks e 900 caracteres por chunk não foi atingido. |
| F, prompt do LLM | Apenas p. 3, captura verificada; SHA-256 `54b2849046aac3630d1455d1bd5e9e2141f408a81f73bf7991bf2e0f7fd0837e`. |

IDs técnicos dos quatro chunks únicos: p. 3 `9c1809cf-479b-54e7-8f7c-2cc9e4a489c2`, p. 1 `ce125b0e-cb8d-57b3-a016-c23ca360d832`, p. 5 `948fe78f-e7e0-5633-966c-9ee44b8c0887`, p. 4 `ac9cbb27-3f14-5be1-a51f-d0857c893773`. A segunda consulta retornou os mesmos quatro IDs com distâncias maiores.

**Primeira perda confirmada: C, limite de três candidatos ao grader.** A busca recuperou p. 4 nas duas consultas, mas sua distância a deixou abaixo de outras três páginas após deduplicação. A ausência no prompt não pode ser atribuída ao grader nem ao limite final de dois chunks. É **hipótese**, não prova, que a disponibilidade da p. 4 teria levado o gerador a uma resposta melhor: a pergunta continua ambígua, e uma resposta com várias interpretações ou um pedido de esclarecimento depende do critério humano ainda pendente.

**Intervenção mínima recomendada para a Etapa 4B:** primeiro obter decisão humana sobre o tratamento de “prazo” ambíguo. Então comparar, em experimento isolado, esclarecimento dirigido com seleção sensível às interpretações. Aumentar globalmente `max_chunks_to_grade` não é justificado por estes dois casos.

## Validação e limites

- `python -m unittest discover -s tests -p 'test_*.py' -q`: **23 testes passaram**, incluindo ordenação, colisão de deduplicação, descarte por limite, filtro do grader, limite de contexto, rota sem contexto, captura desligada e seleção de IDs pela CLI.
- A execução dirigida completou **2/2 casos**; não executou juiz, não publicou no Cloud e não alterou a resposta ou as baselines. A cobertura lexical determinística média foi 0,5 e a abstenção passou em 0/1 caso esperado neste subconjunto; esses números não equivalem a correção factual.
- São duas execuções novas, não uma repetição determinística das respostas da baseline 3D. O diagnóstico de perda de chunks é sustentado pelos candidatos e pelo código. A eficácia de qualquer intervenção ainda exige casos sintéticos independentes, avaliação de Answer Correctness, Faithfulness e Abstention Correctness, além de latência, tokens e custo. O provider não informou custo monetário confiável.
- A trilha registra quais candidatos saíram do grader, sem armazenar texto nem justificativa livre. Na execução original, o motivo era `grader_not_selected`; a instrumentação agora distingue `grader_marked_not_relevant` de `grader_result_missing` em novas execuções. Isso não afeta a conclusão sobre p. 1 e p. 4, perdidas antes do grader.
