"""Testes do relatório de qualificação (fase R11).

Dois eixos: o documento é autocontido e determinístico, e o texto **separa o
que a evidência comprova do que exige medição** — que é a regra editorial
inegociável do padrão Rankine.
"""

import re

import pytest

from mastertool_bridge.reports.qualification_report import (
    render_qualification_report,
)


def _equivalencia(*, count=3, equivalentes=3, minimo=3, violacoes=(),
                  volateis=None, problemas=()):
    geracoes = []
    for i in range(1, count + 1):
        caminho = "C:/lote/run-%03d" % i
        equivalente = i <= equivalentes
        geracao = {
            "generation": caminho,
            "equivalent": equivalente,
            "divergences": ([] if equivalente
                            else ["GVL_FAB:declaration: sha256 aaa != bbb"]),
            "layers_compared": ["persisted_texts", "tree"],
            "layers_absent": ["structural_diff"],
            "volatile_differences": [],
        }
        if i == 1:
            geracao["note"] = ("referência: equivalente a si mesma por "
                               "definição, não por medição")
        geracoes.append(geracao)
    return {
        "repeatable": (equivalentes == count and not violacoes
                       and count >= minimo),
        "layout": "factory",
        "count": count,
        "minimum_required": minimo,
        "meets_minimum": count >= minimo,
        "reference": "C:/lote/run-001",
        "generations": ["C:/lote/run-%03d" % i for i in range(1, count + 1)],
        "equivalent_count": equivalentes,
        "all_equivalent": equivalentes == count,
        "per_generation": geracoes,
        "independence_violations": list(violacoes),
        "volatile_distribution": (volateis if volateis is not None else [
            {"field": "generated_at", "classification": "allowed_volatile",
             "distinct_values": count, "observed_in": count,
             "runs": {}},
            {"field": "plan_sha256", "classification": "allowed_volatile",
             "distinct_values": 1, "observed_in": count, "runs": {}},
        ]),
        "problems": list(problemas),
    }


def _lote(**kwargs):
    equivalencia = _equivalencia(**kwargs)
    return {
        "schema_version": 1,
        "qualification_id": "R1-W7-W9",
        "qualified": equivalencia["repeatable"],
        "requested_runs": equivalencia["count"],
        "completed_runs": equivalencia["count"],
        "all_runs_completed": True,
        "runs": [],
        "problems": [],
        "equivalence": equivalencia,
    }


def _render(**kwargs):
    return render_qualification_report(
        _lote(**kwargs), generated_at="2026-08-02T07:15",
        qualification_id="R1-W7-W9",
        template_profile="mastertool-x-4.1.0.11-tpl-v1-io-v1",
        product_version="MasterTool X 4.1.0.11")


# =============================================================================
# autocontenção — o arquivo tem de abrir de um pen drive
# =============================================================================

def test_o_html_nao_referencia_nada_externo():
    doc = _render()
    assert "<script" not in doc.lower()
    assert "cdn" not in doc.lower()
    assert "@import" not in doc
    assert "http://" not in doc
    # O único link externo permitido é o site no rodapé, e é <a>, não recurso.
    externos = re.findall(r'src="([^"]+)"', doc)
    assert all(u.startswith("data:") for u in externos), externos


def test_sem_logo_o_documento_sai_sem_logo_e_nao_com_um_inventado():
    doc = _render()
    assert "<img" not in doc

    com_logo = render_qualification_report(
        _lote(), generated_at="2026-08-02T07:15",
        logo_data_uri="data:image/png;base64,AAAA")
    assert 'src="data:image/png;base64,AAAA"' in com_logo
    assert com_logo.count("<img") == 2   # capa e rodapé


def test_o_relatorio_e_deterministico():
    assert _render() == _render()


def test_a_hora_entra_como_dado_e_nao_do_relogio():
    doc = _render()
    assert "2026-08-02T07:15" in doc
    outro = render_qualification_report(_lote(),
                                        generated_at="1999-01-01T00:00")
    assert "1999-01-01T00:00" in outro


# =============================================================================
# regra editorial: comprova x exige medição
# =============================================================================

def test_a_secao_de_limites_e_a_ultima_e_separa_as_duas_colunas():
    doc = _render()
    assert doc.index('id="s5"') > doc.index('id="s4"')
    assert "A evidência estabelece" in doc
    assert "Continua exigindo medição" in doc
    assert "não se presume provada em outra" in doc


def test_lote_estavel_abaixo_do_piso_nao_e_chamado_de_repetivel():
    """Três execuções equivalentes comprovam estabilidade em três — não
    repetibilidade, que é afirmação sobre dez."""
    doc = _render(count=3, equivalentes=3, minimo=10)
    assert "Lote reprovado" in doc
    assert "Estável, e ainda não qualificado" in doc
    assert "não repetibilidade" in doc or "não&nbsp;repetibilidade" in doc


def test_toda_tabela_tem_caption_explicando_como_ler():
    doc = _render()
    tabelas = doc.count("<table>")
    captions = doc.count("<caption>")
    assert tabelas >= 3
    assert captions == tabelas


def test_o_volatil_permitido_aparece_com_a_contagem():
    doc = _render()
    assert "generated_at" in doc
    assert "plan_sha256" in doc
    assert "não</strong> reprovam o lote" in doc


def test_volatil_que_alterna_e_marcado_como_achado():
    """Dois valores em dez execuções não é variação esperada — é alternância,
    e merece explicação."""
    doc = _render(count=10, equivalentes=10, minimo=10, volateis=[
        {"field": "output_project_path", "classification": "allowed_volatile",
         "distinct_values": 2, "observed_in": 10, "runs": {}}])
    assert "Alterna" in doc
    assert "merece explicação" in doc


# =============================================================================
# veredito
# =============================================================================

def test_lote_qualificado_diz_qualificado():
    doc = _render(count=10, equivalentes=10, minimo=10)
    assert "Lote qualificado" in doc
    assert "c-ok" in doc


def test_geracao_divergente_aparece_nomeada_com_a_divergencia():
    doc = _render(count=3, equivalentes=2, minimo=3)
    assert "Diverge" in doc
    assert "run-003" in doc
    assert "sha256 aaa != bbb" in doc


def test_violacao_de_independencia_vira_caixa_critica():
    doc = _render(violacoes=["C:/lote/run-002 e C:/lote/run-003 têm os mesmos "
                             "GUIDs de objeto"])
    assert "Execuções não independentes" in doc
    assert "box crit" in doc


def test_a_referencia_e_identificada_como_tal():
    doc = _render()
    assert "Referência" in doc
    assert "por definição, não por medição" in doc


def test_problemas_da_apuracao_aparecem():
    doc = _render(problemas=["árvore ausente em run-003"])
    assert "Problemas registrados na apuração" in doc
    assert "run-003" in doc


# =============================================================================
# robustez
# =============================================================================

def test_nome_de_diretorio_com_html_e_escapado():
    """Nome de diretório é dado externo, e dado externo não entra cru."""
    lote = _lote()
    # Sem barra nenhuma no nome: `_nome_curto` corta pelo último `/`, e um
    # valor com barra exercitaria o corte em vez do escape.
    lote["equivalence"]["per_generation"][1]["generation"] = 'run-<b>x"y'
    doc = render_qualification_report(lote, generated_at="2026-08-02T07:15")
    assert "<b>x" not in doc
    assert "run-&lt;b&gt;x&quot;y" in doc


def test_entrada_que_nao_e_dict_levanta_com_nome():
    with pytest.raises(TypeError):
        render_qualification_report(["nao", "e", "dict"],
                                    generated_at="2026-08-02T07:15")


def test_relatorio_direto_de_um_resultado_de_comparacao():
    """Aceita tanto o dicionário do lote quanto o do comparador — o segundo é
    o que sai de `compare_many` sem runner nenhum."""
    doc = render_qualification_report(_equivalencia(),
                                      generated_at="2026-08-02T07:15")
    assert "Sumário executivo" in doc


def test_lote_sem_volateis_diz_que_ausencia_nao_e_ausencia_de_variacao():
    doc = _render(volateis=[])
    assert "ausência de observação não é ausência de variação" in doc


# =============================================================================
# integração com a CLI
# =============================================================================

def test_cli_gera_o_documento_html(tmp_path, capsys):
    import io as _io
    import json as _json

    from mastertool_bridge.cli import main

    # Lote sintético mínimo no layout da fábrica.
    raiz = tmp_path / "lote"
    for i in range(1, 3):
        destino = raiz / ("run-%03d" % i) / "verificacao"
        destino.mkdir(parents=True)
        (destino / "factory-verify-texts.json").write_text(
            _json.dumps({"objects": [
                {"family": "gvls", "name": "GVL_FAB",
                 "texts": [{"field": "declaration",
                            "sha256_observed": "a" * 64}]}]}),
            encoding="utf-8")
        (destino / "factory-verify-flat-nodes.json").write_text(
            _json.dumps({"nodes": [{
                "node_id": "root/1/0/0/0", "parent_node_id": "root/1/0/0",
                "depth": 4, "index": 0, "name": "GVL_FAB",
                "type_guid": "ffbfa93a-b94d-45fc-a329-229860183b1d",
                "child_count": 0, "object_guid": "guid-%d" % i}]}),
            encoding="utf-8")

    destino_html = tmp_path / "relatorio.html"
    main(["qualify-repeatability", "--runs-root", str(raiz), "--minimum", "2",
          "--html", str(destino_html), "--generated-at", "2026-08-02T07:15",
          "--qualification-id", "R1-PILOTO",
          "--product-version", "MasterTool X 4.1.0.11"])

    doc = _io.open(str(destino_html), encoding="utf-8").read()
    assert doc.startswith("<!doctype html>")
    assert "R1-PILOTO" in doc
    assert "MasterTool X 4.1.0.11" in doc
    assert "2026-08-02T07:15" in doc
    assert "<script" not in doc.lower()
    assert "documento:" in capsys.readouterr().out


def test_cli_passa_o_logo_quando_informado(tmp_path):
    import io as _io
    import json as _json

    from mastertool_bridge.cli import main

    raiz = tmp_path / "lote"
    for i in range(1, 3):
        destino = raiz / ("run-%03d" % i) / "verificacao"
        destino.mkdir(parents=True)
        (destino / "factory-verify-texts.json").write_text(
            _json.dumps({"objects": []}), encoding="utf-8")
        (destino / "factory-verify-flat-nodes.json").write_text(
            _json.dumps({"nodes": []}), encoding="utf-8")

    logo = tmp_path / "logo.txt"
    logo.write_text("data:image/png;base64,QUJD\n", encoding="utf-8")

    destino_html = tmp_path / "com-logo.html"
    main(["qualify-repeatability", "--runs-root", str(raiz), "--minimum", "2",
          "--html", str(destino_html), "--generated-at", "2026-08-02T07:15",
          "--logo-file", str(logo)])

    doc = _io.open(str(destino_html), encoding="utf-8").read()
    assert 'src="data:image/png;base64,QUJD"' in doc
