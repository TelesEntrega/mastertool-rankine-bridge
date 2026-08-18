"""Política de cobertura de análise — as sete perguntas obrigatórias.

O QUE ESTES TESTES DEFENDEM
===========================
1. **Entrada ausente vira `not_applicable` com motivo**, nunca "nenhum
   achado". Um relatório que diz zero porque não olhou é pior que não ter
   relatório.
2. **A política relata e nunca reprova.** Múltiplos escritores é fato do
   projeto; `read_never_written` pode ser hardware.
3. **A camada é a RESOLVIDA**, não a heurística de `analysis/`.

Fixtures sintéticas.
"""

from __future__ import annotations

import json

import pytest

from mastertool_bridge.coverage.policy import (
    INPUT_CODE,
    INPUT_PLANT,
    MEASURED,
    NATURES,
    NOT_APPLICABLE,
    QUESTIONS,
    analyse_coverage,
)
from mastertool_bridge.plant.control_points import ingest_rows


def _inventario(linhas=None):
    cabecalho = {"B": "ITEM", "C": "TAG", "D": "DESCRICAO", "E": "LOCALIZACAO",
                 "F": "ED", "G": "SD", "H": "EDS", "I": "SDS"}
    corpo = linhas if linhas is not None else [
        {"B": "ESTEIRA"},
        {"B": "1", "C": "MOT1", "D": "motor", "G": "1"},     # saída
        {"B": "2", "C": "SEN1", "D": "sensor", "F": "1"},    # entrada
    ]
    return ingest_rows([cabecalho, *corpo], document="inv.xlsx", version="V1")


class _View:
    """Dublê da visão resolvida. Só o contrato que a política consome."""

    def __init__(self, readers=None, writers=None, calls=()):
        self._r = readers or {}
        self._w = writers or {}
        self._calls = list(calls)

    def readers(self, s):
        return self._r.get(s, [])

    def writers(self, s):
        return self._w.get(s, [])

    def symbols(self):
        return sorted(set(self._r) | set(self._w))

    def multi_writers(self):
        return {s: f for s, f in self._w.items() if len(f) > 1}


def _fato(lang="LD", net="net:0001"):
    return {"source_language": lang, "network_id": net, "element_id": "el:1"}


# =============================================================================
# degradação honesta
# =============================================================================

def test_sem_entrada_a_pergunta_e_NOT_APPLICABLE_com_motivo() -> None:
    """Nunca "nenhum achado": um relatório que diz zero porque não olhou é
    pior que não ter relatório."""
    r = analyse_coverage(view=None, plant=None)
    assert all(q.state == NOT_APPLICABLE for q in r.questions)
    for q in r.questions:
        assert q.reason and "entrada ausente" in q.reason
        assert "não é o mesmo que não ter achado nada" in q.reason
        assert q.findings == []
    assert r.complete is False
    assert r.summary()["answered"] == 0


def test_so_com_codigo_responde_o_que_depende_SO_de_codigo() -> None:
    r = analyse_coverage(view=_View(writers={"A": [_fato()]}))
    por_chave = {q.key: q for q in r.questions}
    assert por_chave["multiple_writers"].state == MEASURED
    assert por_chave["written_never_read"].state == MEASURED
    assert por_chave["actuator_without_writer"].state == NOT_APPLICABLE
    assert INPUT_PLANT in por_chave["actuator_without_writer"].reason


def test_so_com_inventario_responde_o_que_depende_SO_de_inventario() -> None:
    r = analyse_coverage(plant=_inventario())
    por_chave = {q.key: q for q in r.questions}
    assert por_chave["safety_excluded_from_generation"].state == MEASURED
    assert por_chave["multiple_writers"].state == NOT_APPLICABLE
    assert INPUT_CODE in por_chave["multiple_writers"].reason


def test_complete_e_DERIVADO() -> None:
    assert analyse_coverage(view=_View(), plant=_inventario()).complete is True
    assert analyse_coverage(view=_View()).complete is False


# =============================================================================
# as perguntas
# =============================================================================

def test_acionamento_sem_escritor_e_detectado() -> None:
    """Uma saída física sem escritor pode existir por anos sem ninguém saber,
    porque a consulta depende de alguém lembrar de rodá-la."""
    r = analyse_coverage(view=_View(), plant=_inventario())
    q = next(x for x in r.questions if x.key == "actuator_without_writer")
    assert [f.subject for f in q.findings] == ["MOT1"]


def test_entrada_sem_escritor_NAO_e_achado() -> None:
    """Ela vem do campo. Só SAÍDA é acionamento."""
    r = analyse_coverage(view=_View(), plant=_inventario())
    q = next(x for x in r.questions if x.key == "actuator_without_writer")
    assert "SEN1" not in {f.subject for f in q.findings}


def test_acionamento_COM_escritor_nao_aparece() -> None:
    r = analyse_coverage(view=_View(writers={"MOT1": [_fato()]}),
                         plant=_inventario())
    q = next(x for x in r.questions if x.key == "actuator_without_writer")
    assert q.findings == []


def test_multiplos_escritores_e_FATO_e_nao_defeito() -> None:
    vista = _View(writers={"S": [_fato(net="net:1"), _fato(net="net:2")]})
    r = analyse_coverage(view=vista)
    q = next(x for x in r.questions if x.key == "multiple_writers")
    assert q.nature == "fact"
    assert [f.subject for f in q.findings] == ["S"]
    assert "FATO do projeto" in q.findings[0].detail


def test_escrito_nunca_lido_e_lido_nunca_escrito() -> None:
    vista = _View(readers={"LIDO": [_fato()]},
                  writers={"ESCRITO": [_fato()]})
    r = analyse_coverage(view=vista)
    por_chave = {q.key: q for q in r.questions}
    assert [f.subject for f in por_chave["written_never_read"].findings] == ["ESCRITO"]
    assert [f.subject for f in por_chave["read_never_written"].findings] == ["LIDO"]


def test_lido_nunca_escrito_e_CONTEXTO_e_nao_diagnostico() -> None:
    """Pode ser entrada de hardware ou variável de comunicação."""
    q = next(x for x in analyse_coverage(
        view=_View(readers={"E": [_fato()]})).questions
        if x.key == "read_never_written")
    assert q.nature == "context"
    assert "entrada de hardware" in q.findings[0].detail


def test_simbolo_com_leitura_E_escrita_nao_aparece_em_nenhuma_das_duas() -> None:
    vista = _View(readers={"OK": [_fato()]}, writers={"OK": [_fato()]})
    r = analyse_coverage(view=vista)
    for chave in ("written_never_read", "read_never_written"):
        q = next(x for x in r.questions if x.key == chave)
        assert q.findings == []


def test_ponto_do_inventario_ausente_da_logica() -> None:
    r = analyse_coverage(view=_View(readers={"SEN1": [_fato()]}),
                         plant=_inventario())
    q = next(x for x in r.questions
             if x.key == "inventory_point_absent_from_logic")
    assert [f.subject for f in q.findings] == ["MOT1"]


def test_seguranca_segregada_e_afirmacao_POSITIVA() -> None:
    """A pergunta é respondida mesmo sem achado: "todos fora da geração" é a
    resposta, e ela precisa aparecer."""
    inv = _inventario([{"B": "P"},
                       {"B": "1", "C": "BS1", "D": "barreira", "H": "1"}])
    q = next(x for x in analyse_coverage(plant=inv).questions
             if x.key == "safety_excluded_from_generation")
    assert q.state == MEASURED
    assert q.findings and "todos fora da geração" in q.findings[0].detail


def test_seguranca_dentro_da_geracao_seria_ACHADO() -> None:
    """Controle negativo: se a segregação quebrar, a pergunta acusa."""
    inv = _inventario([{"B": "P"},
                       {"B": "1", "C": "BS1", "D": "barreira", "H": "1"}])
    q = next(x for x in analyse_coverage(plant=inv).questions
             if x.key == "safety_excluded_from_generation")
    seguros = {p.tag for p in inv.safety_points()}
    geraveis = {p.tag for p in inv.generable_points()}
    assert seguros and not (seguros & geraveis), (
        "a segregação é o que a pergunta verifica; se ela cair, o teste do "
        "modelo cai antes")


def test_nao_resolvido_COM_categoria_nao_e_achado() -> None:
    """A pergunta não é "há não-resolvidos?" — é "estão categorizados?"."""
    class _Chamada:
        resolution_status = "unresolved"
        unresolved_category = "symbol_not_found"
        target_text = "TON"

    vista = _View(calls=[_Chamada()])
    q = next(x for x in analyse_coverage(view=vista).questions
             if x.key == "unresolved_references_categorised")
    assert q.findings == []


def test_nao_resolvido_SEM_categoria_e_achado() -> None:
    class _Chamada:
        resolution_status = "unresolved"
        unresolved_category = None
        target_text = "XPTO"

    vista = _View(calls=[_Chamada()])
    q = next(x for x in analyse_coverage(view=vista).questions
             if x.key == "unresolved_references_categorised")
    assert [f.subject for f in q.findings] == ["XPTO"]
    assert q.nature == "limitation"


# =============================================================================
# a política relata, nunca reprova
# =============================================================================

def test_a_CLI_sai_0_mesmo_com_achados(tmp_path) -> None:
    """Reprovar por múltiplos escritores transformaria qualquer CI num alarme
    falso permanente, até alguém desligar a verificação inteira."""
    import contextlib
    import io
    from pathlib import Path

    from mastertool_bridge.cli import main

    fixture = (Path(__file__).resolve().parents[1] / "fixtures" / "plcopen"
               / "ladder_sample.xml")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        codigo = main(["coverage-report", "--ladder", str(fixture)])
    dados = json.loads(buf.getvalue())
    assert codigo == 0
    assert dados["summary"]["findings_by_nature"], "houve achados"


def test_a_CLI_sai_diferente_de_0_quando_NAO_ha_entrada() -> None:
    """Sai != 0 apenas quando a ANÁLISE não rodou."""
    import contextlib
    import io

    from mastertool_bridge.cli import main

    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        assert main(["coverage-report"]) != 0


# =============================================================================
# forma e determinismo
# =============================================================================

def test_sao_SETE_perguntas_e_a_lista_e_FECHADA() -> None:
    assert len(QUESTIONS) == 7
    chaves = {q[0] for q in QUESTIONS}
    assert chaves == {
        "actuator_without_writer", "multiple_writers", "written_never_read",
        "read_never_written", "inventory_point_absent_from_logic",
        "unresolved_references_categorised", "safety_excluded_from_generation"}


def test_toda_pergunta_declara_natureza_e_entradas() -> None:
    for chave, texto, natureza, exige in QUESTIONS:
        assert natureza in NATURES, chave
        assert exige, "%s não declara de que entrada depende" % chave
        assert texto.endswith("?"), chave


def test_a_serializacao_e_DETERMINISTICA() -> None:
    kw = dict(view=_View(readers={"A": [_fato()]},
                         writers={"B": [_fato(), _fato(net="n2")]}),
              plant=_inventario())
    assert (json.dumps(analyse_coverage(**kw).to_dict(), sort_keys=True)
            == json.dumps(analyse_coverage(**kw).to_dict(), sort_keys=True))


def test_a_politica_NAO_usa_a_camada_heuristica() -> None:
    """`analysis/safety_checks.py` casa texto e marca `heuristic: True` em
    todo achado. Esta política existe justamente para levar as mesmas
    perguntas para a camada resolvida.

    A guarda é de **AST**, e não de texto: o módulo CITA a camada heurística
    na própria docstring, para explicar por que existe. Proibir a menção
    proibiria a explicação — e foi exatamente esse o erro na primeira versão
    deste teste.
    """
    import ast
    from pathlib import Path

    fonte = (Path(__file__).resolve().parents[2] / "src" / "mastertool_bridge"
             / "coverage" / "policy.py")
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))

    proibidos = {"safety_checks", "reference_finder"}
    funcoes = {"find_in_text", "filter_writes", "filter_reads",
               "find_references"}

    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module:
            assert not any(p in no.module for p in proibidos), no.module
            for alias in no.names:
                assert alias.name not in funcoes, alias.name
        elif isinstance(no, ast.Import):
            for alias in no.names:
                assert not any(p in alias.name for p in proibidos), alias.name
        elif isinstance(no, ast.Call):
            alvo = no.func
            nome = (alvo.attr if isinstance(alvo, ast.Attribute)
                    else alvo.id if isinstance(alvo, ast.Name) else None)
            assert nome not in funcoes, "chama %s da camada heurística" % nome
