"""Testes ESTRUTURAIS do gate de escrita controlada em
`scripts/mastertool/common/safety.py`.

Puramente estruturais: nenhuma API do MasterTool e invocada, nenhum projeto e
aberto. O que estes testes impedem e a abertura AMPLA acidental -- que o gate
deixe de significar exatamente "W1.3A: replace e save_as, mais nada".

Sao testes de politica, nao de mutacao.
"""

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

from common import safety  # noqa: E402


# --- W5 (prova de FB/FUNCTION) ATIVA; W1..W4 COMPLETOS ----------------------

FASE_ATIVA_W2 = "W2_BIND_PROGRAM_CALL"   # a fase que criou o Program Call
OPERACOES_DA_FASE_ATIVA = frozenset()

FASES_ENCERRADAS = {
    "W1_1_CREATE_GVL": frozenset(["create_gvl", "save_as"]),
    "W1_2_CREATE_PROGRAM": frozenset(["create_program", "save_as"]),
    "W1_3A_EDIT_GVL": frozenset(["replace", "save_as"]),
    "W1_3B_EDIT_PROGRAM": frozenset(["replace", "save_as"]),
    "W1_5_MEASURE_IEC_BIRTH": frozenset(["create_function_block",
                                         "create_function"]),
    "W1_4_INTEGRATED_BUILD": frozenset(["create_gvl", "create_program",
                                        "replace", "save_as", "build"]),
}

FASES_ENCERRADAS["W2_BIND_PROGRAM_CALL"] = frozenset(["add", "save_as"])
FASES_ENCERRADAS["W2_VERIFY_BUILD"] = frozenset(["build"])

# W3 -- a chamada IDIOMATICA, executada na run-026 e ENCERRADA. O build
# passou de 1 aviso do fabricante (W2) para 0 (W3).
FASES_ENCERRADAS["W3_IDIOMATIC_CALL"] = frozenset(["replace", "save_as"])
FASES_ENCERRADAS["W3_VERIFY_BUILD"] = frozenset(["build"])

# W4 -- a FABRICA, executada na run-027 e ENCERRADA. A spec virou plano, o
# plano virou projeto, e o projeto compilou com 0 erros e 0 avisos.
FASES_ENCERRADAS["W4_EXECUTE_PLAN"] = frozenset(["create_gvl",
                                                 "create_program",
                                                 "replace", "save_as"])
FASES_ENCERRADAS["W4_VERIFY_BUILD"] = frozenset(["build"])

# W5 -- provar FB e FUNCTION em cadeia que persiste e compila.
# `W5_PROVE_IEC_PACKAGE` esta ATIVA.
FASES_ENCERRADAS["W5_PROVE_IEC_PACKAGE"] = frozenset(
    ["create_gvl", "create_program", "create_function_block",
     "create_function", "replace", "save_as"])
FASES_ENCERRADAS["W5_VERIFY_BUILD"] = frozenset(["build"])

# W6 -- provar `create_dut` e `create_task` em cadeia.
FASES_ENCERRADAS_DE_W6 = {
    "W6_PROVE_DUT_AND_TASK": frozenset(
        ["create_gvl", "create_program", "create_function_block",
         "create_function", "create_dut", "create_task", "replace",
         "save_as"]),
    "W6_VERIFY_BUILD": frozenset(["build"]),
}

TODAS_AS_FASES = dict(FASES_ENCERRADAS)
FASES_ENCERRADAS.update(FASES_ENCERRADAS_DE_W6)
TODAS_AS_FASES.update(FASES_ENCERRADAS_DE_W6)

# ============================================================================
# O ESTADO ESPERADO MORA AQUI, e em mais lugar nenhum.
#
# `FASE_ATIVA` e o mapa acima sao literais escritos A MAO -- nada aqui e
# lido de `safety`, senao o arquivo passaria a concordar consigo mesmo.
# As assercoes de recusa DERIVAM deles, e por isso abrir ou encerrar uma
# fase custa duas linhas em vez de vinte asserts espalhados.
#
# `None` quando nenhuma fase esta aberta.
# ============================================================================
# W7 -- a fabrica com TUDO que esta provado. Uniao das allowlists de autoria
# de W1.4, W3, W5 e W6. Executada nas runs 034 e 035 e ENCERRADA (docs/47).
#
# Enquanto esteve ATIVA, ficou fora de `FASES_ENCERRADAS`: aquele dicionario e
# o registro do que ja foi fechado, e um teste percorre ele afirmando que
# nenhuma das entradas e a fase apontada. Agora que fechou, ela migra para la.
FASES_DE_W7 = {
    "W7_FACTORY_FULL": frozenset(
        ["create_gvl", "create_program", "create_function_block",
         "create_function", "create_dut", "replace", "save_as"]),
    "W7_VERIFY_BUILD": frozenset(["build"]),
}
FASES_ENCERRADAS.update(FASES_DE_W7)
TODAS_AS_FASES.update(FASES_DE_W7)

# W8 -- criar a task E dar-lhe o POU. Executada na run-036 e ENCERRADA
# (docs/48). Enquanto esteve ativa ficou fora de `FASES_ENCERRADAS`; agora
# migra para la, como toda fase que fecha.
FASES_DE_W8 = {
    "W8_PROVE_TASK_WITH_POU": frozenset(
        ["create_gvl", "create_program", "create_dut", "create_task", "add",
         "replace", "save_as"]),
    "W8_VERIFY_BUILD": frozenset(["build"]),
}
FASES_ENCERRADAS.update(FASES_DE_W8)
TODAS_AS_FASES.update(FASES_DE_W8)

# W9 -- a primeira fase a autorizar ESCRITA DE PROPRIEDADE. Executada na
# run-037 e ENCERRADA (docs/49).
FASES_DE_W9 = {
    "W9_PROVE_TASK_TIMING": frozenset(
        ["create_gvl", "create_program", "create_task", "add", "replace",
         "save_as", "set:kind_of_task", "set:interval", "set:interval_unit",
         "set:priority"]),
    "W9_VERIFY_BUILD": frozenset(["build"]),
}
FASES_ENCERRADAS.update(FASES_DE_W9)
TODAS_AS_FASES.update(FASES_DE_W9)

# W10 -- ALTERACAO DE OBJETO PREEXISTENTE (fase R2). A allowlist e a menor
# possivel: `replace` e `save_as`. A diferenca para W1_3A/W1_3B nao esta nos
# verbos -- esta em o alvo ser preexistente, e no executor conferir o hash
# anterior MEDIDO antes de sobrescrever.
FASES_DE_W10 = {
    "W10_EDIT_EXISTING": frozenset(["replace", "save_as"]),
    "W10_VERIFY_BUILD": frozenset(["build"]),
    # REVERSAO. Allowlist IDENTICA a da alteracao, e fases PROPRIAS: desfazer
    # usa o mesmo mecanismo com o mesmo rigor, mas nao e um detalhe da mesma
    # sessao que fez. Autorizada pela fase da alteracao, uma reversao poderia
    # rodar dentro dela, e "alterou e desfez" ficaria indistinguivel de
    # "alterou" no registro.
    "W10_REVERT": frozenset(["replace", "save_as"]),
    "W10_REVERT_VERIFY_BUILD": frozenset(["build"]),
}
TODAS_AS_FASES.update(FASES_DE_W10)

# --- R3.1B: a PRIMEIRA criacao de MEMBRO contra o produto (docs/87) ---------
#
# Tres fases, e a separacao entre elas e o desenho:
#
#   PROOF    cria o membro e persiste
#   VERIFY   so compila
#   REVERT   so desfaz -- allowlist MINIMA, e sem nenhum `create_*`
#
# Fase compartilhada entre criar e desfazer tornaria "criou e desfez"
# indistinguivel de "criou" no registro (docs/54).
FASES_DE_R3_1B = {
    "R3_1B_METHOD_PROOF": frozenset(["create_dut", "create_function_block",
                                     "create_method", "replace", "save_as"]),
    "R3_1B_VERIFY_BUILD": frozenset(["build"]),
    "R3_1B_METHOD_REVERT": frozenset(["object:remove", "save_as"]),
}
TODAS_AS_FASES.update(FASES_DE_R3_1B)

FASE_ATIVA = None

AUTORIZADAS_AGORA = (TODAS_AS_FASES[FASE_ATIVA] if FASE_ATIVA
                     else frozenset())


def esperado_recusar(operacao):
    """A operacao deve ser recusada no estado atual?

    So serve de prova de recusa o que a fase ATIVA nao autoriza -- uma
    operacao dentro da allowlist passaria pela fase, e nao pelo mapa, e o
    teste estaria medindo outra coisa.
    """
    return operacao not in AUTORIZADAS_AGORA


def recusa(operacao):
    """Afirma a recusa, ou pula quando a fase ativa autoriza."""
    if not esperado_recusar(operacao):
        return False
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed(operacao)
    return True


def test_a_fase_de_prova_esta_ENCERRADA_e_a_allowlist_dela_permanece():
    """Ela existe para resolver um ovo-e-galinha: o planner nao emite plano
    executavel com operacao nao provada, e sem executar nao ha prova.

    Escrever `create_function_block` nesta allowlist, a mao, E a decisao
    humana de que esta execucao existe para exercer aquela operacao. A
    alternativa -- marcar `field_proven` antes de medir -- seria declarar em
    vez de medir, o fail-open fechado em docs/42 secao 4."""
    assert safety.CONTROLLED_WRITE_PHASE == FASE_ATIVA
    assert safety.READ_ONLY_PHASE is True
    assert len(safety.PHASE_ALLOWED_OPERATIONS) == len(TODAS_AS_FASES)
    assert (safety.PHASE_ALLOWED_OPERATIONS["W5_PROVE_IEC_PACKAGE"]
            == frozenset(["create_gvl", "create_program",
                          "create_function_block", "create_function",
                          "replace", "save_as"]))
    for operacao in ("create_function_block", "create_function"):
        recusa(operacao)


def test_a_prova_e_a_fabrica_mais_os_DOIS_verbos_em_prova():
    """Nao e abertura ampla: e W4 mais exatamente os dois verbos que esta
    execucao existe para exercer."""
    fabrica = safety.PHASE_ALLOWED_OPERATIONS["W4_EXECUTE_PLAN"]
    prova = safety.PHASE_ALLOWED_OPERATIONS["W5_PROVE_IEC_PACKAGE"]
    assert prova - fabrica == frozenset(["create_function_block",
                                         "create_function"])


def test_create_dut_saiu_da_fase_de_prova_para_a_fabrica():
    """Ele ficou fora de TODAS as fases ate W6, por um motivo que se provou
    errado: docs/35 dizia que o enum `DutType` nao estava catalogado.

    A allowlist estava certa em nao antecipar o que ninguem sabia chamar --
    o que estava errado era o "ninguem sabia" (docs/45)."""
    com_dut = sorted(f for f, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
                     if "create_dut" in ops)
    assert com_dut == ["R3_1B_METHOD_PROOF",
                       "W6_PROVE_DUT_AND_TASK", "W7_FACTORY_FULL",
                       "W8_PROVE_TASK_WITH_POU"]
    recusa("create_dut")


def test_a_fabrica_completa_e_a_UNIAO_do_que_ja_foi_provado():
    """W7 nao alarga nada: ela e exatamente a uniao das allowlists de AUTORIA
    das fases que provaram cada verbo, sem `build`, sem `add` e sem
    `create_task`.

    Este teste e o que impede a fase da fabrica de virar a porta larga: se
    aparecer nela um verbo que nenhum marco provou, a igualdade quebra."""
    autoria = frozenset()
    for fase in ("W1_4_INTEGRATED_BUILD", "W3_IDIOMATIC_CALL",
                 "W5_PROVE_IEC_PACKAGE", "W6_PROVE_DUT_AND_TASK"):
        autoria = autoria | safety.PHASE_ALLOWED_OPERATIONS[fase]
    esperado = autoria - frozenset(["build", "add", "create_task"])
    assert safety.PHASE_ALLOWED_OPERATIONS["W7_FACTORY_FULL"] == esperado


def test_create_task_e_a_UNICA_operacao_do_vocabulario_fora_da_fabrica():
    """As doze operacoes do planner menos as que a fabrica autoriza, menos as
    que nao mutam e menos `build`/`add`: sobra `create_task`, e essa e a
    fronteira do que a fabrica sabe fazer hoje."""
    fabrica = safety.PHASE_ALLOWED_OPERATIONS["W7_FACTORY_FULL"]
    assert "create_task" not in fabrica
    assert "add" not in fabrica
    assert "build" not in fabrica


def test_a_autoria_da_fabrica_esta_ENCERRADA():
    assert (safety.PHASE_ALLOWED_OPERATIONS["W4_EXECUTE_PLAN"]
            == frozenset(["create_gvl", "create_program", "replace",
                          "save_as"]))
    assert safety.CONTROLLED_WRITE_PHASE != "W4_EXECUTE_PLAN"
    for operacao in ("create_gvl", "create_program", "replace", "save_as"):
        recusa(operacao)


def test_a_allowlist_da_fabrica_e_LITERAL_e_nao_derivada_do_plano():
    """A decisao que importa. O plano declara `required_allowlist`, e abrir
    a fase com o que ele pedir faria a fase deixar de autorizar coisa
    alguma -- o proprio pedido definiria a permissao.

    Este teste amarra a lista a um literal escrito a mao: acrescentar verbo
    obriga a editar o teste, e editar o teste e decisao humana."""
    assert (safety.PHASE_ALLOWED_OPERATIONS["W4_EXECUTE_PLAN"]
            == frozenset(["create_gvl", "create_program", "replace",
                          "save_as"]))


def test_a_fabrica_NAO_autoriza_build_nem_add_nem_os_nao_provados():
    """Cada ausencia com motivo: `build` tem fase propria; `add` e o
    caminho de W2, recusado como padrao; as quatro criacoes tem API
    catalogada e nenhuma foi exercida em cadeia que persistiu e compilou."""
    ativa = safety.PHASE_ALLOWED_OPERATIONS["W4_EXECUTE_PLAN"]
    for operacao in ("build", "add", "create_function_block",
                     "create_function", "create_dut", "create_task",
                     "save"):
        assert operacao not in ativa, operacao
        recusa(operacao)


def test_a_fabrica_e_a_uniao_de_w1_4_com_w3_menos_o_build():
    """Nao e abertura nova: e o que W1.4 e W3 ja provaram, sem `build`."""
    w1_4 = safety.PHASE_ALLOWED_OPERATIONS["W1_4_INTEGRATED_BUILD"]
    w3 = safety.PHASE_ALLOWED_OPERATIONS["W3_IDIOMATIC_CALL"]
    assert (safety.PHASE_ALLOWED_OPERATIONS["W4_EXECUTE_PLAN"]
            == (w1_4 | w3) - frozenset(["build"]))


def test_a_mutacao_de_w3_esta_ENCERRADA_e_a_allowlist_dela_permanece():
    """A allowlist de `W3_IDIOMATIC_CALL` e IDENTICA a de W1.3A e W1.3B, e
    isso e o ponto do marco: o verbo e o mesmo `replace` que W1.3B ja provou
    sobre um PROGRAM. O que W3 mede nao e a capacidade -- e ONDE a chamada
    mora."""
    assert (safety.PHASE_ALLOWED_OPERATIONS["W3_IDIOMATIC_CALL"]
            == frozenset(["replace", "save_as"]))
    assert (safety.PHASE_ALLOWED_OPERATIONS["W3_IDIOMATIC_CALL"]
            == safety.PHASE_ALLOWED_OPERATIONS["W1_3B_EDIT_PROGRAM"])
    assert safety.CONTROLLED_WRITE_PHASE != "W3_IDIOMATIC_CALL"
    for operacao in ("replace", "save_as"):
        recusa(operacao)


def test_w3_NAO_autoriza_add__que_e_o_que_o_fabricante_desaconselha():
    """`add` na `MainTask` e o que W2 fez e o que o aviso do fabricante
    desaconselha. Autoriza-lo em W3 apagaria a diferenca entre os dois marcos.

    W8 autoriza `add` de novo, e nao e contradicao: o aviso NOMEIA a
    `MainTask`, e W8 existe para a task que a spec CRIA -- outra task, outro
    receptor, e nenhuma POU de perfil no caminho."""
    assert "add" not in safety.PHASE_ALLOWED_OPERATIONS["W3_IDIOMATIC_CALL"]
    com_add = sorted(f for f, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
                     if "add" in ops)
    assert com_add == ["W2_BIND_PROGRAM_CALL", "W8_PROVE_TASK_WITH_POU",
                       "W9_PROVE_TASK_TIMING"]
    recusa("add")


def test_as_duas_fases_de_w3_nunca_estiveram_apontadas_juntas():
    """Verificar nao e autoria. As duas foram declaradas no mesmo commit,
    mas o ponteiro so aponta para uma de cada vez -- e a de verificacao nao
    escreve."""
    assert (safety.PHASE_ALLOWED_OPERATIONS["W3_VERIFY_BUILD"]
            == frozenset(["build"]))
    assert "save_as" not in safety.PHASE_ALLOWED_OPERATIONS["W3_VERIFY_BUILD"]
    assert "build" not in safety.PHASE_ALLOWED_OPERATIONS["W3_IDIOMATIC_CALL"]


def test_w1_4_foi_reaberta_e_encerrada_com_a_MESMA_allowlist():
    """A reabertura para medir determinismo (docs/40) nao deixou residuo.

    A allowlist e a MESMA da abertura original -- se ela tivesse mudado, nao
    seria a mesma fase, e a segunda execucao nao seria comparavel com a
    primeira: a spec autorizada teria mudado entre as duas."""
    assert (safety.PHASE_ALLOWED_OPERATIONS["W1_4_INTEGRATED_BUILD"]
            == frozenset(["create_gvl", "create_program", "replace",
                          "save_as", "build"]))
    assert safety.CONTROLLED_WRITE_PHASE != "W1_4_INTEGRATED_BUILD"
    for operacao in sorted(
            safety.PHASE_ALLOWED_OPERATIONS["W1_4_INTEGRATED_BUILD"]):
        recusa(operacao)


def test_w2_autorizou_exatamente_add_e_save_as():
    assert (safety.PHASE_ALLOWED_OPERATIONS["W2_BIND_PROGRAM_CALL"]
            == frozenset(["add", "save_as"]))
    # `add` nunca voltou a ser autorizado depois de W2; `save_as` depende da
    # fase ativa, e por isso passa pelo auxiliar.
    for operacao in ("add", "save_as"):
        recusa(operacao)


def test_verificar_teve_fase_PROPRIA_e_so_com_build():
    """`docs/38` separa mutar de verificar. Juntar `build` na allowlist de W2
    teria alargado a fase da MUTACAO para cobrir uma VERIFICACAO -- e
    verificar nao e autoria."""
    assert (safety.PHASE_ALLOWED_OPERATIONS["W2_VERIFY_BUILD"]
            == frozenset(["build"]))
    assert "build" not in safety.PHASE_ALLOWED_OPERATIONS["W2_BIND_PROGRAM_CALL"]
    assert "save_as" not in safety.PHASE_ALLOWED_OPERATIONS["W2_VERIFY_BUILD"]


def test_create_task_NAO_entrou_em_w2_e_create_task_configuration_em_nada():
    """MainTask ja existe: reutiliza-la reduziu a superficie mutavel de duas
    operacoes estruturais para uma, e por isso `create_task` so apareceu em
    W6, a fase que existe para prova-la.

    `create_task_configuration` continua fora de TUDO: a configuracao de
    tasks ja vem no template, e allowlist nao antecipa operacao que ninguem
    chama."""
    assert "create_task" not in safety.PHASE_ALLOWED_OPERATIONS[
        "W2_BIND_PROGRAM_CALL"]
    com_task = sorted(f for f, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
                      if "create_task" in ops)
    assert com_task == ["W6_PROVE_DUT_AND_TASK", "W8_PROVE_TASK_WITH_POU",
                        "W9_PROVE_TASK_TIMING"]
    for fase, operacoes in safety.PHASE_ALLOWED_OPERATIONS.items():
        assert "create_task_configuration" not in operacoes, fase
    recusa("create_task_configuration")


def test_os_vizinhos_de_add_na_MESMA_colecao_ficam_fora():
    """`ScriptPouObjectCollection` herda de `list`: `insert`, `remove` e
    `replace` moram na mesma colecao que `add`, e nenhum e chamado.
    Justamente por serem vizinhos e que precisam de teste nomeado."""
    for operacao in ("insert", "remove", "replace"):
        assert operacao not in safety.PHASE_ALLOWED_OPERATIONS[
            "W2_BIND_PROGRAM_CALL"]
    # Com a fase de VERIFICACAO ativa, os TRES discriminam.
    # `replace` esta autorizado pela fase de PROVA e passaria pelo motivo
    # errado.
    for operacao in ("insert", "remove"):
        with pytest.raises(safety.SafetyError):
            safety.assert_controlled_write_allowed(operacao)


def test_save_continua_FORA_mesmo_com_save_as_dentro():
    """A distincao decide se a testemunha do estado inicial sobrevive:
    `save_as` escreve em arquivo NOVO e deixa a entrada intacta -- medido em
    W1.3A; `save` sobrescreveria a copia de trabalho."""
    com_save_as = [f for f, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
                   if "save_as" in ops]
    assert len(com_save_as) >= 5, com_save_as
    # A afirmacao vale para o mapa INTEIRO, e nao para uma fase so: `save`
    # nunca esteve em allowlist alguma, em nenhum dos dez marcos.
    for fase, operacoes in safety.PHASE_ALLOWED_OPERATIONS.items():
        assert "save" not in operacoes, fase
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed("save")


def test_as_DUAS_fases_sem_save_as_e_por_que():
    """As unicas duas que nao persistem, e por motivos diferentes:

    W1.5 CRIA para ler e descarta a copia -- medir nao e autorizar a existir.
    W2_VERIFY_BUILD so COMPILA -- verificar nao e autoria.

    As outras seis persistem. Sem esta segunda metade, a ausencia nas duas
    poderia ser descuido em vez de escolha."""
    sem_persistencia = sorted(
        fase for fase, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
        if "save_as" not in ops)
    assert sem_persistencia == ["R3_1B_VERIFY_BUILD",
                                "W10_REVERT_VERIFY_BUILD",
                                "W10_VERIFY_BUILD", "W1_5_MEASURE_IEC_BIRTH",
                                "W2_VERIFY_BUILD",
                                "W3_VERIFY_BUILD", "W4_VERIFY_BUILD",
                                "W5_VERIFY_BUILD", "W6_VERIFY_BUILD",
                                "W7_VERIFY_BUILD", "W8_VERIFY_BUILD",
     "W9_VERIFY_BUILD"]
    for fase, ops in safety.PHASE_ALLOWED_OPERATIONS.items():
        assert "save" not in ops, fase


def test_create_dut_entrou_na_prova_e_depois_na_fabrica():
    """Ele ficou de fora de TUDO ate W6 por falta de catalogo -- e o catalogo
    que faltava era o DESTE PROJETO, nao o do produto: o enum `DutType` estava
    no stub o tempo todo, e a run-031 (docs/45) mediu que ele e injetado no
    escopo do script.

    A regra continua valendo: allowlist nao antecipa API que ninguem sabe
    chamar. O que mudou foi o "ninguem sabe"."""
    com_dut = sorted(f for f, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
                     if "create_dut" in ops)
    assert com_dut == ["R3_1B_METHOD_PROOF",
                       "W6_PROVE_DUT_AND_TASK", "W7_FACTORY_FULL",
                       "W8_PROVE_TASK_WITH_POU"]
    recusa("create_dut")


def test_fase_ausente_recusa_TODA_mutacao(monkeypatch):
    """O fechamento tem de continuar funcionando com a fase ABERTA -- e assim
    que W1.4 sera encerrada."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", None)
    for operacao in sorted(safety.MASTERTOOL_MUTATING_OPERATIONS):
        with pytest.raises(safety.SafetyError):
            safety.assert_controlled_write_allowed(operacao)


def test_todas_as_fases_ficam_no_registro():
    """Apagar uma entrada apagaria a evidencia de que a fase existiu. Estar no
    mapa nao autoriza nada -- quem autoriza e o ponteiro."""
    for fase, operacoes in TODAS_AS_FASES.items():
        assert safety.PHASE_ALLOWED_OPERATIONS[fase] == operacoes


def test_w1_3a_e_w1_3b_tem_a_MESMA_allowlist():
    """Nao e descuido: o verbo autorizado e o mesmo nas duas, o que muda e
    quantos documentos o recebem -- um na GVL, dois no PROGRAM. A allowlist
    diz QUE VERBO esta autorizado, nunca quantas vezes; contagem foi trabalho
    do probe e do artefato. Este teste existe para que a diferenca fique
    escrita, e nao apenas subentendida."""
    assert (safety.PHASE_ALLOWED_OPERATIONS["W1_3A_EDIT_GVL"]
            == safety.PHASE_ALLOWED_OPERATIONS["W1_3B_EDIT_PROGRAM"])


def test_o_mapa_nao_tem_fase_alem_das_declaradas():
    """Se uma fase nova entrar no mapa sem passar por aqui, ela existiria sem
    ninguem ter declarado que existe. W1_4 ainda NAO existe."""
    assert set(safety.PHASE_ALLOWED_OPERATIONS) == set(TODAS_AS_FASES)


def test_o_nome_alternativo_de_w1_4_NAO_existe():
    """`docs/32` chamou a fase de `W1_4_INTEGRATED_AUTHORING` antes de os
    instrumentos fixarem `W1_4_INTEGRATED_BUILD`. Dois nomes para a mesma fase
    seriam duas portas, e a segunda envelheceria em silencio."""
    assert "W1_4_INTEGRATED_AUTHORING" not in safety.PHASE_ALLOWED_OPERATIONS
    recusa("create_task")


def test_build_so_aparece_nas_SETE_fases_que_o_declararam():
    """Ele esteve no registro de mutaveis desde b8ad7bb e nunca em allowlist
    alguma. Este teste guarda a exclusividade: se `build` aparecer em qualquer
    outra fase, alguem o autorizou sem dizer."""
    assert "build" in safety.MASTERTOOL_MUTATING_OPERATIONS
    com_build = sorted(f for f, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
                       if "build" in ops)
    assert com_build == ["R3_1B_VERIFY_BUILD",
                         "W10_REVERT_VERIFY_BUILD",
                         "W10_VERIFY_BUILD", "W1_4_INTEGRATED_BUILD",
                         "W2_VERIFY_BUILD",
                         "W3_VERIFY_BUILD", "W4_VERIFY_BUILD",
                         "W5_VERIFY_BUILD", "W6_VERIFY_BUILD",
                         "W7_VERIFY_BUILD", "W8_VERIFY_BUILD",
     "W9_VERIFY_BUILD"]
    recusa("build")


def test_estar_no_mapa_nao_basta_para_autorizar():
    """Estar no mapa nao autoriza: quem autoriza e o ponteiro.

    As DEZ entradas continuam no mapa como registro historico de qual
    allowlist esteve ativa em cada marco, e NENHUMA esta apontada. Foi essa
    disciplina -- encerrar sem apagar -- que tornou possivel reabrir W1.4 e
    medir determinismo sem reescrever autorizacao (docs/40)."""
    for encerrada in FASES_ENCERRADAS:
        assert encerrada in safety.PHASE_ALLOWED_OPERATIONS
        assert encerrada != safety.CONTROLLED_WRITE_PHASE
    # So as operacoes FORA da allowlist ativa servem de prova: as que estao
    # dentro passariam pela fase aberta, e nao pelo mapa.
    for encerrada, operacoes in FASES_ENCERRADAS.items():
        for operacao in sorted(operacoes):
            recusa(operacao)



@pytest.mark.parametrize("fase,operacao", [
    ("W1_1_CREATE_GVL", "create_gvl"),
    ("W1_2_CREATE_PROGRAM", "create_program"),
    ("W1_3A_EDIT_GVL", "replace"),
])
def test_apontar_uma_fase_autoriza_so_a_dela(monkeypatch, fase, operacao):
    """Trocar o ponteiro troca a allowlist inteira -- nunca acumula. `save_as`
    e comum as tres e por isso nao serve de discriminante: o que discrimina e
    a operacao propria de cada fase."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", fase)
    assert safety.assert_controlled_write_allowed(operacao) is True
    assert safety.assert_controlled_write_allowed("save_as") is True
    proprias = {"W1_1_CREATE_GVL": "create_gvl",
                "W1_2_CREATE_PROGRAM": "create_program",
                "W1_3A_EDIT_GVL": "replace"}
    for outra_fase, outra_operacao in proprias.items():
        if outra_fase == fase:
            continue
        with pytest.raises(safety.SafetyError):
            safety.assert_controlled_write_allowed(outra_operacao)


def test_read_only_phase_permanece_true():
    """Abrir e fechar a fase de escrita controlada nunca mexeu no booleano
    geral: ele esteve True o tempo todo, inclusive DURANTE a run-008, e as sete
    operacoes legadas seguem bloqueadas. Foi exatamente para evitar
    `READ_ONLY_PHASE = False` que a fase nomeada existe."""
    assert safety.READ_ONLY_PHASE is True
    for operacao in safety.WRITE_OPERATIONS:
        with pytest.raises(safety.SafetyError):
            safety.assert_operation_allowed(operacao)


# --- tudo o mais continua proibido ------------------------------------------

# A lista nomeia cada operacao em vez de confiar so na iteracao sobre o
# registro: se o registro encolher por engano, a iteracao encolhe junto e nao
# reclama; a lista literal reclama.
# O REGISTRO CONGELADO das operacoes mutaveis, a mao. Ele existe para que
# uma API nova entrando em `MASTERTOOL_MUTATING_OPERATIONS` obrigue um
# humano a edita-lo -- sem isso ela deixaria de ser testada em silencio, e
# a lista pareceria completa sem ser. Foi assim que quatro APIs de
# dispositivo apareceram, presentes no registro desde b8ad7bb e nunca
# verificadas.
#
# A RECUSA de cada uma e conferida so quando a fase ativa nao a autoriza
# (ver `recusa`), e por isso esta lista nao muda quando uma fase abre.
REGISTRO_CONGELADO = [
    "add",
    "create_pou", "create_function",
    "create_function_block", "create_dut", "create_interface",
    "create_persistentvars", "create_folder",
    "create_task", "create_task_configuration", "create_boot_application",
    # R3.1B (docs/87): MEMBRO de POU. Os irmãos (`create_property`,
    # `create_action`, `create_transition`) ficam FORA — estar na mesma
    # interface não os torna escopo, e uma allowlist que cresce por vizinhança
    # deixa de descrever o que está em uso.
    "create_method",
    # `remove` FOI DIVIDIDO no R3.1B (docs/87 §4). O nome nu era identidade
    # insuficiente: `IScriptTextDocument.remove(offset, length)` apaga
    # caracteres e `IScriptObject.remove()` apaga o nó da árvore. A allowlist é
    # por nome, então autorizar o primeiro autorizava o segundo.
    "replace_line", "insert", "append",
    "text:remove", "object:remove",
    "save", "save_archive", "rebuild", "clean",
    "import_xml", "import_native", "import_device", "rename", "move",
    "unplug", "update", "set_gateway_and_ip_address", "remove_device",
    "set_compilerversion_to_newest", "download_missing_libraries",
    "remove_library", "add_library",
    # As quatro abaixo estavam no registro de mutaveis desde o commit b8ad7bb e
    # NUNCA apareceram nesta lista: ninguem verificava que elas eram recusadas.
    # Foram descobertas pelo teste logo abaixo, na primeira vez que ele rodou.
    "import_vendor_description", "import_io_mappings_from_csv",
    "remove_vendor_description", "save_device_cache",
    # As de autoria, que varias fases ja autorizaram e que voltam a ser
    # recusadas sempre que a fase que as autorizava e encerrada.
    "create_gvl", "create_program", "create_function_block",
    "create_function", "create_dut", "create_task", "replace", "save_as",
    "build",
]


def test_o_registro_congelado_cobre_o_registro_INTEIRO():
    """Guarda da propria lista acima: se uma API nova entrar no registro de
    mutaveis e ninguem a acrescentar aqui, ela deixaria de ser testada em
    silencio -- e a lista pareceria completa sem ser. Foi assim que quatro APIs
    de dispositivo apareceram, presentes no registro desde b8ad7bb e nunca
    verificadas.

    A lista e do REGISTRO inteiro, e nao do que esta proibido agora: ela
    nao muda quando uma fase abre, e por isso nao precisa ser reescrita a
    cada marco."""
    assert set(REGISTRO_CONGELADO) == set(
        safety.MASTERTOOL_MUTATING_OPERATIONS)


@pytest.mark.parametrize("operacao", REGISTRO_CONGELADO)
def test_operacao_fora_da_allowlist_falha(operacao):
    """Toda operacao do registro que a fase ATIVA nao autoriza e recusada.

    As que ela autoriza sao puladas -- exigir recusa delas seria exigir que o
    gate contradissesse a fase que alguem acabou de abrir a mao."""
    if not recusa(operacao):
        pytest.skip("autorizada pela fase ativa %r" % (FASE_ATIVA,))


@pytest.mark.parametrize("operacao", [
    "go_online", "download_to_plc", "force_variables",
    "change_hardware_configuration", "apply_ai_changes_to_official_project",
])
def test_proibicao_permanente_continua_valendo(operacao):
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed(operacao)
    with pytest.raises(safety.SafetyError):
        safety.assert_operation_allowed(operacao)


# --- fail-closed: desconhecido nunca passa ----------------------------------

@pytest.mark.parametrize("operacao", [
    "create_gvl_extra",      # sufixo
    "create_",               # prefixo
    "create",                # fragmento
    "*",                     # curinga
    "create_*",              # curinga com prefixo
    "CREATE_GVL",            # caixa diferente
    "Create_Gvl",
    " create_gvl",           # espaco a esquerda
    "create_gvl ",           # espaco a direita
    "save_as_novo",
    "operacao_que_nao_existe",
])
def test_nome_desconhecido_ou_parcial_falha_fechado(operacao):
    """Sem curinga, sem prefixo, sem correspondencia parcial, sem caixa
    flexivel: a comparacao e por igualdade exata."""
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed(operacao)


@pytest.mark.parametrize("valor", [None, "", 0, 1, True, [], {}, ["create_gvl"]])
def test_argumento_que_nao_e_texto_falha_fechado(valor):
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed(valor)


def test_fase_none_bloqueia_tudo(monkeypatch):
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", None)
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed("create_gvl")


@pytest.mark.parametrize("fase", ["", "W1_2", "w1_1_create_gvl", "QUALQUER"])
def test_fase_desconhecida_bloqueia_tudo(monkeypatch, fase):
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", fase)
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed("create_gvl")


def test_configuracao_incompleta_bloqueia(monkeypatch):
    """Fase declarada mas sem allowlist correspondente: falha fechado, nunca
    'sem restricao'."""
    monkeypatch.setattr(safety, "PHASE_ALLOWED_OPERATIONS", {})
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed("create_gvl")


# --- porta unica ------------------------------------------------------------

@pytest.mark.parametrize("operacao", ["create_gvl", "save_as", "build", "replace"])
def test_guarda_legada_nunca_libera_operacao_do_mastertool_x(operacao):
    """Antes deste slice, assert_operation_allowed devolvia True para TODOS
    estes nomes -- ela so conhecia os sete legados e falhava aberta no resto.
    Agora desvia para a porta unica, inclusive para os dois autorizados."""
    with pytest.raises(safety.SafetyError):
        safety.assert_operation_allowed(operacao)


def test_guarda_legada_preserva_comportamento_das_operacoes_antigas():
    """Probes read-only nao podem mudar de comportamento por causa deste
    slice."""
    for operacao in safety.WRITE_OPERATIONS:
        with pytest.raises(safety.SafetyError):
            safety.assert_operation_allowed(operacao)
    for operacao in ["list_project_tree", "read_declaration", "export_xml_read_only"]:
        assert safety.assert_operation_allowed(operacao) is True


# --- invariantes estruturais do registro ------------------------------------

def test_allowlist_e_subconjunto_do_registro_de_mutaveis():
    """Autorizar nome que nao esta em registro nenhum seria autorizar algo que
    a porta recusa depois -- contradicao silenciosa.

    Sao DOIS registros desde W9, e a uniao nao afrouxa: eles sao disjuntos, e
    o laco de dentro exige que cada nome caia em exatamente um. O registro em
    que o nome mora tambem decide QUAL porta o confere."""
    conhecidos = (safety.MASTERTOOL_MUTATING_OPERATIONS
                  | safety.MASTERTOOL_PROPERTY_WRITES)
    for fase, operacoes in safety.PHASE_ALLOWED_OPERATIONS.items():
        assert operacoes <= conhecidos, fase
        for nome in operacoes:
            metodo = nome in safety.MASTERTOOL_MUTATING_OPERATIONS
            propriedade = nome in safety.MASTERTOOL_PROPERTY_WRITES
            assert metodo != propriedade, (fase, nome)


def test_registro_nao_contem_curinga_nem_padrao():
    for operacao in safety.MASTERTOOL_MUTATING_OPERATIONS:
        assert "*" not in operacao
        assert "?" not in operacao
        assert operacao == operacao.strip()
        assert operacao == operacao.lower()


def test_registro_cobre_as_apis_catalogadas_para_w1():
    """As seis APIs da allowlist do plano W1 (docs/29) precisam existir no
    registro, ou o gate nao teria o que bloquear nas fases seguintes."""
    for operacao in ["create_gvl", "create_program", "create_pou", "replace",
                     "save_as", "build"]:
        assert operacao in safety.MASTERTOOL_MUTATING_OPERATIONS


def test_resumo_sem_fase_declara_zero_e_nao_omite(monkeypatch):
    """Manifesto que cala sobre autorizacao nao serve de evidencia: sem fase, o
    resumo diz `None` e lista vazia, em vez de omitir os campos."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", None)
    resumo = safety.controlled_write_summary()
    assert resumo["controlled_write_phase"] is None
    assert resumo["allowed_operations"] == []
    assert resumo["read_only_phase"] is True
    assert resumo["mutating_operations_known"] == len(
        safety.MASTERTOOL_MUTATING_OPERATIONS)


def test_resumo_REAL_declara_a_fase_ATIVA_sem_monkeypatch():
    """Sem monkeypatch de proposito: o que vai para o manifesto e o estado
    REAL do modulo, nao um estado simulado no teste. Um manifesto que
    declarasse fase diferente da que a porta usa seria evidencia de outra
    coisa que nao a execucao."""
    resumo = safety.controlled_write_summary()
    assert resumo["controlled_write_phase"] == FASE_ATIVA
    assert resumo["allowed_operations"] == sorted(AUTORIZADAS_AGORA)
    assert resumo["read_only_phase"] is True


@pytest.mark.parametrize("fase", sorted(TODAS_AS_FASES))
def test_resumo_de_fase_encerrada_recupera_a_allowlist_dela(monkeypatch, fase):
    """Prova que as fases encerradas foram DESATIVADAS e nao quebradas:
    reapontar o ponteiro devolve exatamente a allowlist de cada uma."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", fase)
    resumo = safety.controlled_write_summary()
    assert resumo["controlled_write_phase"] == fase
    assert resumo["allowed_operations"] == sorted(TODAS_AS_FASES[fase])


def test_resumo_declara_a_fase_quando_ha_uma(monkeypatch):
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", "W1_2_CREATE_PROGRAM")
    resumo = safety.controlled_write_summary()
    assert resumo["controlled_write_phase"] == "W1_2_CREATE_PROGRAM"
    assert resumo["allowed_operations"] == ["create_program", "save_as"]


def test_resumo_nao_expoe_allowlist_mutavel(monkeypatch):
    """Copia defensiva: quem le o resumo nao altera a allowlist por
    referencia."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", "W1_1_CREATE_GVL")
    resumo = safety.controlled_write_summary()
    assert resumo["allowed_operations"] == ["create_gvl", "save_as"]
    resumo["allowed_operations"].append("build")
    assert safety.PHASE_ALLOWED_OPERATIONS["W1_1_CREATE_GVL"] == frozenset(
        ["create_gvl", "save_as"])


# --- a OUTRA porta: escrita de propriedade -----------------------------------
#
# Ela nasceu da run-036 (docs/48): a task criada veio com `t#20ms` e prioridade
# 1, e o gate nao tinha como autorizar a correcao -- nem como recusa-la, o que
# e pior. `task.interval = x` nao era bloqueado; era INVISIVEL.

REGISTRO_DE_PROPRIEDADES = frozenset([
    "set:kind_of_task", "set:interval", "set:interval_unit", "set:priority",
])


def test_o_registro_de_propriedades_e_LITERAL_e_prefixado():
    """Prefixo `set:` em TODAS, sem excecao: e ele que impede um nome de campo
    de se confundir com um nome de metodo dentro da mesma allowlist."""
    assert safety.MASTERTOOL_PROPERTY_WRITES == REGISTRO_DE_PROPRIEDADES
    for nome in safety.MASTERTOOL_PROPERTY_WRITES:
        assert nome.startswith("set:"), nome
        assert nome.count(":") == 1, nome


def test_as_duas_classes_de_mutacao_NAO_se_misturam():
    """Registros disjuntos, e a interseccao vazia e o teste.

    Se um nome vivesse nos dois, a allowlist de uma fase deixaria de dizer qual
    das duas coisas foi autorizada -- e a guarda de uma nao enxerga a outra."""
    assert not (safety.MASTERTOOL_PROPERTY_WRITES
                & safety.MASTERTOOL_MUTATING_OPERATIONS)
    for nome in safety.MASTERTOOL_MUTATING_OPERATIONS:
        assert not nome.startswith("set:"), nome


def test_propriedade_fora_do_registro_falha_FECHADO(monkeypatch):
    """`watchdog` e `event` sao settable no stub e NAO estao no registro. Uma
    fase que os autorizasse ainda assim seria recusada aqui -- o registro vem
    antes da allowlist, como na porta de metodos."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", "FASE_FICTICIA")
    monkeypatch.setitem(safety.PHASE_ALLOWED_OPERATIONS, "FASE_FICTICIA",
                        frozenset(["set:event", "set:core_binding"]))
    for nome in ("set:event", "set:core_binding", "set:watchdog"):
        with pytest.raises(safety.SafetyError):
            safety.assert_controlled_property_write_allowed(nome)


def test_propriedade_sem_prefixo_e_recusada(monkeypatch):
    """O nome cru do campo nao serve, mesmo estando a fase aberta: e o formato
    que distingue as duas classes."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", "FASE_FICTICIA")
    monkeypatch.setitem(safety.PHASE_ALLOWED_OPERATIONS, "FASE_FICTICIA",
                        frozenset(["set:interval", "interval"]))
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_property_write_allowed("interval")
    assert safety.assert_controlled_property_write_allowed("set:interval")


@pytest.mark.parametrize("entrada", [None, "", 0, [], {}, True, "SET:INTERVAL"])
def test_entrada_degenerada_na_porta_de_propriedade(entrada):
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_property_write_allowed(entrada)


def test_a_escrita_de_propriedade_so_passa_pela_fase_QUE_A_NOMEIA():
    """Este teste ja afirmou que NENHUMA propriedade passava, porque nenhuma
    fase as autorizava. W9 autoriza as quatro, e o que ele guarda agora e de
    ONDE veio a autorizacao -- se um dia vier de outra fase, isto reprova."""
    for nome in sorted(safety.MASTERTOOL_PROPERTY_WRITES):
        if nome in AUTORIZADAS_AGORA:
            assert FASE_ATIVA == "W9_PROVE_TASK_TIMING", FASE_ATIVA
            assert safety.assert_controlled_property_write_allowed(nome)
        else:
            with pytest.raises(safety.SafetyError):
                safety.assert_controlled_property_write_allowed(nome)


def test_SO_a_fase_de_W9_autoriza_escrita_de_propriedade():
    """As dezoito fases anteriores sao todas mais velhas que esta classe de
    mutacao, e nenhuma delas pode ganhar `set:` por acidente."""
    com_propriedade = sorted(
        fase for fase, ops in safety.PHASE_ALLOWED_OPERATIONS.items()
        if ops & safety.MASTERTOOL_PROPERTY_WRITES)
    assert com_propriedade == ["W9_PROVE_TASK_TIMING"]
    # E a fase que as autoriza autoriza as QUATRO -- nem mais, nem menos.
    assert (safety.PHASE_ALLOWED_OPERATIONS["W9_PROVE_TASK_TIMING"]
            & safety.MASTERTOOL_PROPERTY_WRITES
            == safety.MASTERTOOL_PROPERTY_WRITES)


def test_o_resumo_conta_as_duas_classes():
    resumo = safety.controlled_write_summary()
    assert resumo["property_writes_known"] == len(REGISTRO_DE_PROPRIEDADES)
    assert resumo["mutating_operations_known"] == len(
        safety.MASTERTOOL_MUTATING_OPERATIONS)
