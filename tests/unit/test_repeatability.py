"""Testes do mecanismo de repetibilidade (fase R1) — runner de N execuções e
comparador N-ário.

Este é o **gate offline** da R1: o mecanismo inteiro é exercitado com gerações
sintéticas, antes de qualquer lote real no MasterTool. Um erro mecânico no
empacotamento descoberto durante a qualificação desperdiçaria dez execuções de
campo sem acrescentar evidência nenhuma.
"""

import io
import json

import pytest

from mastertool_bridge.automation.generation_equivalence import (
    LAYOUT_FACTORY,
    compare_many,
)
from mastertool_bridge.automation.repeatability import (
    QualificationRequest,
    REQUIRED_RUN_ARTIFACTS,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_INCOMPLETE,
    execute_qualification,
    plan_iterations,
    validate_request,
)

SHA_ORIGEM = "5966257" + "9" * 57


def _no(indice, nome, guid):
    return {
        "node_id": "root/1/0/0/%d" % indice,
        "parent_node_id": "root/1/0/0",
        "depth": 4,
        "index": indice,
        "name": nome,
        "type_guid": "ffbfa93a-b94d-45fc-a329-229860183b1d",
        "child_count": 0,
        "object_guid": guid,
    }


def _escrever(caminho, payload):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    io.open(str(caminho), "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False))


def _geracao(raiz, run_id, *, guid_sufixo, texto_sha=None, nomes=None,
             gerado_em=None, artefatos=True, artefatos_faltando=()):
    """Escreve uma geração sintética no layout da FÁBRICA."""
    destino = raiz / run_id
    nomes = nomes or ["GVL_FAB", "PRG_FAB"]
    texto_sha = texto_sha or ("a" * 64)

    _escrever(destino / "verificacao" / "factory-verify-texts.json", {
        "objects": [
            {"family": "gvls", "name": nomes[0],
             "texts": [{"field": "declaration", "sha256_observed": texto_sha}]},
            {"family": "programs", "name": nomes[1],
             "texts": [{"field": "implementation",
                        "sha256_observed": "b" * 64}]},
        ]
    })
    _escrever(destino / "verificacao" / "factory-verify-flat-nodes.json", {
        "nodes": [_no(i, nome, "guid-%s-%d" % (guid_sufixo, i))
                  for i, nome in enumerate(nomes)]
    })
    if artefatos:
        for nome in REQUIRED_RUN_ARTIFACTS:
            if nome in artefatos_faltando:
                continue
            _escrever(destino / nome, {"run": run_id})
    # A conclusão é escrita DEPOIS dos artefatos obrigatórios porque
    # `execution-completion.json` está nos dois conjuntos: ela é o sinal de
    # conclusão do probe 46 E a fonte dos campos voláteis. Escrever na ordem
    # inversa sobrescreveria os voláteis com um marcador vazio — foi o que
    # aconteceu na primeira versão deste fixture, e o sintoma foi uma
    # distribuição de voláteis vazia num lote que tem três.
    if "execution-completion.json" not in artefatos_faltando:
        _escrever(destino / "execucao" / "execution-completion.json", {
            "generated_at": gerado_em or (
                "2026-08-01T00:00:%02d" % guid_sufixo
                if isinstance(guid_sufixo, int) else "x"),
            "plan_sha256": "c" * 64,
            "output_project_path": str(destino / "saida.project"),
        })
    return destino


def _lote(raiz, quantidade, **kwargs):
    return [_geracao(raiz, "run-%03d" % i, guid_sufixo=i, **kwargs)
            for i in range(1, quantidade + 1)]


# =============================================================================
# comparador N-ário
# =============================================================================

def test_n_geracoes_identicas_e_independentes_qualificam(tmp_path):
    dirs = _lote(tmp_path, 3)
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.problems == [], resultado.problems
    assert resultado.all_equivalent
    assert resultado.independence_violations == []
    assert resultado.repeatable is True
    assert resultado.count == 3


def test_o_piso_padrao_vem_da_norma_e_nao_deste_modulo(tmp_path):
    """Sem `minimum_required`, o número é o mesmo que o gate do Template
    Profile aplica — uma constante só para a mesma norma."""
    from mastertool_bridge.templates.profile import MIN_INDEPENDENT_RUNS

    dirs = _lote(tmp_path, 3)
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY)
    assert resultado.minimum_required == MIN_INDEPENDENT_RUNS["repeatable"]
    assert resultado.meets_minimum is False
    # Equivalentes e independentes, e mesmo assim NÃO repetíveis: três não é
    # dez, e o veredito não arredonda.
    assert resultado.all_equivalent is True
    assert resultado.repeatable is False


def test_uma_geracao_divergente_reprova_e_e_nomeada(tmp_path):
    dirs = _lote(tmp_path, 3)
    _geracao(tmp_path, "run-004", guid_sufixo=4, texto_sha="f" * 64)
    dirs.append(tmp_path / "run-004")

    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.repeatable is False
    divergentes = [g for g in resultado.per_generation if not g["equivalent"]]
    assert len(divergentes) == 1
    assert divergentes[0]["generation"].endswith("run-004")
    assert any("sha256" in d for d in divergentes[0]["divergences"])


def test_duas_classes_de_divergencia_aparecem_separadas(tmp_path):
    dirs = _lote(tmp_path, 2)
    _geracao(tmp_path, "run-003", guid_sufixo=3, texto_sha="f" * 64)
    _geracao(tmp_path, "run-004", guid_sufixo=4,
             nomes=["GVL_OUTRA", "PRG_FAB"])
    dirs += [tmp_path / "run-003", tmp_path / "run-004"]

    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=4)
    assert resultado.repeatable is False
    por_geracao = {g["generation"].split("\\")[-1].split("/")[-1]: g
                   for g in resultado.per_generation}
    assert any("sha256" in d
               for d in por_geracao["run-003"]["divergences"])
    assert any("assinatura da árvore" in d or "conjunto de textos" in d
               for d in por_geracao["run-004"]["divergences"])


def test_independencia_e_conferida_entre_TODOS_os_pares(tmp_path):
    """A recusa que uma comparação contra referência não pegaria.

    `run-002` e `run-003` compartilham GUIDs entre si, e nenhuma das duas
    compartilha com a referência. Conferir só contra `run-001` daria o lote
    como independente — e ele não é."""
    _geracao(tmp_path, "run-001", guid_sufixo=1)
    _geracao(tmp_path, "run-002", guid_sufixo=7)
    _geracao(tmp_path, "run-003", guid_sufixo=7)
    dirs = [tmp_path / "run-001", tmp_path / "run-002", tmp_path / "run-003"]

    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.all_equivalent is True
    assert len(resultado.independence_violations) == 1
    assert "run-002" in resultado.independence_violations[0]
    assert "run-003" in resultado.independence_violations[0]
    assert resultado.repeatable is False


def test_campo_volatil_permitido_nao_reprova_mas_aparece(tmp_path):
    """Estar na allowlist dispensa de reprovar, não de aparecer."""
    dirs = _lote(tmp_path, 3)
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.repeatable is True

    por_campo = {v["field"]: v for v in resultado.volatile_distribution}
    assert por_campo["generated_at"]["distinct_values"] == 3
    assert por_campo["generated_at"]["classification"] == "allowed_volatile"
    assert len(por_campo["generated_at"]["runs"]) == 3
    # `plan_sha256` é igual nas três: volátil PERMITIDO não quer dizer que
    # varie sempre, e o relatório mostra os dois casos.
    assert por_campo["plan_sha256"]["distinct_values"] == 1


def test_campo_NAO_volatil_que_varia_reprova(tmp_path):
    """A contraprova do teste anterior: o que não está na lista literal de
    voláteis reprova ao variar."""
    dirs = _lote(tmp_path, 2)
    _geracao(tmp_path, "run-003", guid_sufixo=3, texto_sha="e" * 64)
    dirs.append(tmp_path / "run-003")
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.repeatable is False


def test_uma_geracao_so_nao_e_comparacao(tmp_path):
    dirs = _lote(tmp_path, 1)
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=1)
    assert resultado.repeatable is False
    assert any("duas gerações" in p for p in resultado.problems)


def test_mesmo_diretorio_repetido_nao_e_repeticao(tmp_path):
    """Dez vezes o mesmo diretório passa em toda camada de igualdade e não
    mede nada."""
    dirs = _lote(tmp_path, 1) * 3
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.repeatable is False
    assert any("repetido" in p for p in resultado.problems)


def test_arvore_ilegivel_torna_independencia_nao_verificavel(tmp_path):
    dirs = _lote(tmp_path, 3)
    (dirs[2] / "verificacao" / "factory-verify-flat-nodes.json").unlink()
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.repeatable is False
    assert any("independência não verificável" in p for p in resultado.problems)


def test_relatorio_e_deterministico(tmp_path):
    dirs = _lote(tmp_path, 3)
    primeiro = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    segundo = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert primeiro.to_dict() == segundo.to_dict()


def test_a_referencia_e_equivalente_a_si_mesma_por_definicao(tmp_path):
    """Compará-la consigo mesma dispararia a regra de GUIDs distintos e
    produziria uma divergência sem significado."""
    dirs = _lote(tmp_path, 2)
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=2)
    primeira = resultado.per_generation[0]
    assert primeira["equivalent"] is True
    assert "definição" in primeira["note"]


# =============================================================================
# runner de N execuções
# =============================================================================

def _pedido(tmp_path, runs=3, **kwargs):
    base = dict(
        qualification_id="R1-W7-W9",
        template_profile="mastertool-x-4.1.0.11-tmf-v1-io-v1",
        source_project_sha256=SHA_ORIGEM,
        specification="spec-fabrica.json",
        runs=runs,
        output_root=str(tmp_path / "lote"),
    )
    base.update(kwargs)
    return QualificationRequest(**base)


def _executor_ok(vaga):
    _geracao(vaga.output_dir.parent, vaga.output_dir.name,
             guid_sufixo=vaga.index)
    return {"status": STATUS_COMPLETED,
            "input_sha256_before": SHA_ORIGEM,
            "input_sha256_after": SHA_ORIGEM}


def test_vagas_sao_numeradas_antes_de_qualquer_execucao(tmp_path):
    """A numeração não depende do que deu certo: `run-007` é a sétima vaga,
    tenha ela concluído ou não."""
    vagas = plan_iterations(_pedido(tmp_path, runs=10))
    assert [v.run_id for v in vagas][:3] == ["run-001", "run-002", "run-003"]
    assert vagas[-1].run_id == "run-010"
    assert len({str(v.output_dir) for v in vagas}) == 10


def test_lote_completo_e_equivalente_qualifica(tmp_path):
    resultado = execute_qualification(_pedido(tmp_path, runs=3), _executor_ok,
                                      minimum_required=3)
    assert resultado.problems == [], resultado.problems
    assert resultado.completed_runs == 3
    assert resultado.all_runs_completed is True
    assert resultado.qualified is True


def test_uma_run_reprovada_reprova_o_LOTE_e_as_outras_seguem(tmp_path):
    """Parar na primeira falha economizaria tempo e destruiria a evidência que
    distingue falha isolada de falha sistemática."""
    def executor(vaga):
        if vaga.index == 2:
            return {"status": STATUS_FAILED,
                    "problems": ["build reprovou com 1 erro"]}
        return _executor_ok(vaga)

    resultado = execute_qualification(_pedido(tmp_path, runs=4), executor,
                                      minimum_required=3)
    assert len(resultado.outcomes) == 4          # todas tentadas
    assert resultado.completed_runs == 3
    assert resultado.qualified is False
    assert resultado.outcomes[1].status == STATUS_FAILED


def test_run_que_se_declara_completa_sem_artefato_vira_incompleta(tmp_path):
    """O status vem do que está em disco, não do que a run diz de si mesma."""
    def executor(vaga):
        _geracao(vaga.output_dir.parent, vaga.output_dir.name,
                 guid_sufixo=vaga.index,
                 artefatos_faltando=("execution-steps.json",))
        return {"status": STATUS_COMPLETED,
                "input_sha256_before": SHA_ORIGEM,
                "input_sha256_after": SHA_ORIGEM}

    resultado = execute_qualification(_pedido(tmp_path, runs=2), executor,
                                      minimum_required=2)
    assert all(o.status == STATUS_INCOMPLETE for o in resultado.outcomes)
    assert resultado.outcomes[0].missing_artifacts == ["execution-steps.json"]
    assert resultado.qualified is False


def test_entrada_alterada_durante_a_run_reprova(tmp_path):
    """Uma run que altera o projeto de origem é o pior sucesso possível."""
    def executor(vaga):
        _executor_ok(vaga)
        return {"status": STATUS_COMPLETED,
                "input_sha256_before": SHA_ORIGEM,
                "input_sha256_after": "0" * 64}

    resultado = execute_qualification(_pedido(tmp_path, runs=2), executor,
                                      minimum_required=2)
    assert resultado.outcomes[0].status == STATUS_FAILED
    assert any("mudou durante a run" in p for p in resultado.outcomes[0].problems)


def test_entrada_diferente_da_declarada_reprova(tmp_path):
    def executor(vaga):
        _executor_ok(vaga)
        return {"status": STATUS_COMPLETED,
                "input_sha256_before": "1" * 64,
                "input_sha256_after": "1" * 64}

    resultado = execute_qualification(_pedido(tmp_path, runs=2), executor,
                                      minimum_required=2)
    assert resultado.outcomes[0].status == STATUS_FAILED
    assert any("não é o declarado" in p for p in resultado.outcomes[0].problems)


def test_saida_preexistente_recusa_ANTES_da_primeira_execucao(tmp_path):
    pedido = _pedido(tmp_path, runs=3)
    (tmp_path / "lote" / "run-002").mkdir(parents=True)
    chamadas = []

    def executor(vaga):
        chamadas.append(vaga.run_id)
        return _executor_ok(vaga)

    resultado = execute_qualification(pedido, executor, minimum_required=3)
    assert chamadas == []
    assert resultado.qualified is False
    assert any("já existe" in p for p in resultado.problems)


def test_executor_que_levanta_vira_falha_e_nao_derruba_o_lote(tmp_path):
    def executor(vaga):
        if vaga.index == 1:
            raise RuntimeError("MT9000 morreu")
        return _executor_ok(vaga)

    resultado = execute_qualification(_pedido(tmp_path, runs=3), executor,
                                      minimum_required=2)
    assert resultado.outcomes[0].status == STATUS_FAILED
    assert "MT9000 morreu" in resultado.outcomes[0].problems[0]
    assert resultado.completed_runs == 2
    assert resultado.qualified is False


def test_parar_no_primeiro_erro_e_opcional_e_deixa_rastro(tmp_path):
    def executor(vaga):
        if vaga.index == 2:
            return {"status": STATUS_FAILED}
        return _executor_ok(vaga)

    resultado = execute_qualification(
        _pedido(tmp_path, runs=5, continue_after_failure=False), executor,
        minimum_required=2)
    assert len(resultado.outcomes) == 2
    assert any("não executada" in p for p in resultado.problems)
    assert resultado.qualified is False


def test_status_fora_do_vocabulario_vira_incompleto(tmp_path):
    def executor(vaga):
        _executor_ok(vaga)
        return {"status": "quase"}

    resultado = execute_qualification(_pedido(tmp_path, runs=2), executor,
                                      minimum_required=2)
    assert resultado.outcomes[0].status == STATUS_INCOMPLETE
    assert any("vocabulário fechado" in p
               for p in resultado.outcomes[0].problems)


def test_menos_de_duas_runs_concluidas_nao_qualifica(tmp_path):
    def executor(vaga):
        if vaga.index > 1:
            return {"status": STATUS_FAILED}
        return _executor_ok(vaga)

    resultado = execute_qualification(_pedido(tmp_path, runs=3), executor,
                                      minimum_required=2)
    assert any("menos de duas runs" in p for p in resultado.problems)
    assert resultado.qualified is False


def test_relatorio_do_lote_e_serializavel_e_completo(tmp_path):
    resultado = execute_qualification(_pedido(tmp_path, runs=3), _executor_ok,
                                      minimum_required=3)
    d = resultado.to_dict()
    assert json.loads(json.dumps(d, ensure_ascii=False))["qualified"] is True
    assert len(d["runs"]) == 3
    assert d["equivalence"]["count"] == 3
    assert d["schema_version"] == 1


@pytest.mark.parametrize("mudanca,esperado", [
    ({"runs": 0}, "runs"),
    ({"runs": True}, "runs"),
    ({"source_project_sha256": "nao-e-sha"}, "source_project_sha256"),
    ({"qualification_id": "  "}, "qualification_id"),
    ({"template_profile": ""}, "template_profile"),
])
def test_solicitacao_invalida_reprova_com_nome(tmp_path, mudanca, esperado):
    problemas = validate_request(_pedido(tmp_path, **mudanca))
    assert any(esperado in p for p in problemas)


def test_solicitacao_degenerada_nao_levanta():
    for entrada in (None, {}, "R1", 7):
        assert validate_request(entrada)


def test_solicitacao_invalida_nao_executa_nada(tmp_path):
    chamadas = []

    def executor(vaga):
        chamadas.append(vaga.run_id)
        return _executor_ok(vaga)

    resultado = execute_qualification(_pedido(tmp_path, runs=0), executor)
    assert chamadas == []
    assert resultado.qualified is False


# =============================================================================
# comando de CLI -- a metade que o operador usa depois do lote
# =============================================================================

def test_cli_julga_lote_equivalente(tmp_path, capsys):
    from mastertool_bridge.cli import main

    raiz = tmp_path / "lote"
    for i in range(1, 4):
        _geracao(raiz, "run-%03d" % i, guid_sufixo=i)

    codigo = main(["qualify-repeatability", "--runs-root", str(raiz),
                   "--minimum", "3",
                   "--output", str(tmp_path / "relatorio.json")])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "[OK]" in saida
    assert "3 geração(ões)" in saida
    relatorio = json.loads(io.open(str(tmp_path / "relatorio.json"),
                                   encoding="utf-8").read())
    assert relatorio["repeatable"] is True


def test_cli_reprova_e_nomeia_a_geracao_divergente(tmp_path, capsys):
    from mastertool_bridge.cli import main

    raiz = tmp_path / "lote"
    for i in range(1, 3):
        _geracao(raiz, "run-%03d" % i, guid_sufixo=i)
    _geracao(raiz, "run-003", guid_sufixo=3, texto_sha="f" * 64)

    codigo = main(["qualify-repeatability", "--runs-root", str(raiz),
                   "--minimum", "3"])
    saida = capsys.readouterr().out
    assert codigo == 1
    assert "REPROVADO" in saida
    assert "run-003" in saida


def test_cli_mostra_o_volatil_permitido_em_vez_de_escondê_lo(tmp_path, capsys):
    from mastertool_bridge.cli import main

    raiz = tmp_path / "lote"
    for i in range(1, 4):
        _geracao(raiz, "run-%03d" % i, guid_sufixo=i)
    main(["qualify-repeatability", "--runs-root", str(raiz), "--minimum", "3"])
    saida = capsys.readouterr().out
    assert "volátil permitido" in saida
    assert "generated_at" in saida


def test_cli_recusa_lote_inexistente_ou_vazio(tmp_path, capsys):
    from mastertool_bridge.cli import main

    assert main(["qualify-repeatability", "--runs-root",
                 str(tmp_path / "nao-existe")]) == 1
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    assert main(["qualify-repeatability", "--runs-root", str(vazio)]) == 1
    saida = capsys.readouterr().out
    assert "não encontrado" in saida or "nenhum diretório" in saida


def test_cli_sem_minimo_usa_o_piso_da_norma(tmp_path, capsys):
    """Três gerações equivalentes e independentes: aprovadas na equivalência,
    reprovadas na fase, porque três não é dez."""
    from mastertool_bridge.cli import main

    raiz = tmp_path / "lote"
    for i in range(1, 4):
        _geracao(raiz, "run-%03d" % i, guid_sufixo=i)
    codigo = main(["qualify-repeatability", "--runs-root", str(raiz)])
    saida = capsys.readouterr().out
    assert codigo == 1
    assert "NÃO atingido" in saida
    assert "equivalentes       : 3/3" in saida


# =============================================================================
# o layout REAL da fábrica -- artefatos sob `artefatos/`, conclusão com o nome
# que o probe 46 grava
# =============================================================================

def _geracao_layout_real(raiz, run_id, *, guid_sufixo):
    """Como `run_project_factory.ps1` de fato grava: tudo sob
    `<WorkRoot>/artefatos/`, e a conclusão chamada
    `execution-completion.json` (probe 46, ARTIFACT_NAMES)."""
    destino = raiz / run_id / "artefatos"
    _escrever(destino / "verificacao" / "factory-verify-texts.json", {
        "objects": [{"family": "gvls", "name": "GVL_FAB",
                     "texts": [{"field": "declaration",
                                "sha256_observed": "a" * 64}]}]})
    _escrever(destino / "verificacao" / "factory-verify-flat-nodes.json", {
        "nodes": [_no(0, "GVL_FAB", "guid-%d-0" % guid_sufixo)]})
    for nome in REQUIRED_RUN_ARTIFACTS:
        _escrever(destino / nome, {"run": run_id})
    # Depois dos obrigatórios: `execution-completion.json` pertence aos dois
    # conjuntos, e a ordem inversa apagaria os campos voláteis.
    _escrever(destino / "execucao" / "execution-completion.json", {
        "generated_at": "2026-08-02T0%d:00" % guid_sufixo,
        "plan_sha256": "c" * 64,
        "output_project_path": str(destino / "saida.project")})
    return destino


def test_a_conclusao_e_lida_pelo_nome_QUE_O_PROBE_GRAVA(tmp_path):
    """O nome fixo `completion.json` não existia em lote real nenhum: a
    cadeia da fábrica grava `execution-completion.json`. O efeito era pior que
    um erro — a distribuição de voláteis saía VAZIA, e campo volátil ausente
    não reprova. O relatório diria "0 campos voláteis" sobre um lote com
    três."""
    dirs = [_geracao_layout_real(tmp_path, "run-%03d" % i, guid_sufixo=i)
            for i in (1, 2, 3)]
    resultado = compare_many(dirs, layout=LAYOUT_FACTORY, minimum_required=3)
    assert resultado.repeatable is True
    campos = {v["field"] for v in resultado.volatile_distribution}
    assert campos == {"generated_at", "plan_sha256", "output_project_path"}
    por_campo = {v["field"]: v for v in resultado.volatile_distribution}
    assert por_campo["generated_at"]["distinct_values"] == 3


def test_o_nome_da_conclusao_e_declarado_por_layout():
    from mastertool_bridge.automation.generation_equivalence import LAYOUT_W1_4

    assert LAYOUT_FACTORY["completion"] == "execucao/execution-completion.json"
    assert LAYOUT_W1_4["completion"] == "completion.json"


def test_cli_resolve_o_diretorio_de_artefatos_da_fabrica(tmp_path, capsys):
    """Olhar direto para `run-NNN/` acharia o diretório e nenhum artefato, e o
    veredito sairia "árvore ausente" para um lote perfeitamente bom."""
    from mastertool_bridge.cli import main

    raiz = tmp_path / "lote"
    for i in (1, 2, 3):
        _geracao_layout_real(raiz, "run-%03d" % i, guid_sufixo=i)

    codigo = main(["qualify-repeatability", "--runs-root", str(raiz),
                   "--minimum", "3"])
    saida = capsys.readouterr().out
    assert codigo == 0, saida
    assert "[OK]" in saida
    assert "artefatos" in saida or "3 geração(ões)" in saida


def test_cli_continua_aceitando_diretorio_que_ja_e_o_de_artefatos(tmp_path,
                                                                  capsys):
    """Resolução por EXISTÊNCIA, não por convenção."""
    from mastertool_bridge.cli import main

    raiz = tmp_path / "lote"
    for i in (1, 2, 3):
        _geracao(raiz, "run-%03d" % i, guid_sufixo=i)   # sem `artefatos/`
    assert main(["qualify-repeatability", "--runs-root", str(raiz),
                 "--minimum", "3"]) == 0
