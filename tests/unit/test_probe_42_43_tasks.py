"""Testes de `probes/42_recon_tasks_readonly.py` e
`probes/43_bind_program_to_task.py`, com dubles ESTRITOS e verificacao estatica
por RECEPTOR.

O perigo deste par nao e o mesmo do probe 41. La os mutadores moravam no mesmo
objeto que a leitura, mas tinham nomes proprios (`add_library` e companhia).
Aqui `ScriptPouObjectCollection` HERDA DE `list` (stub `ScriptTaskConfigObject.
pyi` L288) e os seus mutadores se chamam `add`, `insert`, `remove` e `replace`:
quatro nomes que qualquer colecao Python tambem tem.

Isso quebra a verificacao por NOME nas duas direcoes -- ela reprovaria codigo
Python legitimo E nao distinguiria a chamada que escreve no projeto. Por isso:

* o mapa de "quem chama o que" e por RECEPTOR e esta CONGELADO nos dois probes;
* a guarda de escrita e conferida por ADJACENCIA na AST: a chamada mutavel tem
  de ter `assert_controlled_write_allowed("<literal certo>")` na linha
  imediatamente anterior, dentro da mesma funcao;
* os dubles LEVANTAM se um membro fora da leitura medida for tocado.

As tres falsificacoes exigidas pelo contrato estao em
`test_falsificacao_*` -- elas provam que cada guarda ACUSA quando deve, em vez
de passar por vacuidade.
"""

import ast
import hashlib
import io
import json
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

PROBE42_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "42_recon_tasks_readonly.py")
PROBE43_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "43_bind_program_to_task.py")

GUARDA = "assert_controlled_write_allowed"

# Receptor de proxy do MasterTool -> operacao que a guarda DEVE nomear naquela
# linha. O mapa mora no teste, e nao no probe: e ele que decide o que conta
# como mutacao, e o probe nao pode se autorizar.
RECEPTORES_MUTAVEIS = {
    "pou_collection": "add",
    "project": "save_as",
}

NOMES_MUTADORES_DE_TASK = ("create_task", "create_task_configuration",
                           "create_boot_application", "insert", "remove",
                           "replace", "save", "save_archive", "build",
                           "rebuild", "clean", "import_xml", "rename", "move")


def _load_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe42 = _load_module(PROBE42_PATH, "probe42_recon_tasks")
probe43 = _load_module(PROBE43_PATH, "probe43_bind_program")

from common import safety as safety_real   # noqa: E402


# =============================================================================
# Dubles ESTRITOS -- qualquer acesso fora da leitura medida LEVANTA
# =============================================================================

class _Estrito(object):
    """Base dos dubles: tudo o que nao for declarado explicitamente levanta."""

    _ROTULO = "objeto"

    def __getattr__(self, nome):
        raise AssertionError(
            "o probe tocou %r em %s -- fora da leitura medida"
            % (nome, self._ROTULO))


class ColecaoEstrita(_Estrito):
    """Colecao CLR de filhos: so `Count` e indexador."""

    _ROTULO = "colecao de filhos"

    def __init__(self, itens):
        self._itens = list(itens)
        self.Count = len(self._itens)

    def __getitem__(self, indice):
        return self._itens[indice]


class PousSomenteLeitura(_Estrito):
    """`ScriptPouObjectCollection` como o probe 42 pode ve-la: `__len__` e
    indexador, e nada mais. Tocar `add`, `insert`, `remove` ou `replace`
    levanta -- e e exatamente isso que a falsificacao 1 verifica."""

    _ROTULO = "colecao de POUs (leitura)"

    def __init__(self, itens=None, erro_len=None, erro_indice=None,
                 item_estranho=False):
        self._itens = list(itens or [])
        self._erro_len = erro_len
        self._erro_indice = erro_indice
        self._item_estranho = item_estranho

    def __len__(self):
        if self._erro_len is not None:
            raise self._erro_len
        return len(self._itens)

    def __getitem__(self, indice):
        if self._erro_indice is not None:
            raise self._erro_indice
        if self._item_estranho:
            return object()
        return self._itens[indice]


class PousMutavel(PousSomenteLeitura):
    """A mesma colecao, agora com o mutador -- so o probe 43 pode toca-la."""

    _ROTULO = "colecao de POUs (mutavel)"

    def __init__(self, itens=None, erro_add=None, efeito=None):
        PousSomenteLeitura.__init__(self, itens=itens)
        self._erro_add = erro_add
        self._efeito = efeito
        self.chamadas_add = []

    def add(self, pou_name, comment=None):
        self.chamadas_add.append((pou_name, comment))
        if self._erro_add is not None:
            raise self._erro_add
        if self._efeito is not None:
            self._efeito(self._itens, pou_name)
            return
        self._itens.append((pou_name, None))


class WatchdogEstrito(_Estrito):
    _ROTULO = "watchdog"

    def __init__(self, enabled=True, time="10", time_unit="ms",
                 sensitivity="1", erros=None):
        self._valores = {"enabled": enabled, "time": time,
                         "time_unit": time_unit, "sensitivity": sensitivity}
        self._erros = erros or {}

    def _ler(self, campo):
        if campo in self._erros:
            raise self._erros[campo]
        return self._valores[campo]

    @property
    def enabled(self):
        return self._ler("enabled")

    @property
    def time(self):
        return self._ler("time")

    @property
    def time_unit(self):
        return self._ler("time_unit")

    @property
    def sensitivity(self):
        return self._ler("sensitivity")


class NoEstrito(_Estrito):
    """No qualquer da arvore: os dois marcadores, `get_name` e
    `get_children`."""

    _ROTULO = "no da arvore"

    def __init__(self, nome="no", filhos=None, is_task_configuration=False,
                 erro_marcador=None, erro_children=None):
        self._nome = nome
        self._filhos = list(filhos or [])
        self._is_task_configuration = is_task_configuration
        self._erro_marcador = erro_marcador
        self._erro_children = erro_children

    @property
    def is_task_configuration(self):
        if self._erro_marcador is not None:
            raise self._erro_marcador
        return self._is_task_configuration

    @property
    def is_task(self):
        if self._erro_marcador is not None:
            raise self._erro_marcador
        return False

    def get_name(self, recursivo):
        assert recursivo is False
        return self._nome

    def get_children(self, recursivo):
        assert recursivo is False
        if self._erro_children is not None:
            raise self._erro_children
        return ColecaoEstrita(self._filhos)


class TaskEstrita(NoEstrito):
    """`ScriptTaskObject`: os campos catalogados no stub e nada mais."""

    _ROTULO = "task"

    def __init__(self, nome="MainTask", kind_of_task="KindOfTask.Cyclic",
                 priority="1", interval="t#20ms", interval_unit="ms",
                 watchdog=None, pous=None, erros=None, filhos=None):
        NoEstrito.__init__(self, nome=nome, filhos=filhos)
        self._valores = {"name": nome, "kind_of_task": kind_of_task,
                         "priority": priority, "interval": interval,
                         "interval_unit": interval_unit}
        self._watchdog = watchdog if watchdog is not None else WatchdogEstrito()
        self._pous = pous if pous is not None else PousSomenteLeitura()
        self._erros = erros or {}
        self.lidos = []

    def _ler(self, campo):
        self.lidos.append(campo)
        if campo in self._erros:
            raise self._erros[campo]
        return self._valores[campo]

    @property
    def is_task(self):
        return True

    @property
    def name(self):
        return self._ler("name")

    @property
    def kind_of_task(self):
        return self._ler("kind_of_task")

    @property
    def priority(self):
        return self._ler("priority")

    @property
    def interval(self):
        return self._ler("interval")

    @property
    def interval_unit(self):
        return self._ler("interval_unit")

    @property
    def watchdog(self):
        if "watchdog" in self._erros:
            raise self._erros["watchdog"]
        return self._watchdog

    @property
    def pous(self):
        if "pous" in self._erros:
            raise self._erros["pous"]
        return self._pous


class ProjetoEstrito(_Estrito):
    """Projeto para o probe 42: `get_children` e `path`. NAO expoe `save_as`
    -- se o probe read-only tentasse persistir, este duble levantaria."""

    _ROTULO = "projeto (leitura)"

    def __init__(self, filhos=None, path="C:/w/proj.project"):
        self._filhos = list(filhos or [])
        self.path = path

    def get_children(self, recursivo):
        assert recursivo is False
        return ColecaoEstrita(self._filhos)


class ProjetoGravavel(ProjetoEstrito):
    """Projeto para o probe 43: acrescenta `save_as`, e so ele."""

    _ROTULO = "projeto (gravavel)"

    def __init__(self, filhos=None, path="C:/w/proj.project", erro_save=None,
                 criar_arquivo=True):
        ProjetoEstrito.__init__(self, filhos=filhos, path=path)
        self._erro_save = erro_save
        self._criar_arquivo = criar_arquivo
        self.salvo_em = []

    def save_as(self, caminho):
        self.salvo_em.append(caminho)
        if self._erro_save is not None:
            raise self._erro_save
        if self._criar_arquivo:
            handle = open(caminho, "w")
            handle.write("projeto")
            handle.close()


def _arvore_com(no, profundidade=2, classe_projeto=ProjetoEstrito, path=None):
    """Enterra o no alguns niveis, para que a varredura tenha de descer."""
    atual = no
    for indice in range(profundidade):
        atual = NoEstrito(nome="nivel%d" % indice, filhos=[atual])
    kwargs = {"filhos": [NoEstrito(nome="irmao"), atual]}
    if path is not None:
        kwargs["path"] = path
    return classe_projeto(**kwargs)


# =============================================================================
# FALSIFICACAO 1 -- o duble e mesmo um alarme?
# =============================================================================

@pytest.mark.parametrize("mutador", ["add", "insert", "remove", "replace"])
def test_falsificacao_o_duble_de_pous_levanta_em_qualquer_mutador(mutador):
    """Prova que `PousSomenteLeitura` e alarme e nao enfeite. Sem este teste,
    "o duble levantaria" seria so uma frase de docstring -- e um
    `__getattr__` permissivo introduzido amanha passaria despercebido."""
    colecao = PousSomenteLeitura(itens=[("PRG", None)])
    with pytest.raises(AssertionError) as capturado:
        getattr(colecao, mutador)
    assert mutador in str(capturado.value)


def test_falsificacao_o_duble_de_projeto_readonly_levanta_em_save_as():
    with pytest.raises(AssertionError):
        getattr(ProjetoEstrito(), "save_as")


# =============================================================================
# A fonte -- o stub tem de continuar sendo citado com arquivo e linhas
# =============================================================================

def test_a_fonte_e_o_stub_oficial_com_arquivo_e_linhas():
    """A fonte nao pode ser "a documentacao diz": tem de nomear o arquivo e as
    linhas, para que outra pessoa abra o stub e confira."""
    assert probe42.STUB_PATH.endswith("ScriptTaskConfigObject.pyi")
    assert "MT9000 4.1.0" in probe42.STUB_PATH
    assert probe43.STUB_PATH == probe42.STUB_PATH
    assert "21-22" in probe42.MARKER_CHAIN_SOURCE
    assert "39-40" in probe42.MARKER_CHAIN_SOURCE
    assert "is_task_configuration" in probe42.MARKER_CHAIN_SOURCE
    assert "L218-225" in probe42.POUS_SOURCE
    assert "L288-293" in probe42.POUS_SOURCE
    assert "L355-365" in probe42.POUS_SOURCE
    assert "L295-305" in probe43.BIND_SOURCE
    assert "L39-40" in probe43.BIND_SOURCE
    for fonte in (probe42.MARKER_CHAIN_SOURCE, probe42.TASK_FIELDS_SOURCE,
                  probe42.WATCHDOG_FIELDS_SOURCE, probe42.POUS_SOURCE,
                  probe43.BIND_SOURCE):
        assert probe42.STUB_PATH in fonte


def test_os_marcadores_sao_de_tipo_e_a_razao_esta_escrita():
    assert "is_task_configuration" in probe42.MARKER_CHAIN_TASK_CONFIG
    assert "is_task" in probe42.MARKER_CHAIN_TASK
    assert "idioma" in probe42.MARKER_CHAIN_SOURCE


# =============================================================================
# probe 42 -- nucleo puro
# =============================================================================

def test_evidencia_medida_exige_valor():
    ev = probe42.build_evidence([{"name": "MainTask"}], "fonte", None)
    assert ev["status"] == probe42.EVIDENCE_MEASURED
    assert ev["reason"] is None


def test_evidencia_lacuna_exige_valor_nulo_e_razao():
    ev = probe42.build_evidence(None, "fonte", "razao escrita")
    assert ev["status"] == probe42.EVIDENCE_UNRESOLVED
    assert ev["value"] is None
    assert ev["reason"] == "razao escrita"


def test_lista_vazia_e_medida_e_nao_lacuna():
    """A diferenca deliberada em relacao ao probe 41: la zero biblioteca era
    lacuna; aqui zero Program Call e o estado inicial ESPERADO, e distinguir 0
    de 1 e a grandeza que este probe mede."""
    ev = probe42.build_evidence([], "fonte", "razao")
    assert ev["status"] == probe42.EVIDENCE_MEASURED
    assert ev["value"] == []


def test_campo_que_levantou_e_campo_que_devolveu_none_tem_razoes_diferentes():
    """Colapsar as duas ausencias num None mudo obrigaria a proxima pessoa a
    reabrir o MasterTool so para descobrir qual delas aconteceu."""
    levantou = probe42.field_evidence(None, "RuntimeError('sem membro')", "f")
    vazio = probe42.field_evidence(None, None, "f")
    assert levantou["status"] == probe42.EVIDENCE_UNRESOLVED
    assert "sem membro" in levantou["reason"]
    assert probe42.REASON_FIELD_RAISED in levantou["reason"]
    assert vazio["reason"] == probe42.REASON_FIELD_NONE
    assert levantou["reason"] != vazio["reason"]


def test_campo_false_e_medido_e_nao_confundido_com_ausencia():
    """`watchdog.enabled = False` e medida, nao lacuna. Um `if not valor`
    escrito por descuido transformaria "desligado" em "nao lido"."""
    ev = probe42.field_evidence(False, None, "f")
    assert ev["status"] == probe42.EVIDENCE_MEASURED
    assert ev["value"] is False


@pytest.mark.parametrize("no,container,esperado", [
    ("root/1/0/2", "root/1/0", True),
    ("root/10/0", "root/1", False),
    ("root/1", "root/1", False),
    (None, "root/1", False),
])
def test_contencao_e_por_prefixo_com_barra(no, container, esperado):
    """`root/1` nao pode "conter" `root/10`."""
    assert probe42.is_inside(no, container) is esperado


def test_selecao_de_task_por_nome_recusa_ambiguidade():
    tasks = [{"name": {"status": "measured", "value": "MainTask"}},
             {"name": {"status": "measured", "value": "MainTask"}}]
    achada, razao = probe42.find_task_by_name(tasks, "MainTask")
    assert achada is None
    assert razao == probe42.REASON_TASK_AMBIGUOUS


def test_check_binding_encontra_o_vinculo_e_a_posicao():
    tasks = [{
        "node_id": "root/0",
        "name": {"status": "measured", "value": "MainTask"},
        "pous": {"status": "measured",
                 "value": [{"name": "OUTRO"}, {"name": "PRG_AI_TESTE"}]},
    }]
    resultado = probe42.check_binding(tasks, "MainTask", "PRG_AI_TESTE")
    assert resultado["bound"] is True
    assert resultado["position"] == 1
    assert resultado["pous_names"] == ["OUTRO", "PRG_AI_TESTE"]


def test_check_binding_com_lista_ilegivel_nao_vira_nao_vinculado():
    """Lista ilegivel e LACUNA, e nao "o PROGRAM nao esta la": as duas
    conclusoes sao opostas para quem decide promover a saida."""
    tasks = [{
        "node_id": "root/0",
        "name": {"status": "measured", "value": "MainTask"},
        "pous": {"status": "unresolved", "value": None, "reason": "boom"},
    }]
    resultado = probe42.check_binding(tasks, "MainTask", "PRG_AI_TESTE")
    assert resultado["bound"] is False
    assert resultado["pous_readable"] is False
    assert resultado["reason"] == "boom"


def test_check_binding_sem_a_task_diz_qual_elo_faltou():
    resultado = probe42.check_binding([], "MainTask", "PRG")
    assert resultado["task_found"] is False
    assert resultado["reason"] == probe42.REASON_TASK_NOT_FOUND


# =============================================================================
# probe 42 -- varredura e leitura, com os dubles
# =============================================================================

def test_encontra_task_e_task_configuration_pelo_marcador_e_nao_pelo_nome():
    task = TaskEstrita(nome="Tarefa Principal")
    config = NoEstrito(nome="Configuracao de Tarefas", is_task_configuration=True,
                       filhos=[task])
    projeto = ProjetoEstrito(filhos=[NoEstrito(nome="irmao"), config])
    configuracoes, tasks, varredura = probe42.collect_marked_nodes(projeto)
    assert [c["node_id"] for c in configuracoes] == ["root/1"]
    assert [t["node_id"] for t in tasks] == ["root/1/0"]
    assert varredura["errors"] == []


def test_erro_de_marcador_num_no_nao_derruba_a_varredura():
    task = TaskEstrita()
    projeto = ProjetoEstrito(filhos=[
        NoEstrito(nome="ruim", erro_marcador=RuntimeError("sem membro")), task])
    _, tasks, varredura = probe42.collect_marked_nodes(projeto)
    assert [t["node_id"] for t in tasks] == ["root/1"]
    assert any("sem membro" in e for e in varredura["errors"])


def test_le_todos_os_campos_catalogados_de_uma_task():
    pous = PousSomenteLeitura(itens=[("PRG_AI_TESTE", "comentario")])
    task = TaskEstrita(pous=pous)
    entrada = probe42.read_task_entry(task, "root/0/1", [{"node_id": "root/0"}])
    assert entrada["name"]["value"] == "MainTask"
    assert entrada["kind_of_task"]["value"] == "KindOfTask.Cyclic"
    assert entrada["priority"]["value"] == "1"
    assert entrada["interval"]["value"] == "t#20ms"
    assert entrada["interval_unit"]["value"] == "ms"
    assert entrada["watchdog"]["enabled"]["value"] is True
    assert entrada["watchdog"]["time"]["value"] == "10"
    assert entrada["watchdog"]["time_unit"]["value"] == "ms"
    assert entrada["watchdog"]["sensitivity"]["value"] == "1"
    assert entrada["pous"]["value"] == [
        {"index": 0, "name": "PRG_AI_TESTE", "comment": "comentario"}]
    assert entrada["pous_count"] == 1
    assert entrada["within_task_configuration"] == "root/0"


def test_um_campo_que_falha_nao_leva_junto_os_outros():
    task = TaskEstrita(erros={"interval": RuntimeError("nao se aplica")})
    entrada = probe42.read_task_entry(task, "root/0", [])
    assert entrada["name"]["status"] == probe42.EVIDENCE_MEASURED
    assert entrada["interval"]["status"] == probe42.EVIDENCE_UNRESOLVED
    assert "nao se aplica" in entrada["interval"]["reason"]


def test_watchdog_ausente_vira_quatro_lacunas_com_a_mesma_razao():
    task = TaskEstrita(erros={"watchdog": RuntimeError("sem watchdog")})
    entrada = probe42.read_task_entry(task, "root/0", [])
    for campo in ("enabled", "time", "time_unit", "sensitivity"):
        assert entrada["watchdog"][campo]["status"] == probe42.EVIDENCE_UNRESOLVED
        assert "sem watchdog" in entrada["watchdog"][campo]["reason"]


def test_task_sem_program_call_e_medida_com_zero():
    entrada = probe42.read_task_entry(TaskEstrita(), "root/0", [])
    assert entrada["pous"]["status"] == probe42.EVIDENCE_MEASURED
    assert entrada["pous"]["value"] == []
    assert entrada["pous_count"] == 0


def test_item_de_pous_fora_do_formato_do_stub_vira_achado_e_nao_adivinhacao():
    """O stub documenta UMA forma: tupla `(name, comment)`. Se ela nao valer,
    isso e grandeza a MEDIR, e nao algo a adivinhar dentro de um `except`."""
    task = TaskEstrita(pous=PousSomenteLeitura(itens=[("A", None)],
                                               item_estranho=True))
    entrada = probe42.read_task_entry(task, "root/0", [])
    assert entrada["pous"]["status"] == probe42.EVIDENCE_UNRESOLVED
    assert "tupla (name, comment)" in entrada["pous"]["reason"]


def test_lista_de_pous_grande_demais_nao_sai_pela_metade():
    """Uma lista cortada que saisse como MEDIDA poderia "provar" que o PROGRAM
    nao esta vinculado quando ele esta logo depois do corte."""
    itens = [("P%d" % i, None) for i in range(probe42.MAX_POUS_PER_TASK + 1)]
    entradas, erro = probe42.read_pous(TaskEstrita(pous=PousSomenteLeitura(itens)))
    assert entradas is None
    assert "NAO e devolvida pela metade" in erro


# =============================================================================
# probe 42 -- run_probe, com dubles de io/cli
# =============================================================================

class ProbeCliFalso(object):
    def __init__(self, args=None):
        self._args = dict(args or {})

    def find_arg(self, argv, name):
        return self._args.get(name)

    def validate_output_path(self, raw, repo_root, problems):
        if not raw:
            problems.append("--output e obrigatorio")
            return None
        return raw

    def runtime_identity(self):
        return {"file_version": "4.1.0.11"}


class ProjectAccessFalso(object):
    def __init__(self, project, error=None):
        self._project = project
        self._error = error

    def get_primary_project(self, script_globals):
        return self._project, self._error

    def get_project_path(self, project):
        return project.path


class FileIoFalso(object):
    def __init__(self):
        self.json_writes = {}
        self.text_writes = {}
        self.appends = []

    def iso_now(self):
        return "2026-07-31T00:00:00"

    def ensure_dir(self, path):
        return path

    def write_json(self, path, data):
        self.json_writes[os.path.basename(path)] = data
        return path

    def write_text(self, path, text):
        self.text_writes[os.path.basename(path)] = text
        return path

    def append_text(self, path, text):
        self.appends.append((path, text))
        return path


def _cli(**kwargs):
    args = {"output": "C:/fora/artefatos"}
    args.update(kwargs)
    return ProbeCliFalso(args)


def test_run_probe_recon_mede_e_grava_os_tres_artefatos():
    task = TaskEstrita(pous=PousSomenteLeitura(itens=[("PRG_AI_TESTE", None)]))
    projeto = _arvore_com(task)
    file_io = FileIoFalso()
    resultado = probe42.run_probe({}, [], ProjectAccessFalso(projeto), file_io,
                                  _cli())
    assert resultado["status"] == probe42.STATUS_MEASURED
    assert resultado["exit_code"] == 0
    assert resultado["mode"] == probe42.MODE_RECON
    assert resultado["mutating_calls"] == []
    assert resultado["task_summaries"] == [{
        "node_id": "root/1/0/0", "name": "MainTask", "pous_count": 1,
        "pous_names": ["PRG_AI_TESTE"], "within_task_configuration": None}]

    completion = probe42.build_completion(resultado)
    assert completion["is_success"] is True
    assert completion["tasks_count"] == 1

    probe42.write_artifacts(resultado, file_io)
    assert "tasks-completion.json" in file_io.json_writes
    assert "tasks-analysis.json" in file_io.json_writes
    assert "tasks-report.md" in file_io.text_writes


def test_run_probe_sem_task_nao_e_sucesso_e_diz_o_que_isso_significa():
    projeto = ProjetoEstrito(filhos=[NoEstrito(nome="a")])
    resultado = probe42.run_probe({}, [], ProjectAccessFalso(projeto),
                                  FileIoFalso(), _cli())
    assert resultado["status"] == probe42.STATUS_UNRESOLVED
    assert resultado["exit_code"] == 2
    assert "o CLP nao roda nada" in resultado["tasks"]["reason"]


def test_run_probe_com_campo_obrigatorio_ilegivel_e_partial():
    task = TaskEstrita(erros={"pous": RuntimeError("sem pous")})
    resultado = probe42.run_probe({}, [], ProjectAccessFalso(_arvore_com(task)),
                                  FileIoFalso(), _cli())
    assert resultado["status"] == probe42.STATUS_PARTIAL
    assert resultado["exit_code"] == 4
    assert any(probe42.REASON_POUS_UNREADABLE in p for p in resultado["problems"])


def test_run_probe_postsave_confirma_o_vinculo():
    task = TaskEstrita(pous=PousSomenteLeitura(itens=[("PRG_AI_TESTE", None)]))
    resultado = probe42.run_probe(
        {}, [], ProjectAccessFalso(_arvore_com(task)), FileIoFalso(),
        _cli(mode="postsave", **{"expect-task": "MainTask",
                                 "expect-pou": "PRG_AI_TESTE"}))
    assert resultado["status"] == probe42.STATUS_BINDING_VERIFIED
    assert resultado["exit_code"] == 0
    assert resultado["binding"]["bound"] is True
    assert probe42.build_completion(resultado)["binding_verified"] is True


def test_run_probe_postsave_sem_o_vinculo_nao_sai_zero():
    task = TaskEstrita(pous=PousSomenteLeitura(itens=[]))
    resultado = probe42.run_probe(
        {}, [], ProjectAccessFalso(_arvore_com(task)), FileIoFalso(),
        _cli(mode="postsave", **{"expect-task": "MainTask",
                                 "expect-pou": "PRG_AI_TESTE"}))
    assert resultado["status"] == probe42.STATUS_BINDING_MISSING
    assert resultado["exit_code"] == 3
    assert any("vinculo NAO confirmado" in p for p in resultado["problems"])


def test_postsave_sem_o_par_esperado_e_recusado_antes_de_tocar_o_projeto():
    """Se os argumentos forem recusados, o projeto nem chega a ser acessado --
    o duble levantaria se fosse tocado."""
    resultado = probe42.run_probe({}, [], ProjectAccessFalso(None, "n/a"),
                                  FileIoFalso(), _cli(mode="postsave"))
    assert resultado["status"] == probe42.STATUS_FATAL
    assert any("--expect-task" in p for p in resultado["problems"])
    assert any("--expect-pou" in p for p in resultado["problems"])


def test_modo_desconhecido_falha_fechado():
    resultado = probe42.run_probe({}, [], ProjectAccessFalso(None, "n/a"),
                                  FileIoFalso(), _cli(mode="apagar"))
    assert resultado["status"] == probe42.STATUS_FATAL
    assert any("--mode invalido" in p for p in resultado["problems"])


def test_relatorio_mostra_o_program_call_de_cada_task():
    task = TaskEstrita(pous=PousSomenteLeitura(itens=[("PRG_AI_TESTE", None)]))
    resultado = probe42.run_probe({}, [], ProjectAccessFalso(_arvore_com(task)),
                                  FileIoFalso(), _cli())
    texto = probe42.build_report_markdown(resultado)
    assert "PRG_AI_TESTE" in texto
    assert probe42.POUS_CHAIN in texto
    assert probe42.MARKER_CHAIN_TASK in texto


def test_relatorio_diz_NENHUM_quando_a_task_nao_executa_nada():
    resultado = probe42.run_probe({}, [], ProjectAccessFalso(_arvore_com(TaskEstrita())),
                                  FileIoFalso(), _cli())
    assert "Program Call: NENHUM" in probe42.build_report_markdown(resultado)


def test_exit_codes_do_probe_42_cobrem_todos_os_status():
    for status in probe42.ALL_STATUSES:
        assert status in probe42.EXIT_BY_STATUS
        zero = probe42.EXIT_BY_STATUS[status] == 0
        assert zero == (status in probe42.SUCCESS_STATUSES)


# =============================================================================
# probe 43 -- plano e nucleo puro
# =============================================================================

def _sha_de(caminho):
    return hashlib.sha256(open(caminho, "rb").read()).hexdigest()


def _plano_valido(tmp_path, **override):
    base = tmp_path / "base.project"
    base.write_text("projeto base")
    copia = tmp_path / "copia.project"
    copia.write_text("projeto base")
    artefatos = tmp_path / "artefatos"
    plano = {
        "schema_version": "1.0",
        "operation_id": "w2-bind-program-call",
        "phase": "W2_BIND_PROGRAM_CALL",
        "input_project": {"base_path": str(base), "path": str(copia),
                          "sha256": _sha_de(str(copia))},
        "output_project": {"path": str(tmp_path / "saida.project")},
        "operations": [{"kind": "add", "target": "task_pou_collection"},
                       {"kind": "save_as"}],
        "task_name": "MainTask",
        "program_name": "PRG_AI_TESTE",
        "mastertool": {"version": "4.1.0.11", "script_engine": "3.5.17.0"},
        "run_id": "run-020",
        "artifacts_dir": str(artefatos),
    }
    plano.update(override)
    return plano


def _grava_plano(tmp_path, plano):
    caminho = tmp_path / "plano.json"
    caminho.write_text(json.dumps(plano), encoding="utf-8")
    return str(caminho)


def test_plano_valido_passa(tmp_path):
    assert probe43.validate_plan(_plano_valido(tmp_path), _REPO_ROOT) == []


def test_plano_com_fase_alheia_e_recusado(tmp_path):
    problemas = probe43.validate_plan(
        _plano_valido(tmp_path, phase="W1_4_INTEGRATED_BUILD"), _REPO_ROOT)
    assert any("phase inesperada" in p for p in problemas)


def test_plano_com_operacao_a_mais_e_recusado(tmp_path):
    plano = _plano_valido(tmp_path)
    plano["operations"].append({"kind": "build"})
    problemas = probe43.validate_plan(plano, _REPO_ROOT)
    assert any("operations deve ser exatamente" in p for p in problemas)


def test_plano_com_add_sem_alvo_declarado_e_recusado(tmp_path):
    """`add` colide com o metodo homonimo de list. O alvo declarado e o que
    impede que um plano autorize "um add qualquer"."""
    plano = _plano_valido(tmp_path)
    plano["operations"][0]["target"] = "qualquer_colecao"
    problemas = probe43.validate_plan(plano, _REPO_ROOT)
    assert any("task_pou_collection" in p for p in problemas)


def test_plano_com_campo_desconhecido_e_recusado(tmp_path):
    plano = _plano_valido(tmp_path)
    plano["comment"] = "texto livre"
    problemas = probe43.validate_plan(plano, _REPO_ROOT)
    assert any("campo(s) desconhecido(s)" in p for p in problemas)


def test_plano_com_saida_existente_e_recusado(tmp_path):
    plano = _plano_valido(tmp_path)
    (tmp_path / "saida.project").write_text("ja existe")
    problemas = probe43.validate_plan(plano, _REPO_ROOT)
    assert any("save_as nunca sobrescreve" in p for p in problemas)


def test_plano_com_saida_dentro_do_repositorio_e_recusado(tmp_path):
    plano = _plano_valido(tmp_path)
    plano["output_project"]["path"] = os.path.join(_REPO_ROOT, "saida.project")
    problemas = probe43.validate_plan(plano, _REPO_ROOT)
    assert any("dentro do repositorio" in p for p in problemas)


def test_base_path_pode_ter_espaco_e_a_copia_nao(tmp_path):
    """O projeto do cliente MORA num caminho com espaco; quem entra em
    `--scriptargs` e a copia, e e ela que precisa ser livre de espaco."""
    plano = _plano_valido(tmp_path)
    plano["input_project"]["base_path"] = "C:\\TemplateExemplo v1\\TemplateExemplo v1.project"
    assert probe43.validate_plan(plano, _REPO_ROOT) == []
    plano["input_project"]["path"] = "C:\\com espaco\\copia.project"
    assert any("contem espaco" in p
               for p in probe43.validate_plan(plano, _REPO_ROOT))


def test_selecao_de_task_recusa_ausencia_e_ambiguidade():
    tasks = [{"name": "MainTask", "node_id": "root/0"},
             {"name": "MainTask", "node_id": "root/1"}]
    achada, problema = probe43.select_task(tasks, "MainTask")
    assert achada is None and "escolher por acaso" in problema
    achada, problema = probe43.select_task(tasks, "Outra")
    assert achada is None and "nenhuma task" in problema
    achada, problema = probe43.select_task([tasks[0]], "MainTask")
    assert achada is tasks[0] and problema is None


def test_verificacao_do_vinculo_exige_as_tres_condicoes():
    antes = [{"index": 0, "name": "A", "comment": None}]
    depois = antes + [{"index": 1, "name": "PRG", "comment": None}]
    assert probe43.verify_binding(antes, depois, "PRG")["ok"] is True

    # cresceu demais
    sobra = depois + [{"index": 2, "name": "PRG", "comment": None}]
    assert probe43.verify_binding(antes, sobra, "PRG")["ok"] is False
    # prefixo alterado
    trocado = [{"index": 0, "name": "X", "comment": None},
               {"index": 1, "name": "PRG", "comment": None}]
    resultado = probe43.verify_binding(antes, trocado, "PRG")
    assert resultado["ok"] is False and resultado["prefix_intact"] is False
    # cresceu com outro nome
    outro = antes + [{"index": 1, "name": "OUTRO", "comment": None}]
    assert probe43.verify_binding(antes, outro, "PRG")["ok"] is False


# =============================================================================
# probe 43 -- run_bind com dubles, incluindo o duble de safety
# =============================================================================

class SafetyErroFalso(Exception):
    pass


class SafetyFalso(object):
    """Duble da porta unica. Ele REGISTRA o que foi pedido e recusa o que nao
    estiver na allowlist -- as duas coisas importam, porque o artefato afirma
    `no_other_mutator_requested`."""

    SafetyError = SafetyErroFalso

    def __init__(self, phase="W2_BIND_PROGRAM_CALL",
                 allowed=("add", "save_as")):
        self.CONTROLLED_WRITE_PHASE = phase
        self._allowed = set(allowed)
        self.pedidos = []

    def assert_controlled_write_allowed(self, operation):
        self.pedidos.append(operation)
        if operation not in self._allowed:
            raise SafetyErroFalso("operacao %r nao autorizada" % (operation,))
        return True


def _projeto_para_bind(tmp_path, pous=None, erro_save=None, program=True):
    colecao = pous if pous is not None else PousMutavel()
    task = TaskEstrita(pous=colecao)
    filhos = [task]
    if program:
        filhos.append(NoEstrito(nome="PRG_AI_TESTE"))
    config = NoEstrito(nome="Task Configuration", is_task_configuration=True,
                       filhos=filhos)
    projeto = ProjetoGravavel(filhos=[config], path=str(tmp_path / "copia.project"),
                              erro_save=erro_save)
    return projeto, colecao


def _executa_bind(tmp_path, projeto, safety=None, plano=None):
    plano = plano or _plano_valido(tmp_path)
    caminho = _grava_plano(tmp_path, plano)
    file_io = FileIoFalso()
    return probe43.run_bind({}, [], safety or SafetyFalso(),
                            ProjectAccessFalso(projeto), file_io,
                            ProbeCliFalso({"plan": caminho})), file_io


def test_bind_feliz_faz_exatamente_duas_mutacoes_e_salva(tmp_path):
    projeto, colecao = _projeto_para_bind(tmp_path)
    safety = SafetyFalso()
    resultado, file_io = _executa_bind(tmp_path, projeto, safety)
    assert resultado["status"] == probe43.STATUS_SAVED_AS
    assert resultado["exit_code"] == 0
    assert resultado["operations_executed"] == ["add", "save_as"]
    assert safety.pedidos == ["add", "save_as"]
    assert colecao.chamadas_add == [("PRG_AI_TESTE", None)]
    assert projeto.salvo_em == [str(tmp_path / "saida.project")]
    assert resultado["verification"]["ok"] is True

    completion = probe43.build_completion(resultado)
    assert completion["is_success"] is True
    assert completion["no_other_mutator_requested"] is True
    assert completion["pous_after"] == ["PRG_AI_TESTE"]
    probe43.write_artifacts(resultado, file_io)
    assert "bind-completion.json" in file_io.json_writes
    assert "bind-report.md" in file_io.text_writes


def test_bind_e_idempotente_quando_o_vinculo_ja_existe(tmp_path):
    """Acrescentar de novo criaria Program Call duplicado. Nenhuma chamada
    mutavel e emitida -- nem sequer pedida a porta de seguranca."""
    projeto, colecao = _projeto_para_bind(
        tmp_path, pous=PousMutavel(itens=[("PRG_AI_TESTE", None)]))
    safety = SafetyFalso()
    resultado, _ = _executa_bind(tmp_path, projeto, safety)
    assert resultado["status"] == probe43.STATUS_ALREADY_BOUND
    assert resultado["exit_code"] == 2
    assert resultado["operations_requested"] == []
    assert safety.pedidos == []
    assert colecao.chamadas_add == []
    assert projeto.salvo_em == []
    assert resultado["requires_copy_discard"] is False


def test_bind_para_se_a_fase_nao_estiver_autorizada(tmp_path):
    """O estado de HOJE: `W2_BIND_PROGRAM_CALL` nao esta aberta em safety.py.
    O probe para na precondicao, sem tocar o projeto."""
    projeto, colecao = _projeto_para_bind(tmp_path)
    safety = SafetyFalso(phase=None)
    resultado, _ = _executa_bind(tmp_path, projeto, safety)
    assert resultado["status"] == probe43.STATUS_PRECONDITION_FAILED
    assert safety.pedidos == []
    assert colecao.chamadas_add == []
    assert projeto.salvo_em == []
    assert any("fase controlada observada" in p for p in resultado["problems"])


def test_bind_recusa_quando_a_porta_de_seguranca_nega_o_add(tmp_path):
    projeto, colecao = _projeto_para_bind(tmp_path)
    safety = SafetyFalso(allowed=("save_as",))
    resultado, _ = _executa_bind(tmp_path, projeto, safety)
    assert resultado["status"] == probe43.STATUS_PRECONDITION_FAILED
    assert safety.pedidos == ["add"]
    assert projeto.salvo_em == []
    assert any("autorizacao de add recusada" in p for p in resultado["problems"])


def test_bind_sem_o_program_na_arvore_nao_vincula_nome_inexistente(tmp_path):
    projeto, colecao = _projeto_para_bind(tmp_path, program=False)
    resultado, _ = _executa_bind(tmp_path, projeto)
    assert resultado["status"] == probe43.STATUS_PRECONDITION_FAILED
    assert colecao.chamadas_add == []
    assert any("nao existe na arvore varrida" in p for p in resultado["problems"])


def test_bind_sem_a_task_do_plano_para_antes_de_mutar(tmp_path):
    plano = _plano_valido(tmp_path, task_name="TaskQueNaoExiste")
    projeto, colecao = _projeto_para_bind(tmp_path)
    resultado, _ = _executa_bind(tmp_path, projeto, plano=plano)
    assert resultado["status"] == probe43.STATUS_PRECONDITION_FAILED
    assert colecao.chamadas_add == []


def test_bind_com_verificacao_falha_nao_salva_e_manda_descartar(tmp_path):
    """Se o produto nao registrar o que foi pedido, a copia inteira e
    descartada -- nao ha rollback, e `remove` nao seria "desfazer": seria
    outra mutacao."""
    def efeito_errado(itens, nome):
        itens.append(("OUTRA_COISA", None))

    projeto, colecao = _projeto_para_bind(
        tmp_path, pous=PousMutavel(efeito=efeito_errado))
    resultado, _ = _executa_bind(tmp_path, projeto)
    assert resultado["status"] == probe43.STATUS_BIND_VERIFICATION_FAILED
    assert resultado["exit_code"] == 3
    assert resultado["requires_copy_discard"] is True
    assert projeto.salvo_em == []


def test_bind_com_save_as_que_levanta_exige_descarte(tmp_path):
    projeto, _ = _projeto_para_bind(tmp_path, erro_save=RuntimeError("disco cheio"))
    resultado, _ = _executa_bind(tmp_path, projeto)
    assert resultado["status"] == probe43.STATUS_SAVE_AS_FAILED
    assert resultado["requires_copy_discard"] is True


def test_bind_com_projeto_aberto_diferente_do_plano_para(tmp_path):
    projeto, colecao = _projeto_para_bind(tmp_path)
    projeto.path = str(tmp_path / "outro.project")
    resultado, _ = _executa_bind(tmp_path, projeto)
    assert resultado["status"] == probe43.STATUS_PRECONDITION_FAILED
    assert colecao.chamadas_add == []


def test_exit_codes_do_probe_43_cobrem_todos_os_status():
    for status in probe43.ALL_STATUSES:
        assert status in probe43.EXIT_BY_STATUS
        zero = probe43.EXIT_BY_STATUS[status] == 0
        assert zero == (status in probe43.SUCCESS_STATUSES)


# =============================================================================
# A PORTA REAL de safety.py -- fail-closed hoje, e por dois motivos
# =============================================================================

def test_a_fase_deste_marco_foi_aberta_executada_e_ENCERRADA():
    """A fase foi aberta em commit isolado (docs/28 secao 14), DEPOIS de este
    slice entregar os instrumentos.

    Este teste nasceu afirmando o contrario -- que a fase NAO estava aberta --,
    e foi virado de proposito no commit de abertura. A afirmacao muda; o rigor
    nao: antes ele guardava "ninguem abriu ainda", agora guarda "abriu
    exatamente esta, com exatamente estas duas operacoes"."""
    # A entrada FICA no mapa como registro historico; quem autoriza e o
    # ponteiro, e ele voltou a None depois da run-021.
    assert safety_real.CONTROLLED_WRITE_PHASE != probe43.EXPECTED_PHASE
    assert (safety_real.PHASE_ALLOWED_OPERATIONS[probe43.EXPECTED_PHASE]
            == frozenset(["add", "save_as"]))
    # `add` e a operacao PROPRIA de W2, e por isso e ela que prova a recusa --
    # ENQUANTO nenhuma outra fase o autorizar. `save_as` e comum a varias fases
    # e nao discrimina.
    #
    # W8 autoriza `add` de novo, para a task que a spec CRIA: o aviso do
    # fabricante nomeia a `MainTask`, e a task nova nao e ela. Quando a fase
    # ativa o autoriza, o que este teste ainda tem a dizer e DE ONDE veio a
    # autorizacao -- se um dia vier de W2 reaberta, isto reprova.
    ativa = safety_real.CONTROLLED_WRITE_PHASE
    autorizadas = safety_real.PHASE_ALLOWED_OPERATIONS.get(ativa, frozenset())
    if "add" in autorizadas:
        assert ativa in ("W8_PROVE_TASK_WITH_POU", "W9_PROVE_TASK_TIMING"), ativa
    else:
        with pytest.raises(safety_real.SafetyError):
            safety_real.assert_controlled_write_allowed("add")
    # E os vizinhos na MESMA colecao nunca estiveram na allowlist.
    for vizinho in ("insert", "remove", "replace", "create_task"):
        assert vizinho not in safety_real.PHASE_ALLOWED_OPERATIONS[
            probe43.EXPECTED_PHASE]


def test_falsificacao_fase_sem_allowlist_falha_FECHADO(monkeypatch):
    """A guarda que a abertura da fase NAO pode ter enfraquecido: apontar o
    ponteiro para uma fase que nao tem allowlist ainda recusa -- configuracao
    incompleta falha FECHADO.

    Antes da abertura, este teste usava a propria fase de W2 como exemplo de
    "fase sem allowlist". Agora ela TEM allowlist, entao o exemplo passou a
    ser um nome inventado -- se ele continuasse usando W2, passaria pelo
    motivo errado e nao provaria mais nada."""
    inexistente = "W2_BIND_PROGRAM_CALL_QUE_NINGUEM_DECLAROU"
    assert inexistente not in safety_real.PHASE_ALLOWED_OPERATIONS
    monkeypatch.setattr(safety_real, "CONTROLLED_WRITE_PHASE", inexistente)
    with pytest.raises(safety_real.SafetyError) as capturado:
        safety_real.assert_controlled_write_allowed("add")
    assert "allowlist" in str(capturado.value)


def test_as_duas_operacoes_deste_marco_ja_estao_no_registro_literal():
    """`add` e `save_as` ja constam de MASTERTOOL_MUTATING_OPERATIONS. Nada
    precisou ser acrescentado a safety.py por este slice."""
    assert "add" in safety_real.MASTERTOOL_MUTATING_OPERATIONS
    assert "save_as" in safety_real.MASTERTOOL_MUTATING_OPERATIONS


# =============================================================================
# Verificacao estatica (AST) -- por RECEPTOR, nunca por nome de metodo
# =============================================================================

@pytest.fixture(scope="module")
def tree42():
    return ast.parse(io.open(PROBE42_PATH, encoding="utf-8").read())


@pytest.fixture(scope="module")
def tree43():
    return ast.parse(io.open(PROBE43_PATH, encoding="utf-8").read())


def _receptor(no):
    """Rende o receptor de uma chamada como texto estavel.

    E o RECEPTOR que decide se uma chamada e perigosa, nunca o nome do metodo:
    `.add(...)` num `set` Python e inofensivo, e `.add(...)` na colecao de POUs
    de uma task acrescenta um Program Call ao projeto do cliente. Proibir NOMES
    reprovaria codigo legitimo e ainda assim deixaria passar o mutador que
    ninguem listou.
    """
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return _receptor(no.value) + "." + no.attr
    if isinstance(no, ast.Subscript):
        return "<subscript>"
    if isinstance(no, ast.Call):
        return "<call>"
    if isinstance(no, ast.Constant):
        return "<literal>"
    return "<expr>"


def _mapa_de_chamadas(tree):
    mapa = {}
    for no in ast.walk(tree):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            mapa.setdefault(_receptor(no.func.value), set()).add(no.func.attr)
    return dict((k, sorted(v)) for k, v in mapa.items())


# O mapa COMPLETO de "quem chama o que" no probe 42, congelado. O UNICO
# receptor que e proxy do MasterTool e `node` -- e `system`, que so recebe
# `exit`. A colecao de POUs nao aparece aqui porque o probe 42 NAO chama metodo
# nenhum sobre ela: le por `len(...)` e pelo indexador.
MAPA42_CONGELADO = {
    "<call>": ["strip"],
    "<expr>": ["get"],
    "<literal>": ["join"],
    "<subscript>": ["append"],
    "EXIT_BY_STATUS": ["get"],
    "binding": ["get"],
    "configuracao": ["get"],
    "configuracoes": ["append"],
    "encontradas": ["append"],
    "entrada": ["get"],
    "entradas": ["append"],
    "evidencia": ["get"],
    "evidencia_pous": ["get"],
    "file_io": ["ensure_dir", "write_json", "write_text"],
    "filhos": ["append"],
    "item": ["get"],
    "lines": ["append"],
    "no_marcado": ["get"],
    "node": ["get_children", "get_name"],
    "node_id": ["startswith"],
    "os.path": ["abspath", "dirname", "join"],
    "passo": ["get"],
    "passos": ["append"],
    "pilha": ["append", "pop"],
    "probe_cli": ["find_arg", "runtime_identity", "validate_output_path"],
    "problems": ["append"],
    "project_access": ["get_primary_project", "get_project_path"],
    "result": ["get"],
    "script_globals": ["get"],
    "sys": ["exit"],
    "sys.path": ["insert"],
    "system": ["exit"],
    "task_entry": ["get"],
    "tasks": ["append"],
    # O probe 42 continua com `print_exc`: ele e READ-ONLY, e o veredito dele
    # nao decide descarte de copia. Quem precisou do rastro como TEXTO foi o
    # probe 43, cujo artefato fatal tem de dizer se a copia pode ser reusada.
    "traceback": ["print_exc"],
    "value": ["strip"],
    "watchdog": ["get"],
    "written": ["append"],
}

# O mesmo para o probe 43. Os proxies do MasterTool sao `node` (leitura),
# `pou_collection` (a UNICA mutacao de estrutura) e `project` (a UNICA
# persistencia). `system` so recebe `exit`.
MAPA43_CONGELADO = {
    # --- proxies do MasterTool: AS DUAS MUTACOES E MAIS NADA ----------------
    #
    # `pou_collection.add` e `project.save_as` sao as unicas chamadas que
    # escrevem. `ScriptPouObjectCollection` HERDA de `list`, entao proibir o
    # NOME `add` seria inutil nas duas direcoes: reprovaria `set.add` legitimo
    # e nao distinguiria a chamada que escreve no projeto. E o RECEPTOR que
    # decide, e e por isso que este mapa existe.
    'node': ['get_children', 'get_name'],
    'pou_collection': ['add'],
    'project': ['save_as'],
    'safety': ['assert_controlled_write_allowed'],
    'system': ['exit'],
    # --- modulos proprios e estruturas Python -------------------------------
    #
    # `os.makedirs` e os `write`/`close` de `marcador` e `alvo` gravam com
    # `open` puro, sem `file_io`: eles servem ao caminho de EVIDENCIA
    # (marcador de inicio e artefato fatal), e uma falha ao importar
    # `common` e justamente um dos casos que precisam ser registrados.
    '<expr>': ['get'],
    '<call>': ['decode', 'encode', 'get', 'hexdigest', 'index', 'read', 'strip'],
    '<literal>': ['join'],
    '<subscript>': ['append', 'extend', 'get'],
    'EXIT_BY_STATUS': ['get'],
    'alvo': ['close', 'write'],
    'antes': ['count'],
    'bruto': ['split', 'startswith'],
    'depois': ['count'],
    'digest': ['hexdigest', 'update'],
    'entradas': ['append'],
    'file_io': ['append_text', 'ensure_dir', 'write_json', 'write_text'],
    'filhos': ['append'],
    'handle': ['close', 'read'],
    'hashlib': ['sha256'],
    'input_project': ['get'],
    'item': ['get'],
    'journal': ['record'],
    'json': ['dumps', 'loads'],
    'kinds': ['append'],
    'lines': ['append'],
    'marcador': ['close', 'write'],
    'mastertool': ['get'],
    'nomes': ['append'],
    'normalized': ['startswith'],
    'os': ['makedirs'],
    'os.path': ['abspath', 'dirname', 'exists', 'isabs', 'isdir', 'isfile', 'join', 'normcase'],
    'output_project': ['get'],
    'pilha': ['append', 'pop'],
    'plan': ['get'],
    'plano': ['get'],
    'probe_cli': ['find_arg', 'runtime_identity'],
    'problems': ['append'],
    'project_access': ['get_primary_project', 'get_project_path'],
    'raw': ['decode'],
    'result': ['get'],
    'script_globals': ['get'],
    'self': ['now'],
    'self.entries': ['append'],
    'sys': ['exit'],
    'sys.path': ['insert'],
    'task_entry': ['get'],
    'tasks': ['append'],
    'text': ['encode'],
    'traceback': ['format_exc'],
    'unknown': ['append', 'sort'],
    'value': ['lower', 'strip'],
    'varredura': ['get'],
    'verificacao': ['get'],
    'written': ['append'],
}


def test_mapa_de_chamadas_do_probe_42_esta_congelado(tree42):
    assert _mapa_de_chamadas(tree42) == MAPA42_CONGELADO, (
        "o conjunto de chamadas por receptor do probe 42 mudou. Se a mudanca "
        "for legitima, atualize MAPA42_CONGELADO -- e leia com atencao a linha "
        "de `node`, que e o unico proxy do MasterTool")


def test_mapa_de_chamadas_do_probe_43_esta_congelado(tree43):
    assert _mapa_de_chamadas(tree43) == MAPA43_CONGELADO, (
        "o conjunto de chamadas por receptor do probe 43 mudou. Se a mudanca "
        "for legitima, atualize MAPA43_CONGELADO -- e leia com atencao as "
        "linhas de `pou_collection` e `project`, que sao as DUAS mutacoes")


def test_o_probe_42_nao_chama_metodo_algum_sobre_proxy_alem_da_leitura(tree42):
    mapa = _mapa_de_chamadas(tree42)
    assert mapa["node"] == ["get_children", "get_name"]
    assert mapa["system"] == ["exit"]
    assert "pou_collection" not in mapa
    assert "project" not in mapa


def test_o_probe_43_tem_exatamente_duas_chamadas_mutaveis(tree43):
    mapa = _mapa_de_chamadas(tree43)
    assert mapa["pou_collection"] == ["add"]
    assert mapa["project"] == ["save_as"]
    assert mapa["node"] == ["get_children", "get_name"]
    chamadas = _chamadas_mutaveis(tree43)
    assert len(chamadas) == 2
    assert [(c["receptor"], c["metodo"]) for c in chamadas] == [
        ("pou_collection", "add"), ("project", "save_as")]


def _atribuicoes_de_atributo(tree):
    """`(receptor, atributo)` de toda escrita de atributo. Por RECEPTOR, pela
    mesma razao das chamadas: `self.path = ...` num journal do proprio probe
    nao e a mesma coisa que escrever num proxy do produto."""
    return sorted(set(
        (_receptor(no.value), no.attr) for no in ast.walk(tree)
        if isinstance(no, ast.Attribute)
        and isinstance(no.ctx, (ast.Store, ast.Del))))


def test_o_probe_42_nao_atribui_atributo_algum(tree42):
    """`kind_of_task`, `priority`, `interval`, `interval_unit`, `event`,
    `core_binding` e os campos do watchdog TEM setter no stub. Uma unica
    atribuicao de atributo escreveria no projeto sem chamar metodo nenhum, e
    passaria por baixo de qualquer guarda que so olhe chamadas. No probe
    read-only nao ha nenhuma, de nenhum tipo."""
    assert _atribuicoes_de_atributo(tree42) == []


def test_as_atribuicoes_do_probe_43_sao_todas_em_objeto_proprio(tree43):
    """O probe 43 escreve atributo -- mas so no `Journal` que ele mesmo cria.
    Nenhuma delas tem por receptor um proxy do MasterTool, e a lista esta
    congelada: uma escrita nova, em qualquer receptor, derruba este teste."""
    esperadas = [("journal", "path"), ("self", "entries"), ("self", "now"),
                 ("self", "path")]
    assert _atribuicoes_de_atributo(tree43) == esperadas
    for receptor, _ in _atribuicoes_de_atributo(tree43):
        assert receptor not in RECEPTORES_MUTAVEIS
        assert receptor != "node"


@pytest.mark.parametrize("membro", ["is_task_configuration", "is_task", "Count",
                                    "name", "kind_of_task", "priority",
                                    "interval", "interval_unit", "watchdog",
                                    "enabled", "time", "time_unit",
                                    "sensitivity", "pous", "get_children",
                                    "get_name"])
def test_cada_membro_do_produto_aparece_uma_unica_vez_no_probe_42(tree42, membro):
    """Uma ocorrencia no fonte inteiro. Duas seriam retentativa, cascata de
    acessores ou segunda rota nao declarada -- as tres proibidas por
    contrato."""
    ocorrencias = [no for no in ast.walk(tree42)
                   if isinstance(no, ast.Attribute) and no.attr == membro]
    assert len(ocorrencias) == 1


@pytest.mark.parametrize("membro", ["is_task", "pous", "add", "save_as",
                                    "get_children", "get_name", "Count"])
def test_cada_membro_do_produto_aparece_uma_unica_vez_no_probe_43(tree43, membro):
    ocorrencias = [no for no in ast.walk(tree43)
                   if isinstance(no, ast.Attribute) and no.attr == membro]
    assert len(ocorrencias) == 1


@pytest.mark.parametrize("nome", ["getattr", "setattr", "delattr", "hasattr",
                                  "eval", "exec", "compile", "__import__",
                                  "vars", "locals", "dir"])
@pytest.mark.parametrize("probe", ["42", "43"])
def test_sem_acesso_dinamico_em_probe_algum(probe, nome, tree42, tree43):
    """Reflexao foi o instrumento de INVESTIGACAO das DLLs, fora do produto.
    Dentro do probe seria a invencao de API que estes arquivos eliminam."""
    tree = tree42 if probe == "42" else tree43
    encontrados = [n for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nome]
    assert encontrados == []


@pytest.mark.parametrize("caminho", [PROBE42_PATH, PROBE43_PATH])
def test_compativel_com_ironpython_27(caminho):
    fonte = io.open(caminho, encoding="utf-8").read()
    tree = ast.parse(fonte)
    assert "from __future__ import print_function" in fonte
    assert "yield from" not in fonte
    assert "pathlib" not in fonte
    assert [n for n in ast.walk(tree)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []
    for node in ast.walk(tree):
        assert not isinstance(node, ast.AnnAssign)
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None
            for arg in node.args.args:
                assert getattr(arg, "annotation", None) is None
    assert "basestring" in fonte


@pytest.mark.parametrize("caminho", [PROBE42_PATH, PROBE43_PATH])
def test_probes_sao_ascii_puro(caminho):
    dados = io.open(caminho, "rb").read()
    fora = [b for b in bytearray(dados) if b > 127]
    assert fora == [], "%s tem %d byte(s) > 127" % (caminho, len(fora))


@pytest.mark.parametrize("nome", NOMES_MUTADORES_DE_TASK)
def test_o_probe_42_nao_chama_mutador_algum_sobre_proxy(tree42, nome):
    """A metade que sobrevive a uma atualizacao do mapa congelado."""
    encontrados = []
    for chamada in ast.walk(tree42):
        if not (isinstance(chamada, ast.Call)
                and isinstance(chamada.func, ast.Attribute)):
            continue
        if chamada.func.attr != nome:
            continue
        receptor = _receptor(chamada.func.value)
        if receptor == "sys.path":     # `sys.path.insert` nao e a colecao
            continue
        encontrados.append((receptor, chamada.lineno))
    assert encontrados == []


# =============================================================================
# GUARDA POR ADJACENCIA -- e as falsificacoes que provam que ela acusa
# =============================================================================

def _guarda_da_linha_anterior(corpo, indice):
    """A guarda tem de ser o statement IMEDIATAMENTE anterior, no mesmo corpo.

    Devolve o literal que ela nomeia, ou None. Nada de "existe uma guarda em
    algum lugar da funcao": entre a guarda e a chamada nao pode haver ramo,
    laco, wrapper nem log, e adjacencia e a unica forma barata de exigir isso.
    """
    if indice == 0:
        return None
    anterior = corpo[indice - 1]
    if not isinstance(anterior, ast.Expr):
        return None
    chamada = anterior.value
    if not (isinstance(chamada, ast.Call)
            and isinstance(chamada.func, ast.Attribute)
            and chamada.func.attr == GUARDA):
        return None
    if len(chamada.args) != 1 or not isinstance(chamada.args[0], ast.Constant):
        return None
    return chamada.args[0].value


def _chamadas_mutaveis(tree, receptores=None):
    """Toda chamada, em qualquer corpo, cujo RECEPTOR seja um proxy mutavel
    conhecido. Devolve tambem se a guarda adjacente existe e qual literal ela
    nomeia."""
    receptores = receptores or RECEPTORES_MUTAVEIS
    achadas = []
    for no in ast.walk(tree):
        corpo = getattr(no, "body", None)
        if not isinstance(corpo, list):
            continue
        for indice, statement in enumerate(corpo):
            if not isinstance(statement, ast.Expr):
                continue
            chamada = statement.value
            if not (isinstance(chamada, ast.Call)
                    and isinstance(chamada.func, ast.Attribute)):
                continue
            receptor = _receptor(chamada.func.value)
            if receptor not in receptores:
                continue
            achadas.append({
                "receptor": receptor,
                "metodo": chamada.func.attr,
                "linha": chamada.lineno,
                "literal_da_guarda": _guarda_da_linha_anterior(corpo, indice),
                "literal_esperado": receptores[receptor],
            })
    achadas.sort(key=lambda item: item["linha"])
    return achadas


def test_cada_mutacao_do_probe_43_tem_a_guarda_adjacente_com_o_literal_certo(tree43):
    chamadas = _chamadas_mutaveis(tree43)
    assert len(chamadas) == 2
    for chamada in chamadas:
        assert chamada["literal_da_guarda"] == chamada["literal_esperado"], chamada
    assert [c["literal_da_guarda"] for c in chamadas] == ["add", "save_as"]


FONTE_SEM_GUARDA = '''
def add_program_call_guarded(pou_collection, program_name, safety):
    pou_collection.add(program_name)
    return True
'''

FONTE_COM_LITERAL_ERRADO = '''
def add_program_call_guarded(pou_collection, program_name, safety):
    safety.assert_controlled_write_allowed("save_as")
    pou_collection.add(program_name)
    return True
'''

FONTE_COM_GUARDA_DISTANTE = '''
def add_program_call_guarded(pou_collection, program_name, safety):
    safety.assert_controlled_write_allowed("add")
    print("acrescentando")
    pou_collection.add(program_name)
    return True
'''

FONTE_COM_ADD_DE_COLECAO_PYTHON = '''
def resume(nomes, entradas, vistos):
    vistos.add("PRG_AI_TESTE")
    entradas.append("PRG_AI_TESTE")
    nomes.insert(0, "PRG_AI_TESTE")
    nomes.remove("PRG_AI_TESTE")
    return vistos
'''


def test_falsificacao_add_sem_guarda_adjacente_e_detectado():
    """FALSIFICACAO EXIGIDA. Sem este teste, "toda mutacao tem guarda" poderia
    estar passando por vacuidade -- por exemplo se o detector procurasse a
    guarda no arquivo inteiro em vez de na linha anterior."""
    chamadas = _chamadas_mutaveis(ast.parse(FONTE_SEM_GUARDA))
    assert len(chamadas) == 1
    assert chamadas[0]["receptor"] == "pou_collection"
    assert chamadas[0]["metodo"] == "add"
    assert chamadas[0]["literal_da_guarda"] is None


def test_falsificacao_guarda_com_o_literal_errado_e_detectada():
    """Uma guarda que nomeia OUTRA operacao autorizaria a operacao errada --
    e o journal registraria uma coisa enquanto o produto faria outra."""
    chamada = _chamadas_mutaveis(ast.parse(FONTE_COM_LITERAL_ERRADO))[0]
    assert chamada["literal_da_guarda"] == "save_as"
    assert chamada["literal_da_guarda"] != chamada["literal_esperado"]


def test_falsificacao_guarda_afastada_por_uma_linha_e_detectada():
    """Adjacencia e o requisito: um `print` entre a guarda e a chamada ja
    abriria espaco para um `if` amanha."""
    chamada = _chamadas_mutaveis(ast.parse(FONTE_COM_GUARDA_DISTANTE))[0]
    assert chamada["literal_da_guarda"] is None


def test_falsificacao_add_de_colecao_python_nao_e_confundido_com_o_mutador():
    """FALSIFICACAO EXIGIDA, e a razao de a verificacao ser por RECEPTOR.

    `set.add`, `list.append`, `list.insert` e `list.remove` colidem em NOME com
    os mutadores de `ScriptPouObjectCollection` -- que herda de `list`. Uma
    guarda por nome reprovaria este trecho inteiro, que nao toca o produto; a
    guarda por receptor nao acusa nada aqui, e continua acusando o mutador de
    verdade (teste acima).
    """
    tree = ast.parse(FONTE_COM_ADD_DE_COLECAO_PYTHON)
    assert _chamadas_mutaveis(tree) == []
    mapa = _mapa_de_chamadas(tree)
    assert mapa["vistos"] == ["add"]          # existe um `.add` no trecho
    assert set(mapa) & set(RECEPTORES_MUTAVEIS) == set()


def test_falsificacao_o_detector_acha_o_mutador_no_probe_real_e_nao_no_falso():
    """As duas pontas no mesmo teste: o mesmo detector que ignora o `.add`
    de colecao Python encontra as duas mutacoes do probe 43."""
    reais = _chamadas_mutaveis(ast.parse(io.open(PROBE43_PATH, encoding="utf-8").read()))
    falsas = _chamadas_mutaveis(ast.parse(FONTE_COM_ADD_DE_COLECAO_PYTHON))
    assert len(reais) == 2 and falsas == []
