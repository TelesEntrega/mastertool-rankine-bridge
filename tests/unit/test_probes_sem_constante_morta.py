"""Nenhum probe pode carregar constante de modulo que ninguem usa.

Achado ao apurar os criterios de W1.3B: `probes/33` DEFINIA
`EXPECTED_ST_LANGUAGE_GUID` e NUNCA a usava. O efeito nao e desperdicio de
bytes -- e leitura errada. Uma constante chamada "linguagem ST esperada" faz
o leitor concluir que a linguagem e verificada, e foi assim que "linguagem
continua ST" entrou numa lista de criterios sem instrumento por tras.

A regra que este arquivo impoe: **em probe, constante de modulo em CAIXA ALTA
existe para ser usada**. Se nao ha uso, ou a verificacao esta faltando, ou a
constante esta sobrando -- e as duas situacoes precisam de decisao humana, nao
de silencio.

A analise e por AST, e nao por texto: `grep` acharia o nome dentro de
comentario e de docstring, que e exatamente onde uma constante removida
costuma continuar sendo mencionada -- inclusive neste repositorio, onde a
remocao vem sempre acompanhada da razao por escrito.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROBES_DIR = REPO_ROOT / "scripts" / "mastertool" / "probes"
COMMON_DIR = REPO_ROOT / "scripts" / "mastertool" / "common"

# Nomes que existem para serem lidos DE FORA do modulo, ou que o interpretador
# consome sozinho. Ausencia de uso interno neles nao e sintoma de nada.
EXPORTADAS_POR_CONTRATO = frozenset([
    "SCRIPT_NAME",          # aparece nos artefatos, montado por quem os grava
    "SCHEMA_VERSION",       # idem
    "ARTIFACT_NAMES",       # contrato de saida, conferido por teste externo
    "ALL_STATUSES",         # enumeracao publicada
    "VOLATILE_FIELDS",      # consumida por comparadores externos
    # Vocabulario de origem de evidencia (common/capabilities.py). Sao cinco
    # valores de uma enumeracao publicada; tres tem uso interno e dois nao.
    # Enumeracao com membro sem uso interno e normal -- ela existe para o
    # CHAMADOR escolher, e o chamador aqui e o probe que ainda nao precisou
    # daquele grau de evidencia. Nao e o mesmo caso de uma constante que
    # aparenta implementar verificacao.
    "EVIDENCE_OFFICIAL_API_DUMP",
    "EVIDENCE_DOCUMENTATION",
])

# ACHADO em 2026-07-31, na primeira execucao desta guarda. Sao constantes
# mortas PREEXISTENTES, anteriores a W1.3B, em arquivos fora do slice que a
# descobriu. Ficam nomeadas aqui em vez de silenciadas: a guarda continua viva
# para tudo o que e novo, e `test_a_divida_de_constante_morta_nao_cresce`
# impede que a lista aumente.
#
# A classificacao importa, porque os casos NAO sao equivalentes:
#
#   VALID_MODES (quatro probes) -- REDUNDANTE, nao enganosa. O modo E
#     validado, por cadeia explicita if/elif contra MODE_PREFLIGHT e
#     MODE_POSTSAVE; a constante duplica esse conhecimento e ninguem a le.
#     Diferente de EXPECTED_ST_LANGUAGE_GUID, cujo comportamento anunciado
#     simplesmente NAO EXISTIA em lugar nenhum.
#   DEFAULT_LOG_ROOT e _NODE_PROPERTY_MEMBERS -- mortas de fato.
#
# Trabalhar essa divida e slice proprio: mexer em seis arquivos alheios no
# commit que fecha W1.3B misturaria coisas que a cadencia manda separar.
DIVIDA_CONHECIDA = {
    "15_validate_command_line_execution.py": ["DEFAULT_LOG_ROOT"],
    "28_verify_gvl_w1_1_readonly.py": ["VALID_MODES"],
    "29_preflight_program_w1_2_readonly.py": ["VALID_MODES"],
    "31_verify_gvl_edit_w1_3a_readonly.py": ["VALID_MODES"],
    "33_verify_program_edit_w1_3b_readonly.py": ["VALID_MODES"],
    "project_tree_adapter.py": ["_NODE_PROPERTY_MEMBERS"],
    # Apareceu so depois que a varredura foi CORRIGIDA para nao contar nome nu
    # de outro modulo como uso. Comeca com `_`, entao nem por importacao
    # alguem a alcanca: morta de fato.
    "graphic_language_inventory.py": ["_COLLECTION_ERROR_STATES"],
}


def _modulos() -> list[Path]:
    return sorted(PROBES_DIR.glob("*.py")) + sorted(COMMON_DIR.glob("*.py"))


def _arquivos_que_podem_usar() -> list[Path]:
    """TODO o codigo que pode ler uma constante de probe: os proprios probes,
    a camada common, os wrappers Python de scripts/, e os testes.

    Olhar so o modulo que DEFINE produziria falso positivo em massa -- uma
    constante importada por outro arquivo (`from common.artifacts import X`)
    ou exercida por teste apareceria como morta sem ser. Foi o primeiro
    resultado desta guarda, e o defeito era do analisador, nao do repo.
    """
    raizes = [REPO_ROOT / "scripts", REPO_ROOT / "tests"]
    arquivos: list[Path] = []
    for raiz in raizes:
        if raiz.exists():
            arquivos.extend(sorted(raiz.rglob("*.py")))
    # ESTE arquivo sai da varredura. Ele CITA os nomes -- em DIVIDA_CONHECIDA,
    # nas mensagens de erro, na regressao nomeada -- sem usar nenhum deles. Na
    # primeira versao ele se contaminava: escrever "VALID_MODES" aqui fazia a
    # constante contar como lida, e a divida se anulava sozinha. Um verificador
    # que se conta como usuario do que verifica sempre acha tudo em ordem.
    proprio = Path(__file__).resolve()
    return [a for a in arquivos if a.resolve() != proprio]


def _nomes_lidos_de_fora() -> set[str]:
    """Nomes que OUTRO arquivo consome de um modulo alheio.

    So contam duas formas, e a restricao e o ponto:

        `from common.artifacts import CONSTANTE`   -> ImportFrom
        `outro_modulo.CONSTANTE`                   -> Attribute

    A versao anterior contava tambem `ast.Name` solto em qualquer arquivo, e
    isso e ERRADO: um nome nu lido no modulo X nao pode se referir a uma
    constante de modulo do arquivo Y -- sao namespaces diferentes. O efeito
    apareceu quando um probe novo passou a ter a sua PROPRIA `VALID_MODES`:
    de repente as `VALID_MODES` mortas de quatro outros probes "passaram a ser
    usadas", e a lista de divida virou obsoleta sem que uma linha delas
    mudasse. Um verificador coincidencia-por-homonimo nao verifica nada.

    Constante em string tambem saiu da contagem: `getattr` e proibido por
    contrato aqui, entao nome em string nunca e acesso -- e mencao, que e
    exatamente o que este arquivo faz o tempo todo.
    """
    lidos: set[str] = set()
    for arquivo in _arquivos_que_podem_usar():
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - fixture proposital, se houver
            continue
        for no in ast.walk(arvore):
            if isinstance(no, ast.Attribute):
                lidos.add(no.attr)
            elif isinstance(no, ast.ImportFrom):
                for alias in no.names:
                    lidos.add(alias.name)
    return lidos


_LIDOS_DE_FORA = _nomes_lidos_de_fora()


def _definidas_em(caminho: Path) -> dict[str, int]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    definidas: dict[str, int] = {}
    for no in arvore.body:                       # so nivel de modulo
        alvos: list[ast.expr] = []
        if isinstance(no, ast.Assign):
            alvos = list(no.targets)
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvos = [no.target]
        for alvo in alvos:
            if isinstance(alvo, ast.Name) and alvo.id.isupper() and len(alvo.id) > 2:
                definidas.setdefault(alvo.id, no.lineno)
    return definidas


def _constantes_nao_usadas(caminho: Path) -> list[str]:
    """Definidas no modulo e lidas em lugar NENHUM do repositorio.

    A atribuicao em si nao conta como leitura -- senao toda constante se
    justificaria sozinha, que e exatamente o caso que esta guarda existe para
    pegar.
    """
    definidas = _definidas_em(caminho)
    lidas_no_proprio = set()
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name) and isinstance(no.ctx, ast.Load):
            lidas_no_proprio.add(no.id)

    return sorted(
        "%s:L%d" % (nome, linha)
        for nome, linha in definidas.items()
        if nome not in lidas_no_proprio
        and nome not in _LIDOS_DE_FORA
        and nome not in EXPORTADAS_POR_CONTRATO
    )


def test_existe_probe_para_varrer() -> None:
    """Ancora: uma varredura que nao encontra nada passa por vacuidade."""
    assert _modulos(), "nenhum modulo em scripts/mastertool/{probes,common}"


def _nomes(ociosas: list[str]) -> list[str]:
    return sorted(item.split(":")[0] for item in ociosas)


@pytest.mark.parametrize("modulo", _modulos(), ids=lambda p: p.name)
def test_modulo_nao_tem_constante_de_modulo_sem_uso(modulo: Path) -> None:
    """Divida conhecida e tolerada NOMINALMENTE, e so ela. Constante morta
    nova, em qualquer modulo, derruba este teste."""
    ociosas = _nomes(_constantes_nao_usadas(modulo))
    toleradas = sorted(DIVIDA_CONHECIDA.get(modulo.name, []))
    novas = [nome for nome in ociosas if nome not in toleradas]
    assert not novas, (
        "%s define constante(s) de modulo que ninguem le em lugar nenhum do "
        "repositorio: %s. Ou falta a verificacao que justificaria a "
        "constante, ou a constante sobra -- as duas exigem decisao, e nenhuma "
        "admite silencio. Se o nome for consumido de fora, acrescente-o a "
        "EXPORTADAS_POR_CONTRATO com a razao."
        % (modulo.name, novas))


def test_a_divida_de_constante_morta_nao_cresce() -> None:
    """A lista tolerada e um teto, nao um balde. Ela pode ENCOLHER sem tocar
    neste teste; crescer, nao."""
    observada: dict[str, list[str]] = {}
    for modulo in _modulos():
        ociosas = _nomes(_constantes_nao_usadas(modulo))
        if ociosas:
            observada[modulo.name] = ociosas

    excedente = {
        arquivo: [n for n in nomes if n not in DIVIDA_CONHECIDA.get(arquivo, [])]
        for arquivo, nomes in observada.items()
    }
    excedente = {k: v for k, v in excedente.items() if v}
    assert not excedente, "constante morta NOVA fora da divida conhecida: %s" % excedente


def test_a_divida_conhecida_nao_lista_o_que_ja_foi_resolvido() -> None:
    """A outra ponta: entrada que ficou na lista depois de resolvida faz a
    divida parecer maior do que e, e o proximo a ler perde tempo procurando
    defeito que nao existe."""
    observada = {
        modulo.name: _nomes(_constantes_nao_usadas(modulo))
        for modulo in _modulos()
    }
    obsoletas = {
        arquivo: [n for n in nomes if n not in observada.get(arquivo, [])]
        for arquivo, nomes in DIVIDA_CONHECIDA.items()
    }
    obsoletas = {k: v for k, v in obsoletas.items() if v}
    assert not obsoletas, (
        "DIVIDA_CONHECIDA lista constante que ja nao esta morta -- remova a "
        "entrada: %s" % obsoletas)


def test_a_constante_morta_de_w1_3b_nao_voltou() -> None:
    """Regressao nomeada do caso concreto. O nome pode aparecer em comentario
    explicando a remocao -- e aparece --, mas nao pode voltar como
    ATRIBUICAO, que e o que o tornaria lido como cobertura de novo."""
    caminho = PROBES_DIR / "33_verify_program_edit_w1_3b_readonly.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    atribuidos = {
        alvo.id
        for no in arvore.body if isinstance(no, ast.Assign)
        for alvo in no.targets if isinstance(alvo, ast.Name)
    }
    assert "EXPECTED_ST_LANGUAGE_GUID" not in atribuidos, (
        "probes/33 voltou a definir EXPECTED_ST_LANGUAGE_GUID sem usa-la; "
        "nao ha API catalogada que leia a linguagem de um objeto (docs/34)"
    )


def test_o_guid_de_st_continua_onde_TEM_uso() -> None:
    """A outra metade: remover a constante morta nao pode ter levado junto a
    viva. Em probes/34 o GUID e usado para conferir o valor declarado no
    plano contra a constante medida."""
    caminho = PROBES_DIR / "34_edit_program_w1_3b.py"
    assert not _constantes_nao_usadas(caminho), "probes/34 ficou com constante ociosa"
    fonte = caminho.read_text(encoding="utf-8")
    assert fonte.count("EXPECTED_ST_LANGUAGE_GUID") >= 2, (
        "EXPECTED_ST_LANGUAGE_GUID deveria estar definida E usada em probes/34"
    )
