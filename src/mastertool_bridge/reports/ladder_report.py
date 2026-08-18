"""Exposição da semântica Ladder — árvore em Markdown, grafo e HTML.

TRÊS SUPERFÍCIES, UMA FONTE
===========================
Markdown, Mermaid e HTML são renderizações de `LadderQuery` e de mais nada.
Nenhuma delas recalcula, reordena por critério próprio ou infere. Se uma delas
pudesse decidir algo, "o relatório diz outra coisa" viraria um defeito sem
lugar onde procurar.

O QUE A APRESENTAÇÃO PRECISA SEPARAR
====================================
    fato          `SAIDA_A` tem dois escritores
    diagnóstico   `TEMPORIZADOR_0` não foi localizado
    limitação     tal expressão ainda não é suportada
    contexto      o índice necessário não foi fornecido

Agrupar os quatro como "erro" é o modo mais fácil de um relatório mentir sem
escrever nenhuma frase falsa: ele deixa o leitor concluir que o projeto tem
quatro problemas quando tem, no máximo, dois — e nenhum deles é o primeiro.

`EQ` e `MOVE` são operadores do padrão IEC. Eles ficam `not_applicable` e NÃO
entram na lista de símbolos inexistentes.

DETERMINISMO
============
`generated_at` entra como DADO, nunca do relógio: dois relatórios da mesma
análise têm de ser idênticos byte a byte, senão não se pode compará-los.
"""

from __future__ import annotations

import html
from typing import Any

SCHEMA_VERSION = 1

# Paleta importada, e não copiada. O guia canônico diz que alterar a paleta
# desalinha o documento de todos os outros da empresa — e uma SEGUNDA cópia
# dela aqui divergiria da primeira no dia em que alguém corrigisse uma só.
from mastertool_bridge.reports.qualification_report import _CSS  # noqa: E402

_NATUREZA_ROTULO = {
    "diagnostic": "Diagnóstico",
    "limitation": "Limitação declarada",
    "context": "Contexto insuficiente",
}

_CATEGORIA_ROTULO = {
    "symbol_not_found": "símbolo não localizado",
    "symbol_ambiguous": "símbolo ambíguo",
    "expression_not_supported": "expressão ainda não suportada",
    "insufficient_context": "índice não fornecido",
}


def _e(valor: Any) -> str:
    return html.escape("" if valor is None else str(valor), quote=True)


# =============================================================================
# Markdown — a visão por POU e network
# =============================================================================

def render_pou_markdown(query) -> str:
    """A árvore que um humano lê para entender uma POU Ladder."""
    resumo = query.summary()
    linhas = [
        "# POU %s" % query.pou,
        "",
        "> Visão gerada a partir da semântica local (R4.1) e da resolução "
        "contra o índice (R4.2). Nenhuma inferência nova.",
        "",
        "| | |",
        "|---|---|",
        "| Networks | %d |" % resumo["networks"],
        "| Leituras | %d |" % resumo["reads"],
        "| Escritas | %d |" % resumo["writes"],
        "| Leitura e escrita | %d |" % resumo["read_write"],
        "| Chamadas | %d |" % resumo["calls"],
        "| Símbolos com múltiplos escritores | %d |"
        % resumo["multi_writer_symbols"],
        "",
    ]

    for network_id in query.networks():
        net = query.network_semantics(network_id)
        linhas.append("## %s" % network_id)
        linhas.append("")
        if net["reads"]:
            linhas.append("- **reads:** %s" % _com_repeticao(net, "read"))
        if net["writes"]:
            linhas.append("- **writes:** %s" % _com_repeticao(net, "write"))
        instancias = [a for a in net["accesses"] if a["mode"] == "read_write"]
        if instancias:
            linhas.append("- **instances:** %s" % ", ".join(
                "%s [read_write]" % a["symbol_text"] for a in instancias))
        if net["calls"]:
            linhas.append("- **calls:** %s" % ", ".join(sorted(
                c["target_text"] for c in net["calls"])))
        if net["diagnostics"]:
            linhas.append("- **diagnostics:** %s" % "; ".join(
                d["message"] for d in net["diagnostics"]))
        else:
            linhas.append("- **diagnostics:** nenhum")
        if net["unresolved"]:
            linhas.append("- **unresolved:**")
            for aberto in net["unresolved"]:
                linhas.append("  - %s — %s" % (
                    aberto.get("symbol_text") or "(sem símbolo)",
                    aberto["category"]))
        linhas.append("")

    return "\n".join(linhas).rstrip() + "\n"


def _com_repeticao(net: dict, modo: str) -> str:
    """`ENTRADA ×2, ESTADO` — a contagem é de USOS, não de símbolos.

    Dois contatos da mesma variável são dois usos reais, e esconder isso
    faria a network parecer mais simples do que é.
    """
    contagem: dict = {}
    for acesso in net["accesses"]:
        if acesso["mode"] == modo:
            contagem[acesso["symbol_text"]] = contagem.get(
                acesso["symbol_text"], 0) + 1
    partes = []
    for simbolo in sorted(contagem):
        vezes = contagem[simbolo]
        partes.append(simbolo if vezes == 1 else "%s ×%d" % (simbolo, vezes))
    return ", ".join(partes)


# =============================================================================
# Mermaid — dependências
# =============================================================================

def render_dependency_graph(query) -> str:
    """Grafo determinístico em Mermaid.

    REGRAS QUE O DESENHO NÃO PODE QUEBRAR:

    * `power_flow` aparece como ligação LÓGICA (linha pontilhada), e nunca
      como variável — ele não tem símbolo, e desenhar um o inventaria;
    * chamadas e instâncias são nós DISTINTOS: `TON` é o tipo, e
      `TEMPORIZADOR_0` é a variável que guarda o estado;
    * toda aresta é rastreável até a network que a originou;
    * layout não altera identidade: a ordem é derivada dos ids, não do
      desenho.
    """
    linhas = ["graph LR"]
    vistos: set = set()
    # `(origem, seta, rótulo, destino)` → quantas vezes. Duas leituras da
    # mesma variável na mesma network são dois FATOS, e o grafo as mostra
    # como `×2` em vez de duas linhas idênticas: linha repetida não é
    # rastreável até o elemento que a originou, e a tabela do relatório é
    # quem carrega essa granularidade. Agregar aqui resume; não redefine.
    arestas: dict = {}

    def no(identidade: str, rotulo: str, forma: str = "[%s]") -> str:
        if identidade not in vistos:
            vistos.add(identidade)
            linhas.append("  %s%s" % (identidade, forma % rotulo))
        return identidade

    def aresta(origem, seta, rotulo, destino) -> None:
        chave = (origem, seta, rotulo, destino)
        arestas[chave] = arestas.get(chave, 0) + 1

    for network_id in query.networks():
        net = query.network_semantics(network_id)
        rede = no(_id(network_id), network_id, "([%s])")

        for acesso in net["accesses"]:
            simbolo = no(_id("sym:" + acesso["symbol_text"]),
                         acesso["symbol_text"])
            if acesso["mode"] == "read":
                aresta(simbolo, "-->", "read", rede)
            elif acesso["mode"] == "write":
                aresta(rede, "-->", "write", simbolo)
            else:
                aresta(rede, "<-->", "read_write", simbolo)

        for chamada in net["calls"]:
            # O NÓ É O SÍTIO DE CHAMADA, não o tipo. Duas chamadas a `MOVE`
            # na mesma network são dois sítios; colapsá-las num nó só tornaria
            # as arestas de pino impossíveis de atribuir, e a exigência é que
            # toda aresta tenha origem rastreável.
            alvo = no(_id("call:" + chamada["call_id"]),
                      chamada["target_text"], "{{%s}}")
            aresta(rede, "-->", "calls", alvo)

            if chamada["instance_symbol_text"]:
                # Instância e chamada são NÓS DISTINTOS: `TON` é o tipo,
                # `TEMPORIZADOR_0` é a variável que guarda o estado.
                instancia = no(_id("sym:" + chamada["instance_symbol_text"]),
                               chamada["instance_symbol_text"])
                aresta(alvo, "-.->", "instance", instancia)

            for pino in chamada["pins"]:
                if pino["status"] == "bound_symbol":
                    origem = no(_id("sym:" + pino["bound_symbol"]),
                                pino["bound_symbol"])
                    aresta(origem, "-->", pino["formal_parameter"], alvo)
                elif pino["status"] == "power_flow":
                    # LIGAÇÃO LÓGICA, sem símbolo. Pontilhada de propósito:
                    # ela não transporta valor, e desenhá-la como as outras
                    # convidaria a lê-la como dado.
                    aresta(rede, "-.->",
                           "%s: power flow" % pino["formal_parameter"], alvo)

    for (origem, seta, rotulo, destino) in sorted(arestas):
        vezes = arestas[(origem, seta, rotulo, destino)]
        marca = rotulo if vezes == 1 else "%s ×%d" % (rotulo, vezes)
        linhas.append("  %s %s|%s| %s" % (origem, seta, marca, destino))

    return "\n".join(linhas) + "\n"


def _id(texto: str) -> str:
    """Identificador seguro para Mermaid, derivado do texto — não de um
    contador. Contador dependeria da ordem de visita e mudaria o grafo sem
    que nada tivesse mudado."""
    return "n_" + "".join(c if c.isalnum() else "_" for c in texto)


# =============================================================================
# HTML — o relatório
# =============================================================================

_SECOES = (
    ("resumo", "Resumo"),
    ("networks", "Networks"),
    ("acessos", "Leituras e escritas"),
    ("chamadas", "Chamadas"),
    ("multi", "Múltiplos escritores"),
    ("abertos", "Não resolvidos"),
    ("cruzado", "ST × Ladder"),
    ("limites", "Limites"),
)


def render_ladder_report(query, *, generated_at: str,
                         logo_data_uri: str | None = None) -> str:
    """HTML autocontido: sem CDN, sem webfont, sem JS.

    `generated_at` é obrigatório e entra como dado — o gerador não lê o
    relógio, para que dois relatórios da mesma análise sejam idênticos.
    """
    resumo = query.summary()
    partes = [
        "<!-- ladder-report v%d -->" % SCHEMA_VERSION,
        "<style>%s</style>" % _CSS,
        _hero(query, resumo, generated_at, logo_data_uri),
        _toc(),
        _secao_resumo(resumo),
        _secao_networks(query),
        _secao_acessos(query),
        _secao_chamadas(query),
        _secao_multi(query),
        _secao_abertos(query),
        _secao_cruzado(query),
        _secao_limites(),
    ]
    return "\n".join(partes) + "\n"


def _hero(query, resumo, generated_at, logo) -> str:
    marca = ('<img class="logo" src="%s" alt="">' % _e(logo)) if logo else ""
    return (
        '<div class="hero"><div class="wrap">%s'
        '<p class="eyebrow">Semântica Ladder</p>'
        '<h1>POU %s</h1>'
        '<p class="sub">Leituras, escritas e chamadas derivadas do export '
        'PLCopen e resolvidas contra o índice estático do projeto.</p>'
        '<div class="rule"></div>'
        '<div class="meta">'
        '<div><b>Networks</b><span>%d</span></div>'
        '<div><b>Acessos</b><span>%d</span></div>'
        '<div><b>Chamadas</b><span>%d</span></div>'
        '<div><b>Gerado em</b><span class="small">%s</span></div>'
        '</div></div></div>'
        % (marca, _e(query.pou), resumo["networks"], resumo["accesses"],
           resumo["calls"], _e(generated_at)))


def _toc() -> str:
    itens = "".join('<a href="#%s">%s</a>' % (i, _e(t)) for i, t in _SECOES)
    return '<nav class="toc"><div class="wrap">%s</div></nav>' % itens


def _secao(ident, numero, rotulo, conclusao, corpo) -> str:
    return ('<section id="%s"><div class="wrap">'
            '<h2><span class="n">%02d</span>%s</h2><h3>%s</h3>%s'
            '</div></section>' % (ident, numero, _e(rotulo), _e(conclusao),
                                  corpo))


def _tabela(caption, cabecalhos, linhas) -> str:
    if not linhas:
        return '<p class="muted">%s</p>' % _e("Nada a listar.")
    cab = "".join("<th>%s</th>" % _e(c) for c in cabecalhos)
    corpo = "".join(
        "<tr>%s</tr>" % "".join("<td>%s</td>" % _e(c) for c in linha)
        for linha in linhas)
    return ("<table><caption>%s</caption><thead><tr>%s</tr></thead>"
            "<tbody>%s</tbody></table>" % (_e(caption), cab, corpo))


def _secao_resumo(resumo) -> str:
    linhas = [
        ("Networks", resumo["networks"]),
        ("Leituras", resumo["reads"]),
        ("Escritas", resumo["writes"]),
        ("Leitura e escrita", resumo["read_write"]),
        ("Chamadas", resumo["calls"]),
        ("Símbolos com múltiplos escritores", resumo["multi_writer_symbols"]),
    ]
    linhas += [("Resolução: %s" % estado, quantidade)
               for estado, quantidade in resumo["resolution"].items()]
    linhas += [("Aberto: %s" % _CATEGORIA_ROTULO.get(c, c), n)
               for c, n in resumo["unresolved_by_category"].items()]
    return _secao(
        "resumo", 1, "Resumo",
        "A análise cobriu %d network(s) e produziu %d acesso(s)."
        % (resumo["networks"], resumo["accesses"]),
        _tabela("Contagens da ANÁLISE. Elas descrevem o que foi derivado, "
                "não a qualidade do projeto.",
                ("Indicador", "Valor"),
                [(rotulo, valor) for rotulo, valor in linhas]))


def _secao_networks(query) -> str:
    linhas = []
    for network_id in query.networks():
        net = query.network_semantics(network_id)
        linhas.append((
            network_id,
            _com_repeticao(net, "read") or "—",
            _com_repeticao(net, "write") or "—",
            ", ".join(sorted(c["target_text"] for c in net["calls"])) or "—",
            len(net["unresolved"])))
    return _secao(
        "networks", 2, "Networks",
        "Cada network, com o que ela lê, escreve e chama.",
        _tabela("Leia por linha: o que entra, o que sai e o que é chamado. "
                "`×N` indica usos distintos do mesmo símbolo.",
                ("Network", "Reads", "Writes", "Calls", "Abertos"), linhas))


def _secao_acessos(query) -> str:
    linhas = []
    for network_id in query.networks():
        for acesso in query.network_semantics(network_id)["accesses"]:
            linhas.append((acesso["symbol_text"], acesso["mode"], network_id,
                           acesso["evidence"].get("element_id"),
                           acesso["resolution_status"],
                           acesso["declared_type"] or "—"))
    return _secao(
        "acessos", 3, "Leituras e escritas",
        "Cada acesso aponta para o elemento que o originou.",
        _tabela("`resolution_status` é sobre o SÍMBOLO, não sobre o acesso: "
                "o acesso existe mesmo quando o símbolo não foi localizado.",
                ("Símbolo", "Modo", "Network", "Elemento", "Resolução",
                 "Tipo"), linhas))


def _secao_chamadas(query) -> str:
    linhas = []
    for chamada in query.calls():
        pinos = "; ".join(
            "%s=%s" % (p["formal_parameter"],
                       p["bound_symbol"] or p["bound_literal"] or p["status"])
            for p in chamada["pins"])
        linhas.append((chamada["target_text"], chamada["call_kind"],
                       chamada["instance_symbol_text"] or "—",
                       chamada["resolution_status"], pinos))
    return _secao(
        "chamadas", 4, "Chamadas",
        "Tipo e instância são fatos separados, e resolvem em separado.",
        _tabela("`not_applicable` marca operador do padrão IEC (`EQ`, "
                "`MOVE`): ele existe, só não no índice do projeto.",
                ("Alvo", "Espécie", "Instância", "Resolução", "Pinos"),
                linhas))


def _secao_multi(query) -> str:
    multiplos = query.multi_writers()
    linhas = []
    for simbolo, fatos in multiplos.items():
        for fato in fatos:
            linhas.append((simbolo, fato["source_language"],
                           fato.get("network_id") or fato.get("file") or "—",
                           fato.get("element_id") or "—"))
    return _secao(
        "multi", 5, "Múltiplos escritores",
        "%d símbolo(s) com mais de um escritor." % len(multiplos),
        _tabela("Isto é um FATO do projeto, não um defeito: pode ser "
                "intertravamento, modo manual ou comando redundante "
                "deliberado. A ferramenta não julga a engenharia.",
                ("Símbolo", "Linguagem", "Origem", "Elemento"), linhas))


def _secao_abertos(query) -> str:
    abertos = query.unresolved()
    blocos = []
    for categoria, dados in abertos["by_category"].items():
        linhas = [(item.get("symbol_text") or "—",
                   item.get("network_id") or "—",
                   item.get("access_id") or item.get("call_id") or "—")
                  for item in dados["items"]]
        blocos.append(
            "<h4>%s — %s</h4>%s"
            % (_e(_NATUREZA_ROTULO.get(dados["nature"], dados["nature"])),
               _e(_CATEGORIA_ROTULO.get(categoria, categoria)),
               _tabela("Ação de correção específica desta categoria.",
                       ("Símbolo", "Network", "Referência"), linhas)))
    corpo = "".join(blocos) or '<p class="muted">Nada em aberto.</p>'
    return _secao(
        "abertos", 6, "Não resolvidos",
        "%d referência(s), separadas por NATUREZA." % abertos["count"],
        corpo)


def _secao_cruzado(query) -> str:
    cruzados = query.cross_language()
    linhas = []
    for simbolo, dados in cruzados.items():
        for fato in dados["facts"]:
            linhas.append((simbolo, fato["source_language"], fato["mode"],
                           fato.get("network_id") or fato.get("file") or "—"))
    return _secao(
        "cruzado", 7, "ST × Ladder",
        "%d símbolo(s) aparecem nas duas linguagens." % len(cruzados),
        _tabela("As origens permanecem separadas: unir as linguagens numa "
                "linha só perderia de onde cada fato veio.",
                ("Símbolo", "Linguagem", "Modo", "Origem"), linhas))


def _secao_limites() -> str:
    return _secao(
        "limites", 8, "Limites",
        "O que esta análise NÃO afirma.",
        "<ul>"
        "<li>Resolução é <b>estática</b>: ela diz onde um símbolo é lido e "
        "escrito no texto do projeto, nunca o que acontece em execução.</li>"
        "<li><b>Múltiplos escritores</b> é fato, não veredito. Decidir se é "
        "defeito exige conhecer a intenção da lógica.</li>"
        "<li><b>Ligação de fluxo de energia</b> não transporta valor. Ela "
        "aparece como ligação lógica e nunca como variável.</li>"
        "<li><b>Literais</b> são argumentos, e por isso não figuram como "
        "leitura de variável nenhuma.</li>"
        "<li>Tipos de elemento ainda <b>não observados</b> em export real não "
        "recebem interpretação — eles ficam explicitamente em aberto.</li>"
        "<li>Símbolo não localizado pode ser erro de projeto <b>ou</b> índice "
        "incompleto. As duas hipóteses têm categorias distintas, e este "
        "relatório não escolhe entre elas.</li>"
        "</ul>")
