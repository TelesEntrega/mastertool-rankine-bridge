"""O subcomando `package-run` — a porta de entrada que faltava.

`evidence/from_run.package_run` existia desde a fundação da fase R2 e não
tinha chamador nenhum fora dos próprios testes. Um pacote que só se monta de
dentro de um teste nunca é exercido contra uma execução de campo, e foi
exatamente isso que aconteceu: a prova W10 chegou até aqui e não havia como
empacotá-la.

O que estes testes fixam não é o formato do pacote (isso é
`test_evidence_from_run.py`), e sim **o que o código de saída significa**:
completo, incompleto e não-selado são três desfechos distintos, e o segundo
não pode passar pelo primeiro.
"""

import io
import json
import os

from mastertool_bridge.cli import main

RUN_ID = "w-teste-001"


def _escrever(caminho, conteudo):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    io.open(caminho, "w", encoding="utf-8", newline="\n").write(
        json.dumps(conteudo, ensure_ascii=False))


def _run_completa(raiz, com_verificacao=True):
    art = os.path.join(str(raiz), "artefatos")
    _escrever(os.path.join(art, "execucao", "execution-completion.json"),
              {"status": "plan_executed",
               "plan_sha256": "a" * 64,
               "output_sha256": "b" * 64})
    _escrever(os.path.join(art, "execucao", "execution-manifest.json"),
              {"journal": [{"evento": "abriu"}, {"evento": "gravou"}]})
    _escrever(os.path.join(art, "authoring-plan.json"), {"steps": []})
    _escrever(os.path.join(art, "build", "build-messages.json"), [])
    _escrever(os.path.join(art, "build", "build-completion.json"),
              {"status": "build_verified"})
    if com_verificacao:
        _escrever(os.path.join(art, "verificacao",
                               "factory-verify-flat-nodes.json"),
                  {"nodes": []})
    return str(raiz)


def _argumentos(run, bundle, **extras):
    argv = ["package-run", "--run-dir", run, "--bundle-root", bundle,
            "--run-id", RUN_ID]
    for chave, valor in extras.items():
        argv += ["--" + chave.replace("_", "-"), valor]
    return argv


def test_pacote_completo_sai_zero(tmp_path, capsys):
    run = _run_completa(tmp_path / "run")
    spec = str(tmp_path / "spec.json")
    _escrever(spec, {"schema_version": 1})
    uc = str(tmp_path / "uc.json")
    _escrever(uc, {"clean": True})

    codigo = main(_argumentos(run, str(tmp_path / "bundles"), spec=spec,
                              source_project_sha256="c" * 64,
                              unexpected_changes=uc))
    saida = capsys.readouterr().out
    assert codigo == 0, saida
    assert "status: sealed_complete" in saida
    assert "[OK]" in saida


def test_pacote_incompleto_sai_TRES_e_nao_zero(tmp_path, capsys):
    """O desfecho que o comando existe para não esconder: selado, registrado,
    e explicitamente incompleto."""
    run = _run_completa(tmp_path / "run", com_verificacao=False)
    codigo = main(_argumentos(run, str(tmp_path / "bundles")))
    saida = capsys.readouterr().out
    assert codigo == 3
    assert "sealed_incomplete" in saida
    assert "[FALTANDO]" in saida


def test_o_que_faltou_e_LISTADO_um_por_um(tmp_path, capsys):
    run = _run_completa(tmp_path / "run", com_verificacao=False)
    main(_argumentos(run, str(tmp_path / "bundles")))
    saida = capsys.readouterr().out
    assert "plan/specification.json" in saida
    assert "source/project.sha256" in saida
    assert "verification/unexpected_changes.json" in saida


def test_run_sem_diretorio_de_artefatos_nao_e_pacote_incompleto(tmp_path,
                                                                capsys):
    """É recusa. Não há o que selar, e devolver 3 aqui diria que existe um
    pacote — existe é um caminho errado."""
    vazia = str(tmp_path / "nada")
    os.makedirs(vazia)
    codigo = main(_argumentos(vazia, str(tmp_path / "bundles")))
    saida = capsys.readouterr().out
    assert codigo == 2
    assert "PROBLEMA" in saida
    assert "nao chegou a ser selado" in saida.replace("ã", "a")


def test_unexpected_changes_ilegivel_entra_como_FALTANDO(tmp_path, capsys):
    """Arquivo ilegível não vira pacote sem a seção: vira pacote que declara
    a seção faltando. A diferença aparece no manifesto selado."""
    run = _run_completa(tmp_path / "run")
    ruim = str(tmp_path / "ruim.json")
    io.open(ruim, "w", encoding="utf-8").write("{ isto nao e json")
    codigo = main(_argumentos(run, str(tmp_path / "bundles"),
                              unexpected_changes=ruim))
    saida = capsys.readouterr().out
    assert codigo == 3
    assert "[FALTANDO] verification/unexpected_changes.json" in saida


def test_o_pacote_fica_em_disco_e_tem_manifesto(tmp_path):
    run = _run_completa(tmp_path / "run")
    raiz = str(tmp_path / "bundles")
    main(_argumentos(run, raiz))
    # `bundle_root` É o pacote: o `run_id` não vira subdiretório.
    manifesto = os.path.join(raiz, "manifest.json")
    assert os.path.isfile(manifesto)
    dados = json.loads(io.open(manifesto, encoding="utf-8").read())
    assert dados["status"] in ("sealed_complete", "sealed_incomplete")


# =============================================================================
# a obrigatoriedade CONDICIONAL chega ao selo
# =============================================================================

def _run_com_alteracao(raiz, com_before_texts=True):
    caminho = _run_completa(raiz)
    art = os.path.join(caminho, "artefatos")
    _escrever(os.path.join(art, "authoring-plan.json"),
              {"text_hashes": {"modify:programs:UserPrg:implementation": {
                  "raw_sha256": "a" * 64}}})
    if com_before_texts:
        _escrever(os.path.join(art, "execucao", "before-texts.json"),
                  {"objects": [{"source_location":
                                "modify:programs:UserPrg:implementation",
                                "sha256": "b" * 64, "text": "x"}]})
    return caminho


def _manifesto(raiz):
    return json.loads(io.open(os.path.join(raiz, "manifest.json"),
                              encoding="utf-8").read())


def test_plano_COM_alteracao_e_sem_rollback_sela_INCOMPLETO(tmp_path, capsys):
    """O defeito que os dez primeiros pacotes de reversão esconderam: a
    condicional existia, aparecia na saída do comando, e NÃO chegava ao selo.
    O manifesto dizia `sealed_complete` com a seção `rollback/` vazia — e a
    nota do `ROADMAP` §2.7 prometia o contrário."""
    run = _run_com_alteracao(tmp_path / "run", com_before_texts=False)
    raiz = str(tmp_path / "bundles")
    codigo = main(_argumentos(run, raiz))
    capsys.readouterr()
    assert codigo == 3
    manifesto = _manifesto(raiz)
    assert manifesto["status"] == "sealed_incomplete"
    assert "rollback/before-texts.json" in manifesto["missing_required"]
    assert "rollback/rollback-spec.json" in manifesto["missing_required"]


def test_plano_SEM_alteracao_nao_exige_rollback(tmp_path, capsys):
    """Execução que só cria não tem o que reverter. Exigir o artefato dela
    faria toda run de criação selar incompleta."""
    run = _run_completa(tmp_path / "run")
    spec = str(tmp_path / "spec.json")
    _escrever(spec, {})
    uc = str(tmp_path / "uc.json")
    _escrever(uc, {"clean": True})
    raiz = str(tmp_path / "bundles")
    codigo = main(_argumentos(run, raiz, spec=spec,
                              source_project_sha256="c" * 64,
                              unexpected_changes=uc))
    capsys.readouterr()
    assert codigo == 0
    manifesto = _manifesto(raiz)
    assert manifesto["status"] == "sealed_complete"
    assert not [m for m in manifesto["missing_required"]
                if m.startswith("rollback/")]


def test_o_manifesto_REGISTRA_se_o_plano_alterava(tmp_path):
    """Quem lê o pacote depois precisa saber por que `rollback/` era exigido —
    ou por que não era. Deixar isso implícito obrigaria a reabrir o plano."""
    run = _run_com_alteracao(tmp_path / "run")
    raiz = str(tmp_path / "bundles")
    main(_argumentos(run, raiz))
    assert _manifesto(raiz)["metadata"]["plan_has_modifications"] is True
