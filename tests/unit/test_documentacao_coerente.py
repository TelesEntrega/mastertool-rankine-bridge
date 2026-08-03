"""Impede que a documentacao volte a divergir de si mesma.

Este arquivo nao testa comportamento do produto. Ele testa a condicao que,
quando falhou, fez o repositorio afirmar ao mesmo tempo que a compilacao nao
estava implementada e que o `build` rodava com zero erros -- em documentos
ativos, os dois no mesmo `docs/`.

O padrao guardado e sempre o mesmo: **um fato tem UMA fonte**. Onde houver
duas, a que ninguem edita e a que mente. Consequencias praticas:

- o estado vigente mora em `docs/CURRENT_STATUS.md` e em nenhum outro lugar;
- documento superado nao e apagado nem reescrito -- recebe cabecalho que diz o
  que mudou, e so pode conter afirmacao superada se estiver marcado;
- relatorio de execucao e EVIDENCIA datada e nunca e corrigido;
- quando um documento cita um valor que o codigo tambem define
  (`CONTROLLED_WRITE_PHASE`, `READ_ONLY_PHASE`, sha256 do template), quem manda
  e o codigo, e a divergencia e falha de teste, nao detalhe de redacao.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = REPO_ROOT / "docs"
README = REPO_ROOT / "README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
SAFETY_PY = REPO_ROOT / "scripts" / "mastertool" / "common" / "safety.py"

# Documentos que formam a fonte canonica. A ausencia de qualquer um deles
# reabre o problema que este arquivo existe para fechar.
DOCUMENTOS_CANONICOS = (
    "CURRENT_STATUS.md",
    "ROADMAP.md",
    "CAPABILITY_MATRIX.md",
    "COMPATIBILITY_MATRIX.md",
    "SAFETY_MODEL.md",
    "history/README.md",
)

# Marcadores de cabecalho. Um documento que carrega um destes declarou o que e.
MARCADOR_HISTORICO = "**HISTÓRICO — SUPERADO.**"
MARCADOR_PONTEIRO = "**PONTEIRO"

# Relatorios de execucao e de medicao: EVIDENCIA datada, imutavel. Listados um
# a um de proposito -- faixa numerica convidaria a incluir documento novo sem
# decidir o que ele e.
DOCUMENTOS_DE_EVIDENCIA = frozenset(
    {
        "03-scripting-discovery.md",
        "15-automation-launcher-roadmap.md",
        "22-varredura-completa-da-arvore.md",
        "23-export-por-dispositivo.md",
        "24-investigacao-api-de-parametros.md",
        "25-inventario-de-comunicacao.md",
        "26-compatibilidade-de-export-por-dispositivo.md",
        "27-reconhecimento-mastertool-x.md",
        "33-execucao-w1-3a-edicao-gvl.md",
        "34-execucao-w1-3b-edicao-program.md",
        "36-qualificacao-template-tmf-v1.md",
        "37-execucao-w1-4-autoria-integrada.md",
        "39-execucao-w2-program-call.md",
        "40-medicao-determinismo-w1-4.md",
        "41-execucao-w3-chamada-idiomatica.md",
        "42-execucao-w4-fabrica-de-projetos.md",
        "43-execucao-w5-prova-fb-e-function.md",
        "44-medicao-determinismo-da-fabrica.md",
        "45-medicao-enums-duttype-e-kindoftask.md",
        "46-execucao-w6-dut-e-task.md",
        "47-execucao-w7-fabrica-completa.md",
        "48-execucao-w8-task-com-pou.md",
        "49-execucao-w9-tempo-da-task.md",
        "50-qualificacao-r1-n10.md",
        "51-qualificacao-r1-task-n10.md",
        "api/mastertool-api-observations.md",
    }
)

# Documentos cuja FUNCAO e falar sobre a superacao. Eles precisam citar as
# frases superadas para explicar o que mudou; proibi-las ali tornaria
# impossivel documentar a correcao.
DOCUMENTOS_QUE_EXPLICAM_A_SUPERACAO = frozenset(
    {
        "CURRENT_STATUS.md",
        "ROADMAP.md",
        "CAPABILITY_MATRIX.md",
        "COMPATIBILITY_MATRIX.md",
        "SAFETY_MODEL.md",
        "history/README.md",
        "INDEX.md",
    }
)

# Afirmacoes que W1-W9 tornaram falsas. Cada uma foi copiada literalmente do
# documento onde estava, e cada uma tem o registro que a derrubou.
AFIRMACOES_SUPERADAS = (
    (
        "compilacao-nao-implementada",
        re.compile(r"Fase 3\s*[—-]\s*n[ãa]o implementada"),
        "o `build` do MasterTool X e executado e verificado desde a W1.4 (docs/37)",
    ),
    (
        "importacao-bloqueada-como-estado-do-projeto",
        re.compile(r"Importa[çc][ãa]o est[áa] propositalmente desabilitada"),
        "a autoria controlada no MasterTool X esta comprovada em campo (docs/42-49)",
    ),
    (
        "projeto-somente-leitura",
        re.compile(r"Estado atual:\s*\*?\*?Fase 0/1\s*[—-]\s*somente leitura"),
        "vinte fases de escrita controlada foram abertas e encerradas (W0 a W9)",
    ),
    (
        "nada-neste-repo-escreve",
        re.compile(r"Nenhum script deste reposit[óo]rio modifica projetos do MasterTool"),
        "os probes de autoria modificam copias descartaveis desde a W1.1",
    ),
    # As duas formas abaixo aparecem como LINHA DE TABELA de fases, nao como
    # titulo -- e a primeira versao desta guarda nao as pegava. Ficam separadas
    # em vez de generalizadas: regex larga sobre "nao implementada" acusaria
    # todo documento que descreve honestamente uma lacuna, que e justamente o
    # que este projeto quer que se escreva.
    (
        "tabela-de-fases-diz-compilacao-nao-implementada",
        re.compile(r"\|\s*3\s*\|[^|]*[Cc]ompila[çc][ãa]o[^|]*\|\s*[Nn][ãa]o implementada"),
        "o `build` do MasterTool X e executado e verificado desde a W1.4 (docs/37)",
    ),
    (
        "tabela-de-fases-diz-importacao-bloqueada",
        re.compile(r"\|\s*4\s*\|[^|]*[Ii]mporta[çc][ãa]o[^|]*\|\s*(bloqueada|[Nn][ãa]o implementada)"),
        "a autoria controlada no MasterTool X esta comprovada em campo (docs/42-49)",
    ),
)

LINK_MARKDOWN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


# ---------------------------------------------------------------------------
# Funcoes puras -- testadas nos dois sentidos mais abaixo
# ---------------------------------------------------------------------------


def _documentos_markdown() -> list[Path]:
    return sorted(DOCS.rglob("*.md")) + [README]


def _nome_relativo(caminho: Path) -> str:
    return caminho.relative_to(DOCS).as_posix() if DOCS in caminho.parents else caminho.name


def esta_marcado(texto: str) -> bool:
    """O documento declara que e historico ou ponteiro?"""
    return MARCADOR_HISTORICO in texto or MARCADOR_PONTEIRO in texto


def afirmacoes_superadas_em(texto: str) -> list[str]:
    """Nomes das afirmacoes superadas presentes no texto."""
    return [nome for nome, padrao, _ in AFIRMACOES_SUPERADAS if padrao.search(texto)]


def pode_conter_afirmacao_superada(nome: str, texto: str) -> bool:
    """Um documento so pode carregar afirmacao superada se disser o que e.

    Tres formas de dizer: cabecalho de historico/ponteiro, ser relatorio de
    execucao (evidencia datada, jamais corrigida) ou ser um dos documentos
    cuja funcao e explicar a superacao.
    """
    if nome in DOCUMENTOS_QUE_EXPLICAM_A_SUPERACAO:
        return True
    if nome in DOCUMENTOS_DE_EVIDENCIA:
        return True
    return esta_marcado(texto)


def _ancoras_de(texto: str) -> set[str]:
    """Ancoras que o GitHub geraria para os titulos do documento."""
    ancoras: set[str] = set()
    for linha in texto.splitlines():
        if not linha.startswith("#"):
            continue
        titulo = linha.lstrip("#").strip()
        slug = titulo.lower()
        slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
        slug = re.sub(r"[\s]+", "-", slug.strip())
        ancoras.add(slug)
    return ancoras


def links_internos(texto: str) -> list[str]:
    """Alvos de link que apontam para dentro do repositorio."""
    alvos = []
    for alvo in LINK_MARKDOWN.findall(texto):
        alvo = alvo.strip()
        if alvo.startswith(("http://", "https://", "mailto:", "#")):
            continue
        alvos.append(alvo)
    return alvos


# ---------------------------------------------------------------------------
# A fonte canonica existe
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", DOCUMENTOS_CANONICOS)
def test_documento_canonico_existe(nome: str) -> None:
    assert (DOCS / nome).is_file(), (
        "%s nao existe; sem ele o estado do projeto volta a ser derivado de "
        "leitura de varios documentos, que foi exatamente o defeito" % nome
    )


def test_todo_documento_de_docs_esta_classificado() -> None:
    """Documento novo entra classificado, ou nao entra.

    Sem isto, a classificacao envelhece: quem cria `docs/50-...md` nao tem
    nenhuma forca que o obrigue a dizer se aquilo e contrato, evidencia ou
    ponteiro, e seis meses depois ninguem sabe qual documento vale.
    """
    classificacao = (DOCS / "history" / "README.md").read_text(encoding="utf-8")
    nao_classificados = []
    for caminho in _documentos_markdown():
        if caminho == README:
            continue
        nome = _nome_relativo(caminho)
        if nome == "history/README.md":
            continue
        base = Path(nome).name
        # Basta o nome do arquivo aparecer -- a tabela cita ora com extensao,
        # ora com o numero, e exigir forma unica engessaria a redacao.
        numero = re.match(r"(\d+)-", base)
        citado = base in classificacao or nome in classificacao
        if not citado and numero:
            citado = ("`%s`" % numero.group(1)) in classificacao
        if not citado:
            nao_classificados.append(nome)
    assert not nao_classificados, (
        "documentos ausentes de docs/history/README.md: %s -- classifique cada "
        "um como NORMATIVO, EVIDENCIA, PONTEIRO ou HISTORICO" % nao_classificados
    )


# ---------------------------------------------------------------------------
# Nenhum documento ativo contradiz o estado
# ---------------------------------------------------------------------------


def test_nenhum_documento_ativo_carrega_afirmacao_superada() -> None:
    violacoes: list[str] = []
    for caminho in _documentos_markdown():
        texto = caminho.read_text(encoding="utf-8")
        presentes = afirmacoes_superadas_em(texto)
        if not presentes:
            continue
        nome = _nome_relativo(caminho)
        if pode_conter_afirmacao_superada(nome, texto):
            continue
        violacoes.append("%s: %s" % (nome, presentes))
    assert not violacoes, (
        "documento ativo afirma o que W1-W9 tornaram falso: %s -- ou corrija a "
        "afirmacao, ou marque o documento com o cabecalho de historico" % violacoes
    )


def test_readme_aponta_para_a_fonte_canonica() -> None:
    texto = README.read_text(encoding="utf-8")
    assert "CURRENT_STATUS.md" in texto, (
        "o README nao aponta para docs/CURRENT_STATUS.md; um README que "
        "descreve estado sem apontar para a fonte vira a segunda fonte"
    )


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


def test_todo_link_interno_resolve() -> None:
    quebrados: list[str] = []
    for caminho in _documentos_markdown():
        texto = caminho.read_text(encoding="utf-8")
        for alvo in links_internos(texto):
            arquivo = alvo.split("#", 1)[0]
            if not arquivo:
                continue
            destino = (caminho.parent / arquivo).resolve()
            if not destino.exists():
                quebrados.append("%s -> %s" % (_nome_relativo(caminho), alvo))
    assert not quebrados, "links internos quebrados: %s" % quebrados


def ancoras_quebradas_em(caminho: Path, texto: str) -> list[str]:
    """Links `arquivo.md#secao` cujo titulo nao existe no destino.

    Separado do teste porque hoje o repositorio **nao tem** nenhum link com
    ancora: rodar so sobre o repositorio deixaria a guarda passando por
    ausencia de dado, que e o modo de falha que este arquivo inteiro combate.
    A verificacao real da logica esta nos testes sinteticos, e este caminho
    passa a valer no dia em que a primeira ancora for escrita.
    """
    quebradas: list[str] = []
    for alvo in links_internos(texto):
        if "#" not in alvo:
            continue
        arquivo, ancora = alvo.split("#", 1)
        if not arquivo or not ancora:
            continue
        destino = (caminho.parent / arquivo).resolve()
        if not destino.is_file() or destino.suffix != ".md":
            continue
        if ancora.lower() not in _ancoras_de(destino.read_text(encoding="utf-8")):
            quebradas.append(alvo)
    return quebradas


def test_toda_ancora_interna_resolve() -> None:
    """Link com `#secao` que aponta para titulo inexistente e link quebrado
    que nenhuma verificacao de caminho pega."""
    quebradas: list[str] = []
    for caminho in _documentos_markdown():
        texto = caminho.read_text(encoding="utf-8")
        for alvo in links_internos(texto):
            if "#" not in alvo:
                continue
            arquivo, ancora = alvo.split("#", 1)
            if not arquivo or not ancora:
                continue
            destino = (caminho.parent / arquivo).resolve()
            if not destino.is_file() or destino.suffix != ".md":
                continue
            disponiveis = _ancoras_de(destino.read_text(encoding="utf-8"))
            if ancora.lower() not in disponiveis:
                quebradas.append("%s -> %s" % (_nome_relativo(caminho), alvo))
    assert not quebradas, "ancoras internas inexistentes: %s" % quebradas


# ---------------------------------------------------------------------------
# Documento x codigo: onde os dois falam, o codigo manda
# ---------------------------------------------------------------------------


def _valor_literal_em_safety(nome: str) -> str:
    fonte = SAFETY_PY.read_text(encoding="utf-8")
    achado = re.search(r"^%s\s*=\s*(.+)$" % re.escape(nome), fonte, re.M)
    assert achado is not None, "%s nao encontrado em safety.py" % nome
    return achado.group(1).strip()


def test_estado_do_gate_no_documento_confere_com_o_codigo() -> None:
    """`CURRENT_STATUS.md` publica o estado do gate. Se o gate abrir e o
    documento nao acompanhar, o repositorio passa a anunciar que nada escreve
    enquanto uma fase esta aberta -- que e a divergencia mais perigosa possivel
    neste projeto."""
    texto = (DOCS / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    fase = _valor_literal_em_safety("CONTROLLED_WRITE_PHASE")
    read_only = _valor_literal_em_safety("READ_ONLY_PHASE")

    assert "`CONTROLLED_WRITE_PHASE`" in texto, (
        "CURRENT_STATUS.md nao publica CONTROLLED_WRITE_PHASE"
    )
    if fase == "None":
        assert re.search(r"`CONTROLLED_WRITE_PHASE`\s*\|\s*\*\*`None`\*\*", texto), (
            "safety.py tem CONTROLLED_WRITE_PHASE = None, e CURRENT_STATUS.md "
            "nao diz isso na tabela de cabecalho"
        )
    else:
        assert fase.strip('"') in texto, (
            "safety.py abriu a fase %s e CURRENT_STATUS.md nao a nomeia" % fase
        )
    assert ("`%s`" % read_only) in texto, (
        "CURRENT_STATUS.md diverge de READ_ONLY_PHASE = %s" % read_only
    )


def test_matriz_de_capacidades_cobre_todo_o_contrato_do_executor() -> None:
    """A matriz e derivada do codigo, e o codigo e quem manda.

    Uma operacao acrescentada ao `EXECUTOR_CONTRACT` sem entrada na matriz e
    uma capacidade que o planner emite e que a documentacao nao classifica --
    ninguem saberia em que grau ela esta.
    """
    from mastertool_bridge.planner.planner import EXECUTOR_CONTRACT

    matriz = (DOCS / "CAPABILITY_MATRIX.md").read_text(encoding="utf-8")
    ausentes = [nome for nome in EXECUTOR_CONTRACT if "`%s`" % nome not in matriz]
    assert not ausentes, (
        "operacoes do EXECUTOR_CONTRACT ausentes de CAPABILITY_MATRIX.md: %s"
        % ausentes
    )


def test_a_soma_dos_graus_publicados_confere_com_o_contrato() -> None:
    """`CURRENT_STATUS.md` publica quantas operacoes estao em cada grau.

    Este numero ja esteve errado -- registros anteriores diziam treze contra
    catorze chaves no contrato. Contagem escrita a mao envelhece.

    A guarda mudou de forma em 2026-08-02, com a promocao da R1: antes ela
    conferia so `field_proven` contra o contrato, porque nada estava acima
    disso. Agora as operacoes estao repartidas entre graus, e o que tem de
    fechar e a SOMA -- uma operacao que sumisse de um grau sem aparecer em
    outro passaria despercebida numa contagem de grau unico.
    """
    from mastertool_bridge.planner.planner import EXECUTOR_CONTRACT

    provadas = [n for n, e in EXECUTOR_CONTRACT.items() if e.get("field_proven")]
    texto = (DOCS / "CURRENT_STATUS.md").read_text(encoding="utf-8")

    graus = ("production_qualified", "version_qualified", "template_qualified",
             "repeatable", "field_proven")
    publicado = {}
    for grau in graus:
        achado = re.search(
            r"\|\s*`%s`\s*\|\s*\*\*(\d+)\*\*" % grau, texto)
        assert achado is not None, (
            "CURRENT_STATUS.md nao publica a contagem do grau %r" % grau)
        publicado[grau] = int(achado.group(1))

    assert sum(publicado.values()) == len(provadas), (
        "CURRENT_STATUS.md publica %d operacoes somando todos os graus; o "
        "EXECUTOR_CONTRACT declara %d provadas em campo. Publicado: %s"
        % (sum(publicado.values()), len(provadas), publicado))


def test_grau_publicado_nunca_excede_o_que_o_PERFIL_deriva() -> None:
    """Este teste mudou de forma em 2026-08-02, e a mudanca e o registro.

    Ate a qualificacao R1 N=10 ele dizia "nenhuma operacao acima de
    `field_proven`", porque R1 nao tinha rodado e qualquer grau acima seria
    declaracao. R1 rodou: dez execucoes independentes, dez builds verificados,
    10/10 equivalentes, independencia limpa nos 45 pares.

    A invariante que fica e mais forte que a anterior: o que a matriz publica
    nao pode exceder o que o Template Profile DERIVA da evidencia. A matriz
    deixa de ser a fonte do grau e passa a ser o espelho dela -- e um grau
    escrito a mao na matriz, sem lastro no perfil, reprova aqui.
    """
    import json as _json

    matriz = (DOCS / "CAPABILITY_MATRIX.md").read_text(encoding="utf-8")

    perfil_bruto = _json.loads(
        (REPO_ROOT / "config" / "template-profiles"
         / "mastertool-x-4.1.0.11-tmf-v1-io.json").read_text(encoding="utf-8"))
    from mastertool_bridge.templates.profile import (
        MATURITY_SCALE,
        select_profile_for_file,
        validate_template_profile,
    )

    resultado = validate_template_profile(perfil_bruto)
    assert resultado.ok, resultado.problems
    perfil = select_profile_for_file(resultado, perfil_bruto["project"]["sha256"])
    derivados = {c.operation: c.maturity for c in perfil.qualified_capabilities}
    teto_derivado = max(
        (MATURITY_SCALE.index(m) for m in derivados.values()), default=1)

    graus = ("repeatable", "template_qualified", "version_qualified",
             "production_qualified")
    celulas_indevidas = []
    for linha in matriz.splitlines():
        if not linha.strip().startswith("|"):
            continue
        celulas = [c.strip().strip("`*") for c in linha.split("|")]
        for grau in graus:
            if grau not in celulas:
                continue
            if MATURITY_SCALE.index(grau) > teto_derivado:
                celulas_indevidas.append(linha.strip())
                break
            # O grau existe no perfil? A operacao da linha tem de estar la.
            operacao = next(
                (c for c in celulas if c in derivados), None)
            if operacao is None or derivados[operacao] != grau:
                celulas_indevidas.append(linha.strip())
            break
    assert not celulas_indevidas, (
        "CAPABILITY_MATRIX.md publica grau que o Template Profile nao deriva: "
        "%s" % celulas_indevidas)


def test_sha_do_template_confere_entre_documento_e_changelog() -> None:
    """O sha256 da base identifica a baseline inteira. Dois documentos com sha
    diferente significam duas baselines, e ninguem saberia qual foi medida."""
    status = (DOCS / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    changelog = CHANGELOG.read_text(encoding="utf-8")
    shas_status = set(re.findall(r"\b[0-9a-f]{64}\b", status))
    shas_changelog = set(re.findall(r"\b[0-9a-f]{64}\b", changelog))
    assert shas_status, "CURRENT_STATUS.md nao publica o sha256 da base"
    comuns = shas_status & shas_changelog
    assert comuns, (
        "nenhum sha256 de CURRENT_STATUS.md aparece no CHANGELOG; a baseline "
        "publicada no estado corrente nao tem origem registrada"
    )


def test_versao_do_pacote_e_pre_release_da_serie_0_2() -> None:
    """R0 entrega `v0.2.0-alpha.1`. A versao `0.1.0` descrevia uma ponte
    somente leitura e sobreviveu a nove fases de autoria."""
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    versao = dados["project"]["version"]
    assert versao != "0.1.0", (
        "pyproject ainda declara 0.1.0, a versao da fase somente leitura"
    )
    assert versao.startswith("0.2.0"), (
        "R0 fecha em 0.2.0a1; pyproject declara %s" % versao
    )


def test_descricao_do_pacote_nao_diz_somente_leitura() -> None:
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    descricao = dados["project"]["description"].lower()
    assert "somente leitura" not in descricao, (
        "a descricao do pacote ainda anuncia uma ponte somente leitura"
    )


def test_licenca_nao_e_provisoria() -> None:
    texto = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "substitua este arquivo" not in texto.lower(), (
        "LICENSE ainda pede para ser substituida quando a politica de "
        "distribuicao for definida; R0 exige a politica definida"
    )


# ---------------------------------------------------------------------------
# As guardas acima falham quando devem?
#
# Guarda que nunca reprovou nao e guarda. Cada funcao pura e exercida nos dois
# sentidos, com entrada sintetica.
# ---------------------------------------------------------------------------


def test_afirmacao_superada_e_detectada_em_texto_sintetico() -> None:
    texto = "# Doc\n\nEstado atual: **Fase 0/1 — somente leitura.**\n"
    assert afirmacoes_superadas_em(texto) == ["projeto-somente-leitura"]


def test_texto_sem_afirmacao_superada_passa() -> None:
    assert afirmacoes_superadas_em("# Doc\n\nO build roda e e verificado.\n") == []


def test_documento_marcado_pode_conter_afirmacao_superada() -> None:
    texto = "# Doc\n\n> %s Mudou tudo.\n\nFase 3 — não implementada\n" % MARCADOR_HISTORICO
    assert pode_conter_afirmacao_superada("99-qualquer.md", texto) is True


def test_documento_nao_marcado_nao_pode_conter_afirmacao_superada() -> None:
    texto = "# Doc\n\nFase 3 — não implementada\n"
    assert pode_conter_afirmacao_superada("99-qualquer.md", texto) is False


def test_relatorio_de_execucao_pode_conter_afirmacao_superada_sem_cabecalho() -> None:
    """Evidencia datada nao recebe cabecalho de superacao: corrigi-la seria
    reescrever o registro do que foi medido."""
    texto = "# W6\n\n`create_task` recusado.\n"
    assert pode_conter_afirmacao_superada("46-execucao-w6-dut-e-task.md", texto) is True


def test_link_externo_nao_e_verificado_como_caminho() -> None:
    texto = "[a](https://exemplo/x.md) e [b](outro.md)"
    assert links_internos(texto) == ["outro.md"]


def test_ancora_e_derivada_do_titulo() -> None:
    ancoras = _ancoras_de("# Titulo Um\n\n## Dois, com virgula\n")
    assert "titulo-um" in ancoras
    assert "dois-com-virgula" in ancoras


def test_ancora_inexistente_e_detectada(tmp_path: Path) -> None:
    """A guarda de ancora nao roda sobre o repositorio hoje -- nao ha link com
    ancora. Sem este teste ela ficaria verde para sempre sem nunca ter olhado
    para nada."""
    (tmp_path / "destino.md").write_text("# So Este Titulo\n", encoding="utf-8")
    origem = tmp_path / "origem.md"
    texto = "[bom](destino.md#so-este-titulo) e [ruim](destino.md#nao-existe)"
    origem.write_text(texto, encoding="utf-8")
    assert ancoras_quebradas_em(origem, texto) == ["destino.md#nao-existe"]


def test_linha_de_tabela_de_fases_superada_e_detectada() -> None:
    """A forma de tabela escapou da primeira versao desta guarda."""
    linha = "| 3 | Compilação e validação | Não implementada (desabilitada) |"
    assert "tabela-de-fases-diz-compilacao-nao-implementada" in afirmacoes_superadas_em(linha)
