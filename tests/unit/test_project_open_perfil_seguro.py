"""PROJECT_OPEN: o perfil seguro é verificável estaticamente, ou é recusado.

Contrato `docs/84`. Observação medida: `docs/api` §`IScriptProjects`.

`projects.open` não é mutante incondicional nem leitura comum — é **guardada por
potencial de mutação**: o que ela faz depende dos argumentos, e existe
combinação que altera o projeto do cliente em silêncio.

O risco mora nos DEFAULTS do produto, medidos por `ParameterInfo.RawDefaultValue`:

    primary        default True   -> tornaria o projeto PRIMÁRIO
    allow_readonly default False  -> abriria GRAVÁVEL
    update_flags   default 1      -> NoUpdates (o único que já nasce seguro)

**Dois dos três têm default contrário ao uso seguro.** `open(path)` sozinho
torna primário e abre gravável.

E havia uma lacuna medida: `open` NÃO está em `VERBOS_PROIBIDOS` da guarda de
AST do probe 49, então `projects.open(...)` passaria calada por ela. Estas
guardas fecham isso.

A verificação é possível porque o perfil é **estaticamente verificável**:
argumento nomeado com valor literal está no AST. Argumento por variável REPROVA
— não porque variável seja errada, mas porque uma guarda estática não consegue
afirmar nada sobre o valor dela, e guarda que não consegue afirmar tem de
recusar. Não se torna a análise mais inteligente: torna-se a chamada mais
explícita.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO_ROOT / "scripts" / "mastertool"

# Receptores de `.open(` que NÃO são o produto. Lista FECHADA e minúscula: um
# `.open` sobre receptor desconhecido reprova e obriga a decisão explícita —
# mesmo critério do `_e_sys_path_insert` do probe 49.
RECEPTORES_ISENTOS = frozenset({"codecs", "io", "zipfile", "gzip", "tarfile"})

# O receptor do produto.
RECEPTOR_PRODUTO = "projects"


def _chamadas_open(caminho: Path):
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    achados = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        if not isinstance(no.func, ast.Attribute) or no.func.attr != "open":
            continue
        receptor = None
        if isinstance(no.func.value, ast.Name):
            receptor = no.func.value.id
        achados.append((receptor, no))
    return achados


@pytest.fixture(scope="module")
def fontes():
    return sorted(SCRIPTS.rglob("*.py"))


def test_ha_o_que_varrer(fontes) -> None:
    assert fontes, "nenhum fonte em scripts/mastertool -- a varredura mediria nada"


def test_todo_receptor_de_open_e_CONHECIDO(fontes) -> None:
    """Fail-closed. `.open` sobre receptor que ninguém classificou é decisão
    pendente, não detalhe."""
    desconhecidos = []
    for caminho in fontes:
        for receptor, no in _chamadas_open(caminho):
            if receptor == RECEPTOR_PRODUTO:
                continue
            if receptor in RECEPTORES_ISENTOS:
                continue
            desconhecidos.append("%s:%d receptor=%r"
                                 % (caminho.name, no.lineno, receptor))
    assert not desconhecidos, (
        "`.open(` sobre receptor não classificado: %s -- isentar exige editar "
        "RECEPTORES_ISENTOS deliberadamente" % desconhecidos)


_SEM_LITERAL = object()

# A forma pontuada aceita para `update_flags`. Ela NÃO é um literal Python, e é
# aceita mesmo assim porque a run-137 mediu que o inteiro é recusado pelo
# runtime (`expected VersionUpdateFlags, got int`). Continua demonstrável
# estaticamente — `Attribute(Name('VersionUpdateFlags'), 'NoUpdates')` é uma
# forma fechada — e diz o próprio nome, o que a torna mais auditável que `1`.
#
# Só ESTA forma. `flags = VersionUpdateFlags.NoUpdates; open(..., flags)` segue
# reprovado: a indireção por variável é o que a guarda não consegue afirmar.
ENUM_ACEITO = ("VersionUpdateFlags", "NoUpdates")


def _literal(no):
    """Valor do nó em forma demonstrável, ou `_SEM_LITERAL`.

    Nome e expressão não são demonstráveis: a guarda não consegue afirmar nada
    sobre eles. O acesso pontuado a um membro de enum nomeado é, e só ele.
    """
    if isinstance(no, ast.Constant):
        return no.value
    if (isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name)
            and (no.value.id, no.attr) == ENUM_ACEITO):
        return _ENUM_NO_UPDATES
    return _SEM_LITERAL


class _EnumNoUpdates(object):
    """Marcador do membro de enum, comparável ao valor canônico 1."""

    def __eq__(self, outro):
        return outro == 1

    def __ne__(self, outro):
        return not self.__eq__(outro)

    def __repr__(self):
        return "VersionUpdateFlags.NoUpdates"


_ENUM_NO_UPDATES = _EnumNoUpdates()


def test_toda_chamada_ao_PRODUTO_carrega_o_perfil_seguro_LITERAL(fontes) -> None:
    """Os três, por nome, com valor literal. Inclusive `update_flags`, que
    coincide com o default -- default é propriedade do produto e pode mudar
    entre versões; contrato não depende do que ninguém declarou."""
    exigido = {"primary": False, "allow_readonly": True, "update_flags": 1}

    chamadas = []
    for caminho in fontes:
        for receptor, no in _chamadas_open(caminho):
            if receptor != RECEPTOR_PRODUTO:
                continue
            chamadas.append((caminho, no))

    assert chamadas, (
        "nenhuma chamada a `projects.open` encontrada -- se a segunda porta "
        "sumiu, esta guarda deixou de medir alguma coisa")

    for caminho, no in chamadas:
        rotulo = "%s:%d" % (caminho.name, no.lineno)
        nomeados = {k.arg: k.value for k in no.keywords if k.arg is not None}

        assert not any(k.arg is None for k in no.keywords), (
            "%s: `**kwargs` na chamada torna o perfil indemonstrável" % rotulo)

        for chave, esperado in sorted(exigido.items()):
            assert chave in nomeados, (
                "%s: `%s` ausente -- omitir delega a decisão ao default do "
                "produto, e dois dos três defaults são inseguros" % (rotulo, chave))
            valor = _literal(nomeados[chave])
            assert valor is not _SEM_LITERAL, (
                "%s: `%s` não é demonstrável estaticamente. Guarda estática não "
                "consegue afirmar o valor de uma variável, e o que não se "
                "demonstra recusa-se." % (rotulo, chave))
            assert valor == esperado, (
                "%s: `%s` = %r, esperado %r" % (rotulo, chave, valor, esperado))
            if isinstance(esperado, bool):
                # `True == 1` em Python: sem esta checagem, `primary=0` passaria
                # como se fosse `False` e `allow_readonly=1` como `True`. Os dois
                # parâmetros que carregam a garantia são justamente booleanos.
                assert valor is esperado, (
                    "%s: `%s` = %r não é o booleano %r -- inteiro no lugar de "
                    "booleano compara igual e não é a mesma declaração"
                    % (rotulo, chave, valor, esperado))


def test_NENHUM_fallback_para_gravavel(fontes) -> None:
    """Recusa a abrir somente-leitura é resultado NOMEADO, nunca segunda
    tentativa sem a bandeira -- isso transformaria a garantia em preferência."""
    for caminho in fontes:
        for receptor, no in _chamadas_open(caminho):
            if receptor != RECEPTOR_PRODUTO:
                continue
            nomeados = {k.arg: k.value for k in no.keywords if k.arg is not None}
            valor = _literal(nomeados.get("allow_readonly"))
            assert valor is True, (
                "%s:%d abre com allow_readonly=%r" % (caminho.name, no.lineno, valor))
    fonte = (SCRIPTS / "common" / "project_access.py").read_text(encoding="utf-8")
    assert "project_open_readonly_refused" in fonte, (
        "a recusa do produto precisa de nome próprio no resultado")


# =============================================================================
# a porta do host
# =============================================================================

def _safety():
    sys.path.insert(0, str(SCRIPTS))
    try:
        from common import safety  # noqa: PLC0415
        return safety
    finally:
        sys.path.remove(str(SCRIPTS))


def test_a_porta_aceita_o_perfil_seguro() -> None:
    safety = _safety()
    perfil = safety.project_open_safe_profile()
    assert safety.assert_project_open_allowed(
        primary=perfil["primary"],
        update_flags=perfil["update_flags"],
        allow_readonly=perfil["allow_readonly"]) is True


@pytest.mark.parametrize("primary,update_flags,allow_readonly,agulha", [
    (True, 1, True, "primary"),                    # o default do produto
    (False, 1, False, "allow_readonly"),           # o default do produto
    (False, 0, True, "Regular"),                   # zero NÃO é NoUpdates
    (False, 65532, True, "update_flags"),          # UpdateAll
    (False, 8, True, "update_flags"),              # UpdateLibraries
    # `int(True) == 1` em Python: sem recusa explicita de booleano, isto
    # passaria como se fosse `NoUpdates`. E um booleano nesta posicao quase
    # sempre e argumento trocado de lugar com `primary`/`allow_readonly`.
    (False, True, True, "booleano"),
])
def test_a_porta_RECUSA_todo_perfil_que_nao_seja_o_seguro(
        primary, update_flags, allow_readonly, agulha) -> None:
    safety = _safety()
    with pytest.raises(safety.SafetyError) as erro:
        safety.assert_project_open_allowed(
            primary=primary, update_flags=update_flags,
            allow_readonly=allow_readonly)
    assert agulha in str(erro.value)


def test_Regular_zero_NAO_e_NoUpdates() -> None:
    """O erro mais fácil de cometer lendo o enum: `Regular = 0` parece "nada a
    fazer" e é o oposto -- num enum [Flags] zero é a ausência de bandeiras, o
    comportamento padrão do produto, que inclui atualizar."""
    safety = _safety()
    assert safety.PROJECT_OPEN_SAFE_UPDATE_FLAGS == 1
    assert safety.PROJECT_OPEN_SAFE_UPDATE_FLAGS_NAME == "NoUpdates"
    with pytest.raises(safety.SafetyError):
        safety.assert_project_open_allowed(
            primary=False, update_flags=0, allow_readonly=True)


def test_a_porta_NAO_tem_default_em_nenhum_argumento() -> None:
    """Um default aqui reproduziria, do nosso lado, exatamente o defeito que
    torna a chamada perigosa do lado do produto."""
    import inspect
    safety = _safety()
    assinatura = inspect.signature(safety.assert_project_open_allowed)
    for nome, parametro in assinatura.parameters.items():
        assert parametro.default is inspect.Parameter.empty, (
            "`%s` tem default na porta -- o gate não pode presumir nada" % nome)


def test_a_aquisicao_direta_NAO_expoe_o_perfil_como_parametro() -> None:
    """Oferecer o parâmetro criaria a possibilidade de passar o valor errado, e
    a única combinação qualificada é uma só."""
    import inspect
    sys.path.insert(0, str(SCRIPTS))
    try:
        from common import project_access  # noqa: PLC0415
        assinatura = inspect.signature(project_access.open_project_readonly)
    finally:
        sys.path.remove(str(SCRIPTS))
    proibidos = {"primary", "update_flags", "allow_readonly"}
    assert not (proibidos & set(assinatura.parameters)), (
        "a aquisição direta parametrizou o perfil: %s" % list(assinatura.parameters))


def test_a_porta_LEGACY_continua_existindo() -> None:
    """`get_primary_project` é o braço de controle do experimento e não pode
    ser substituída enquanto o DIRECT não passar o gate."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        from common import project_access  # noqa: PLC0415
        assert hasattr(project_access, "get_primary_project")
        assert hasattr(project_access, "open_project_readonly")
    finally:
        sys.path.remove(str(SCRIPTS))
