from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.database.database import SessionLocal

THEMES = [
    {
        "theme_id": "automotive_manual",
        "name": "Manual automotivo",
        "description": (
            "Documentos de manuais de veiculos, com instrucoes de uso, alertas, "
            "especificacoes tecnicas, comandos e sistemas do veiculo."
        ),
        "enrichment_rules": [
            "Diferencie comandos do veiculo, indicadores, advertencias, especificacoes tecnicas e procedimentos de manutencao.",
            "Se o texto mencionar conectividade, diferencie Wi-Fi, rede movel, servicos conectados, chip, eSIM, modem, Bluetooth, Android Auto, Apple CarPlay e integracao com celular quando possivel.",
            "Se o texto mencionar pressao ou calibragem dos pneus, preserve a unidade original e nao converta se o trecho estiver ambiguo.",
            "Se o texto mencionar luzes, diferencie farol baixo, farol alto, luz de posicao, DRL, luz automatica, farol de neblina e lampejo.",
            "Se o texto mencionar bateria, diferencie bateria de tracao, bateria 12V, carregamento, autonomia e regeneracao.",
            "Nao assuma recursos do veiculo que nao estejam explicitamente descritos no texto.",
        ],
        "query_rules": [
            "Para perguntas sobre internet, gere consultas relacionadas a internet embarcada, Wi-Fi, rede movel, servicos conectados, eSIM, chip, modem, central multimidia, Rede e Internet e servicos online.",
            "Para perguntas sobre farol ou luz, gere consultas relacionadas a iluminacao, farol baixo, farol alto, luz de posicao, luz automatica, DRL e lampejo.",
            "Para perguntas sobre celular, gere consultas relacionadas a Bluetooth, Android Auto, Apple CarPlay, integracao de dispositivos moveis e central multimidia.",
            "Para perguntas sobre pneus, gere consultas relacionadas a calibragem, pressao dos pneus, Psi, kPa, bar, etiqueta da porta e rodas e pneus.",
        ],
        "answer_rules": [
            "Responda de forma pratica, como uma orientacao ao proprietario do veiculo.",
            "Quando a informacao estiver indireta ou ambigua, explique a limitacao claramente.",
            "Quando houver risco de seguranca, destaque o alerta.",
            "Nao invente especificacoes tecnicas ausentes no manual.",
            "Quando unidades estiverem ambiguas, preserve o valor como aparece no texto e informe a ambiguidade.",
        ],
    },
    {
        "theme_id": "hr_policy",
        "name": "Politica de RH",
        "description": (
            "Documentos internos de recursos humanos, beneficios, ferias, "
            "reembolsos, regras corporativas e procedimentos."
        ),
        "enrichment_rules": [
            "Identifique regras, elegibilidade, prazos, excecoes, responsaveis e procedimentos.",
            "Diferencie beneficio, obrigacao, restricao, aprovacao necessaria e recomendacao.",
            "Quando o texto usar termos como sujeito a aprovacao, condicionado ou mediante analise, destaque essa limitacao.",
            "Nao transforme uma possibilidade em direito garantido.",
        ],
        "query_rules": [
            "Para perguntas sobre beneficios, busque tambem elegibilidade, cobertura, excecoes, prazo, solicitacao e aprovacao.",
            "Para perguntas sobre ferias, busque tambem periodo aquisitivo, periodo concessivo, solicitacao, aprovacao e regras internas.",
            "Para perguntas sobre reembolso, busque tambem comprovante, prazo, politica, limite e aprovacao.",
        ],
        "answer_rules": [
            "Responda de forma clara e objetiva para um colaborador.",
            "Destaque prazos, condicoes e excecoes.",
            "Se a regra depender de aprovacao, informe isso explicitamente.",
            "Nao assuma direitos ou valores que nao estejam no documento.",
        ],
    },
    {
        "theme_id": "contract",
        "name": "Contrato",
        "description": (
            "Contratos, termos, acordos, clausulas comerciais e documentos juridicos."
        ),
        "enrichment_rules": [
            "Identifique partes, obrigacoes, prazos, condicoes, penalidades, multas, rescisao, vigencia e excecoes.",
            "Diferencie obrigacao, direito, condicao, restricao e penalidade.",
            "Nao forneca aconselhamento juridico definitivo.",
            "Quando o texto for ambiguo, destaque a ambiguidade.",
        ],
        "query_rules": [
            "Para perguntas sobre cancelamento, busque tambem rescisao, encerramento, denuncia, vigencia, multa e aviso previo.",
            "Para perguntas sobre pagamento, busque tambem vencimento, reajuste, multa, juros, obrigacao financeira e inadimplencia.",
            "Para perguntas sobre responsabilidade, busque tambem obrigacao, indenizacao, limitacao e penalidade.",
        ],
        "answer_rules": [
            "Responda com base nas clausulas recuperadas.",
            "Nao de conclusao juridica definitiva.",
            "Quando houver risco de interpretacao, recomende revisao especializada.",
            "Destaque clausulas, prazos e condicoes quando disponiveis.",
        ],
    },
    {
        "theme_id": "technical_documentation",
        "name": "Documentacao tecnica",
        "description": (
            "Documentacao de sistemas, APIs, arquitetura, guias tecnicos e "
            "manuais de software."
        ),
        "enrichment_rules": [
            "Identifique funcionalidades, endpoints, parametros, fluxos, pre-requisitos, erros, limitacoes e exemplos.",
            "Diferencie instrucoes de uso, configuracao, regra tecnica e comportamento esperado.",
            "Preserve nomes de endpoints, parametros, comandos, arquivos e variaveis exatamente como aparecem.",
        ],
        "query_rules": [
            "Para perguntas sobre API, busque tambem endpoint, metodo HTTP, payload, request, response, autenticacao e erro.",
            "Para perguntas sobre configuracao, busque tambem variavel de ambiente, arquivo, instalacao, setup e dependencia.",
            "Para perguntas sobre erro, busque tambem codigo de erro, mensagem, excecao, causa e solucao.",
        ],
        "answer_rules": [
            "Responda de forma tecnica e objetiva.",
            "Preserve nomes de metodos, endpoints, parametros e arquivos.",
            "Quando fizer sentido, organize a resposta em passos.",
            "Nao invente parametros ou endpoints nao documentados.",
        ],
    },
    {
        "theme_id": "generic_pdf",
        "name": "PDF generico",
        "description": "Tema padrao para documentos PDF sem dominio especifico.",
        "enrichment_rules": [
            "Identifique o assunto principal do trecho, termos importantes, possiveis perguntas e limitacoes.",
            "Nao invente informacoes que nao estejam no texto.",
            "Marque como invalido conteudo fragmentado, indice, rodape, capa ou trechos sem contexto util.",
        ],
        "query_rules": [
            "Gere consultas alternativas preservando a intencao original do usuario.",
            "Inclua sinonimos e termos relacionados quando fizer sentido.",
        ],
        "answer_rules": [
            "Responda apenas com base no contexto recuperado.",
            "Quando a informacao nao estiver clara, indique a limitacao.",
            "Nao use conhecimento externo.",
        ],
    },
]


def seed_themes() -> int:
    query = text(
        """
        INSERT INTO smartdocs.themes (
            id,
            name,
            description,
            enrichment_rules,
            query_rules,
            answer_rules,
            is_active,
            updated_at
        )
        VALUES (
            :id,
            :name,
            :description,
            :enrichment_rules,
            :query_rules,
            :answer_rules,
            TRUE,
            NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            enrichment_rules = EXCLUDED.enrichment_rules,
            query_rules = EXCLUDED.query_rules,
            answer_rules = EXCLUDED.answer_rules,
            is_active = TRUE,
            updated_at = NOW()
        """
    ).bindparams(
        bindparam("enrichment_rules", type_=JSONB),
        bindparam("query_rules", type_=JSONB),
        bindparam("answer_rules", type_=JSONB),
    )

    with SessionLocal() as db:
        for theme in THEMES:
            db.execute(
                query,
                {
                    "id": theme["theme_id"],
                    "name": theme["name"],
                    "description": theme["description"],
                    "enrichment_rules": theme.get("enrichment_rules", []),
                    "query_rules": theme.get("query_rules", []),
                    "answer_rules": theme.get("answer_rules", []),
                },
            )

        db.commit()

    return len(THEMES)


if __name__ == "__main__":
    total = seed_themes()
    print(f"Temas processados: {total}")
