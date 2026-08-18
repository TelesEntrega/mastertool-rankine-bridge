"""O contrato entre o núcleo e o produto operacional.

Seis schemas descrevem tudo que atravessa a fronteira entre as duas árvores.
Quatro deles nunca existiram: o probe gravava, o host lia, e nada conferia a
forma.

**Todas as fixtures aqui são sintéticas.** Nenhum caminho local, nenhum hash
de artefato interno, nenhum id de run interna — este arquivo é publicado. A
validação contra artefato REAL de campo mora em
`tests/unit/test_operational_contract_field.py`, que não é publicado, porque
os artefatos reais carregam caminho de máquina.
"""

import json

import pytest

from mastertool_bridge.contract import (
    FAMILY_PROBE,
    FAMILY_SRC,
    SCHEMA_FAMILY,
    SCHEMAS,
    load_schema,
    schema_path,
    validate,
)

SHA = "b" * 64


# =============================================================================
# forma do contrato
# =============================================================================

def test_os_seis_schemas_existem_em_disco():
    """Um contrato com schema faltando não é um contrato: é uma promessa."""
    assert len(SCHEMAS) == 6
    for nome in SCHEMAS:
        assert schema_path(nome).is_file(), nome


def test_todo_schema_e_json_valido_e_declara_id_e_titulo():
    for nome in SCHEMAS:
        schema = load_schema(nome)
        assert schema["$id"], nome
        assert schema["title"], nome
        assert schema["description"], nome


def test_todo_schema_e_FECHADO_no_topo():
    """`additionalProperties: false` é o que faz um campo desconhecido
    recusar em vez de ser ignorado. Campo que o validador não entende pode ser
    justamente o que mudaria o significado dos outros."""
    for nome in SCHEMAS:
        assert load_schema(nome)["additionalProperties"] is False, nome


def test_nome_fora_do_contrato_LEVANTA():
    """Devolver `None` faria um erro de digitação virar "sem schema", e sem
    schema tudo passa."""
    with pytest.raises(KeyError):
        schema_path("nao-existe")


def test_toda_familia_esta_declarada():
    assert set(SCHEMA_FAMILY) == set(SCHEMAS)
    assert set(SCHEMA_FAMILY.values()) == {FAMILY_PROBE, FAMILY_SRC}


def test_a_familia_declarada_bate_com_o_schema():
    """As DUAS famílias de `schema_version` (docs/19 §7), conferidas contra o
    que cada schema realmente exige.

    Artefato de probe usa a string "1.0"; a camada `src/` usa inteiro. Um
    contrato único que exigisse inteiro em todos recusaria todo artefato de
    campo já produzido — inclusive os que sustentam R1 e R2."""
    for nome, familia in SCHEMA_FAMILY.items():
        exigido = load_schema(nome)["properties"]["schema_version"]
        valor = exigido.get("const")
        if familia == FAMILY_PROBE:
            assert valor == "1.0", (nome, valor)
            assert isinstance(valor, str), nome
        else:
            assert valor == 1, (nome, valor)
            assert isinstance(valor, int), nome


# =============================================================================
# cada schema aprova o artefato certo e recusa o errado
# =============================================================================

def _manifesto():
    return {"schema_version": "1.0", "script": "probes/46_x.py",
            "phase": "W_EXEMPLO", "plan_path": "plano.json",
            "plan_sha256": SHA, "spec_path": "spec.json", "spec_sha256": SHA,
            "journal": [{"evento": "abriu"}]}


def _conclusao():
    return {"schema_version": "1.0", "script": "probes/46_x.py",
            "status": "plan_executed", "exit_code": 0, "is_success": True,
            "errors": [], "generated_at": "2026-01-01T00:00:00"}


def _verificacao():
    return {"schema_version": "1.0", "script": "probes/47_x.py",
            "status": "factory_output_verified", "exit_code": 0,
            "is_success": True, "errors": [],
            "generated_at": "2026-01-01T00:00:00"}


def _bundle():
    return {"schema_version": 1, "run_id": "run-sintetica-001",
            "status": "sealed_complete", "complete": True,
            "files": {"source/project.sha256": SHA},
            "missing_required": [], "bundle_sha256": SHA}


CASOS = [
    ("execution-manifest", _manifesto),
    ("execution-completion", _conclusao),
    ("verification-result", _verificacao),
    ("evidence-bundle", _bundle),
]


@pytest.mark.parametrize("nome,fabrica", CASOS)
def test_artefato_bem_formado_passa(nome, fabrica):
    assert validate(nome, fabrica()) == []


@pytest.mark.parametrize("nome,fabrica", CASOS)
def test_campo_ADICIONAL_recusa(nome, fabrica):
    doc = fabrica()
    doc["campo_que_ninguem_conhece"] = 1
    assert validate(nome, doc) != []


@pytest.mark.parametrize("nome,fabrica", CASOS)
def test_campo_OBRIGATORIO_ausente_recusa(nome, fabrica):
    schema = load_schema(nome)
    for obrigatorio in schema["required"]:
        doc = fabrica()
        doc.pop(obrigatorio, None)
        assert validate(nome, doc) != [], (nome, obrigatorio)


@pytest.mark.parametrize("nome,fabrica", CASOS)
def test_schema_version_da_OUTRA_familia_recusa(nome, fabrica):
    """O erro que as duas famílias existem para pegar: alguém gravar inteiro
    onde o artefato de probe usa string, ou o contrário."""
    doc = fabrica()
    doc["schema_version"] = 1 if SCHEMA_FAMILY[nome] == FAMILY_PROBE else "1.0"
    assert validate(nome, doc) != []


def test_status_fora_do_vocabulario_recusa():
    """Status desconhecido não pode ser tratado como aprovação — um veredito
    que ninguém sabe interpretar não é um veredito."""
    doc = _conclusao()
    doc["status"] = "quase_deu_certo"
    assert validate("execution-completion", doc) != []

    doc = _verificacao()
    doc["status"] = "mais_ou_menos_verificado"
    assert validate("verification-result", doc) != []


def test_hash_malformado_recusa():
    doc = _bundle()
    doc["bundle_sha256"] = "nao-e-hash"
    assert validate("evidence-bundle", doc) != []

    doc = _bundle()
    doc["files"] = {"x": "curto"}
    assert validate("evidence-bundle", doc) != []


def test_journal_e_OBRIGATORIO_no_manifesto():
    """Uma execução sem journal não é auditável de forma nenhuma. Lista vazia
    é um journal vazio; campo ausente é outra coisa."""
    doc = _manifesto()
    doc["journal"] = []
    assert validate("execution-manifest", doc) == []
    doc.pop("journal")
    assert validate("execution-manifest", doc) != []


def test_phase_NULL_e_aceita_e_significa_nao_medido():
    """`null` não é "nenhuma fase": é "o probe morreu antes de ler". Recusar
    o `null` faria o artefato de uma falha precoce ser inválido, e é
    justamente ele que precisa ser lido."""
    doc = _manifesto()
    doc["phase"] = None
    assert validate("execution-manifest", doc) == []


def test_bundle_sealed_incomplete_e_um_documento_VALIDO():
    """Selar incompleto é o comportamento correto — a execução que deu errado
    é a que mais precisa ficar registrada. O que `sealed_incomplete` não faz é
    confirmar capacidade na attestation, e isso é decisão do loader, não do
    schema."""
    doc = _bundle()
    doc.update(status="sealed_incomplete", complete=False,
               missing_required=["plan/specification.json"])
    assert validate("evidence-bundle", doc) == []


# =============================================================================
# os dois schemas que MUDARAM de lugar
# =============================================================================

def test_os_schemas_movidos_tem_UM_lugar_so():
    """Duas cópias de um schema divergem. Seria estranho criar um contrato
    entre árvores já duplicado."""
    from mastertool_bridge import attestation, planner

    for pacote in (planner, attestation):
        raiz = __import__("pathlib").Path(pacote.__file__).parent
        assert not list(raiz.glob("*.schema.json")), raiz


def test_o_contrato_VIAJA_com_o_pacote():
    """Diretório de topo não entra na wheel. Um contrato que só existe em
    checkout não é honrado por um core instalado — e os dois schemas
    anteriores nunca foram empacotados, porque `package-data` só listava
    `schemas/*.json`."""
    import io
    import os

    raiz = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    toml = io.open(os.path.join(raiz, "pyproject.toml"), encoding="utf-8").read()
    assert 'contract/*.json' in toml


def test_o_plano_real_do_planner_valida_contra_o_contrato():
    """O schema movido continua descrevendo o que o planner emite."""
    from mastertool_bridge.planner.planner import build_authoring_plan

    spec = {"schema_version": 1, "template": {"id": "x", "sha256": "a" * 64},
            "programs": [{"name": "P1",
                          "declaration": "PROGRAM P1\nEND_PROGRAM",
                          "implementation": ";",
                          "language": {"guid": "cc393387-a21c-4f68-a3e3-84c36951965d"}}]}
    resultado = build_authoring_plan(spec)
    assert resultado.plan is not None, resultado.problems
    assert validate("authoring-plan", resultado.plan) == []


def test_a_attestation_sintetica_valida_contra_o_contrato():
    doc = {"schema_version": 1, "core_contract_sha256": SHA,
           "issued_from_commit": "a" * 40,
           "product": "MasterTool X", "product_version": "4.1.0.11",
           "template_profile": "perfil-sintetico-v1",
           "capabilities": {"create_program": {
               "maturity": "repeatable", "independent_runs": 10,
               "bundle_sha256": SHA, "evidence_id": "EVID-SINTETICA"}}}
    assert validate("capability-attestation", doc) == []


def test_o_fingerprint_do_contrato_e_REPRODUTIVEL():
    """Duas chamadas dão o mesmo hash, e o objeto é montado pelo código.

    Se ele dependesse de ordem de dicionário, de caminho de arquivo ou do
    relógio, o núcleo público e a árvore interna calculariam hashes
    diferentes e nenhuma attestation valeria nos dois."""
    from mastertool_bridge.contract.fingerprint import (
        core_contract,
        core_contract_bytes,
        core_contract_sha256,
    )

    assert core_contract_sha256() == core_contract_sha256()
    assert core_contract_bytes() == core_contract_bytes()
    assert len(core_contract_sha256()) == 64

    contrato = core_contract()
    # O que DECIDE está lá dentro. Faltando um, mudá-lo não invalidaria nada.
    for chave in ("contract_version", "maturity_scale", "minimum_runs",
                  "known_capabilities", "operation_capabilities",
                  "property_write_capabilities", "policies", "schema_hashes"):
        assert chave in contrato, chave
    assert set(contrato["policies"]) == {
        "effective_maturity", "bundle_confirmation", "independence_evidence",
        "planner_threshold"}
    assert set(contrato["schema_hashes"]) == set(SCHEMAS)


def test_o_piso_de_field_proven_esta_no_fingerprint():
    """Ele é DERIVADO — `MIN_INDEPENDENT_RUNS` só tem entrada de `repeatable`
    para cima —, e foi a ausência dele que deixou `field_proven` com zero runs
    passar. Registrar a tabela crua em vez da política aplicada faria mudar o
    piso derivado não invalidar nada."""
    from mastertool_bridge.contract.fingerprint import core_contract

    assert core_contract()["minimum_runs"]["field_proven"] == 1


