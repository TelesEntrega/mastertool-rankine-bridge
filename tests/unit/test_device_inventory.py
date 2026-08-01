"""Testes de `mastertool_bridge.inventory.device_inventory`.

Fixtures **inteiramente sintéticas**: nenhum IP, nome de planta, caminho local
ou identificador de projeto real aparece aqui. Dado industrial fica fora do
repositório por decisão explícita — ver `docs/25`.
"""

import json

import pytest

from mastertool_bridge.inventory import device_inventory as di

NS = 'xmlns="http://www.plcopen.org/xml/tc6_0200"'


def _export(configuration, device_type, interfaces, parameters_xml,
            device_id="0000 0001", version="1.0.0.0"):
    conectores = "".join(
        f'<Connector interface="{i}" connectorId="{n}">'
        f"<HostParameterSet />"
        f"</Connector>"
        for n, i in enumerate(interfaces, start=1))
    tipo = f"<Type>{device_type}</Type>" if device_type is not None else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<project {NS}>\n"
        "<instances><configurations>"
        f'<configuration name="{configuration}">'
        '<addData><data name="Device"><Device><DeviceType>'
        f"<DeviceIdentification>{tipo}<Id>{device_id}</Id>"
        f"<Version>{version}</Version></DeviceIdentification>"
        f"{conectores}"
        '<Connector interface="Host" connectorId="9"><HostParameterSet>'
        f"{parameters_xml}"
        "</HostParameterSet></Connector>"
        "</DeviceType></Device></data></addData>"
        "</configuration></configurations></instances>\n"
        "</project>\n"
    )


def _param(pid, tipo, nome, valor_xml, index="0"):
    return (f'<Parameter ParameterId="{pid}" type="{tipo}" '
            f'IndexInDevDesc="{index}">'
            f"<Attributes />{valor_xml}<Name>{nome}</Name></Parameter>")


def _write(tmp_path, nome, conteudo):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return str(caminho)


def _files(paths_por_dispositivo, source):
    return [{"device_name": nome, "node_id": node_id, "path": caminho,
             "source": source}
            for nome, node_id, caminho in paths_por_dispositivo]


SRC_A = di.RunSource(run_dir="/run/a", state="state_a", project_sha256="a" * 64)
SRC_B = di.RunSource(run_dir="/run/b", state="state_b", project_sha256="b" * 64)


# --- forma do valor ---------------------------------------------------------

@pytest.mark.parametrize("valor,estado,esperado", [
    ("[16#C0,16#A8,16#01,16#02]", di.VALUE_PRESENT, "ip4"),
    ("[1, 2, 3, 4]", di.VALUE_PRESENT, "ip4"),
    ("502", di.VALUE_PRESENT, "scalar"),
    ("'texto'", di.VALUE_PRESENT, "scalar"),
    ("TRUE", di.VALUE_PRESENT, "scalar"),
    ("16#00000815", di.VALUE_PRESENT, "scalar"),
    ("a + b", di.VALUE_PRESENT, "other"),
    ("qualquer", di.VALUE_STRUCTURED, "non_scalar"),
    (None, di.VALUE_ABSENT, "non_scalar"),
])
def test_value_shape(valor, estado, esperado):
    assert di.value_shape(valor, estado) == esperado


# --- estados de valor: presente x estruturado x vazio x ausente -------------

def test_quatro_estados_de_valor_sao_distintos(tmp_path):
    xml = _export("Dev", "101", [], "".join([
        _param(1, "std:WORD", "Escalar", "<Value>7</Value>"),
        _param(2, "std:WORD", "Zero", "<Value>0</Value>"),
        _param(3, "std:WORD", "Vazio", "<Value></Value>"),
        _param(4, "local:Struct", "Estruturado",
               "<Value><Element name='a'>1</Element></Value>"),
        _param(5, "std:WORD", "SemValue", ""),
    ]))
    caminho = _write(tmp_path, "dev", xml)
    resultado = di.parse_device_export(caminho)
    estados = {p["name"]: p["value_state"] for p in resultado["parameters"]}
    assert estados == {
        "Escalar": di.VALUE_PRESENT,
        "Zero": di.VALUE_PRESENT,
        "Vazio": di.VALUE_EMPTY,
        "Estruturado": di.VALUE_STRUCTURED,
        "SemValue": di.VALUE_ABSENT,
    }


def test_zero_e_valor_presente_e_nao_se_confunde_com_vazio(tmp_path):
    """`0` é configuração legítima. Tratá-lo como vazio apagaria dado real."""
    xml = _export("Dev", "101", [], _param(2, "std:WORD", "Zero", "<Value>0</Value>"))
    inventario = di.build_inventory(
        [SRC_A], _files([("Dev", "root/0", _write(tmp_path, "d", xml))], SRC_A))
    assert inventario["validations"]["value_text_zero"] == 1
    assert inventario["validations"]["value_states"][di.VALUE_PRESENT] == 1
    assert di.VALUE_EMPTY not in inventario["validations"]["value_states"]


# --- contexto de protocolo vem da estrutura --------------------------------

def test_contexto_vem_da_estrutura_nao_do_nome():
    assert di.CTX_ETHERNET_IP in di.protocol_context("101", [], [])
    assert di.CTX_MODBUS in di.protocol_context(None, ["Common.ModbusTCP"], [])
    assert di.CTX_MODBUS in di.protocol_context(None, [], ["localTypes:TYPE_MODBUS_X"])
    assert di.protocol_context(None, [], []) == [di.CTX_LOCAL]


# --- hierarquia de evidência ------------------------------------------------

def test_token_de_tipo_vale_high():
    hits, motivo = di.interpret_parameter(
        {"type": "localTypes:TYPE_MODBUS_SLAVE_ADDRESS", "name": "Qualquer",
         "parameter_id": "999", "value": "3", "value_state": di.VALUE_PRESENT},
        [di.CTX_MODBUS])
    assert motivo is None
    assert hits[0]["concept"] == "unit_id"
    assert hits[0]["confidence"] == di.CONFIDENCE_HIGH


def test_parameter_id_exige_nome_esperado():
    """O falso positivo real: id 0 existe em toda device description."""
    base = {"type": "local:FLAGS", "parameter_id": "0", "value": "x",
            "value_state": di.VALUE_PRESENT}
    hits, motivo = di.interpret_parameter(
        dict(base, name="Supported Functions"), [di.CTX_ETHERNET])
    assert hits == []
    assert "ParameterId isolado nao e evidencia" in motivo

    hits, motivo = di.interpret_parameter(
        dict(base, name="IPAddress"), [di.CTX_ETHERNET])
    assert motivo is None
    assert hits[0]["concept"] == "ip_address"
    assert hits[0]["confidence"] == di.CONFIDENCE_HIGH


def test_nome_estrutural_exige_forma_do_valor():
    base = {"type": "std:ARRAY[0..3] OF BYTE", "name": "SubnetMask",
            "parameter_id": "777"}
    hits, _ = di.interpret_parameter(
        dict(base, value="[255, 255, 255, 0]", value_state=di.VALUE_PRESENT),
        [di.CTX_ETHERNET])
    assert hits[0]["concept"] == "subnet_mask"
    assert hits[0]["confidence"] == di.CONFIDENCE_MEDIUM

    hits, motivo = di.interpret_parameter(
        dict(base, value="0", value_state=di.VALUE_PRESENT), [di.CTX_ETHERNET])
    assert hits == []
    assert "forma do valor" in motivo


def test_nome_estrutural_exige_contexto_compativel():
    hits, motivo = di.interpret_parameter(
        {"type": "std:WORD", "name": "Porta TCP", "parameter_id": "5",
         "value": "502", "value_state": di.VALUE_PRESENT},
        [di.CTX_LOCAL])
    assert hits == []
    assert "contexto estrutural" in motivo


def test_nome_isolado_nunca_interpreta():
    """Nenhuma regra classifica só porque uma palavra genérica apareceu."""
    for nome in ("Input Size", "Output Mask", "Port Function", "Address"):
        hits, motivo = di.interpret_parameter(
            {"type": "std:DWORD", "name": nome, "parameter_id": "4242",
             "value": "1", "value_state": di.VALUE_PRESENT}, [di.CTX_LOCAL])
        assert hits == [], nome
        assert motivo


def test_nao_existe_confianca_low():
    """`low` foi eliminado: nome isolado virou candidato, não fato."""
    niveis = {di.CONFIDENCE_HIGH, di.CONFIDENCE_MEDIUM}
    assert "low" not in niveis


# --- composição de runs e proveniência --------------------------------------

def test_run_unica_e_snapshot_single(tmp_path):
    xml = _export("Dev", "101", [], _param(1, "std:WORD", "N", "<Value>1</Value>"))
    inventario = di.build_inventory(
        [SRC_A], _files([("Dev", "root/0", _write(tmp_path, "d", xml))], SRC_A))
    assert inventario["inventory_snapshot_kind"] == di.SNAPSHOT_SINGLE


def test_runs_de_estados_diferentes_viram_composite(tmp_path):
    """O ponto central: dois hashes de projeto não podem virar snapshot único."""
    xml = _export("Dev", "101", [], _param(1, "std:WORD", "N", "<Value>1</Value>"))
    a = _write(tmp_path, "a", xml)
    b = _write(tmp_path, "b", xml)
    arquivos = (_files([("DevA", "root/0", a)], SRC_A) +
                _files([("DevB", "root/1", b)], SRC_B))
    inventario = di.build_inventory([SRC_A, SRC_B], arquivos)
    assert inventario["inventory_snapshot_kind"] == di.SNAPSHOT_COMPOSITE
    assert inventario["coverage"]["devices_by_state"] == {
        "state_a": ["DevA"], "state_b": ["DevB"]}


def test_cada_registro_carrega_a_proveniencia_da_sua_run(tmp_path):
    xml = _export("Dev", "101", [], _param(1, "std:WORD", "N", "<Value>1</Value>"))
    arquivos = (_files([("DevA", "root/0", _write(tmp_path, "a", xml))], SRC_A) +
                _files([("DevB", "root/1", _write(tmp_path, "b", xml))], SRC_B))
    inventario = di.build_inventory([SRC_A, SRC_B], arquivos)
    por_dispositivo = {r["device_name"]: r for r in inventario["raw"]}
    assert por_dispositivo["DevA"]["project_sha256"] == "a" * 64
    assert por_dispositivo["DevB"]["project_sha256"] == "b" * 64
    assert por_dispositivo["DevA"]["project_state"] == "state_a"
    assert all(r["source_sha256"] for r in inventario["raw"])


# --- nada é descartado ------------------------------------------------------

def test_duplicatas_e_conflitos_sao_registrados_nao_removidos(tmp_path):
    xml = _export("Dev", "101", [], "".join([
        _param(1, "std:WORD", "Repetido", "<Value>10</Value>"),
        _param(1, "std:WORD", "Repetido", "<Value>20</Value>"),
        _param(2, "std:WORD", "Igual", "<Value>5</Value>"),
        _param(2, "std:WORD", "Igual", "<Value>5</Value>"),
    ]))
    inventario = di.build_inventory(
        [SRC_A], _files([("Dev", "root/0", _write(tmp_path, "d", xml))], SRC_A))
    assert inventario["validations"]["parameters_total"] == 4
    assert inventario["validations"]["duplicate_parameter_ids"]
    assert inventario["validations"]["exact_duplicates"] == 1
    assert inventario["validations"]["conflicting_values"]


def test_parametro_sem_regra_vai_para_unresolved_e_nao_some(tmp_path):
    xml = _export("Dev", None, [], "".join([
        _param(1, "std:BOOL", "Desconhecido", "<Value>TRUE</Value>"),
        _param(2, "localTypes:TYPE_MODBUS_TIMEOUT", "T", "<Value>3000</Value>"),
    ]))
    inventario = di.build_inventory(
        [SRC_A], _files([("Dev", "root/0", _write(tmp_path, "d", xml))], SRC_A))
    assert inventario["validations"]["parameters_total"] == 2
    assert len(inventario["interpreted"]) == 1
    assert len(inventario["unresolved"]) == 1
    assert inventario["unresolved"][0]["motivo"]


def test_toda_interpretacao_tem_regra_evidencia_e_confianca(tmp_path):
    xml = _export("Dev", "101", ["Common.EthernetIPScanner"], "".join([
        _param(2000, "std:DWORD", "Vendor Code", "<Value>853</Value>"),
        _param(2002, "std:DWORD", "Product Code", "<Value>3072</Value>"),
    ]))
    inventario = di.build_inventory(
        [SRC_A], _files([("Dev", "root/0", _write(tmp_path, "d", xml))], SRC_A))
    assert inventario["interpreted"]
    for item in inventario["interpreted"]:
        assert item["rule"] and item["evidence"] and item["confidence"]
        assert item["source_file"] and item["source_sha256"]
    assert inventario["validations"]["interpretations_missing_provenance"] == 0


# --- cobertura --------------------------------------------------------------

def test_dispositivo_sem_parametro_conta_na_cobertura_estrutural(tmp_path):
    """Barramento/slot sem parâmetro não é falha de cobertura."""
    com = _export("Com", "101", [], _param(1, "std:WORD", "N", "<Value>1</Value>"))
    sem = _export("Sem", None, [], "")
    arquivos = _files([("Com", "root/0", _write(tmp_path, "c", com)),
                       ("Sem", "root/1", _write(tmp_path, "s", sem))], SRC_A)
    inventario = di.build_inventory([SRC_A], arquivos)
    assert inventario["coverage"]["devices_observed"] == 2
    assert inventario["coverage"]["devices_with_parameters"] == 1


# --- determinismo -----------------------------------------------------------

def test_duas_construcoes_produzem_o_mesmo_json(tmp_path):
    xml = _export("Dev", "101", ["Common.EthernetIPScanner"], "".join([
        _param(2000, "std:DWORD", "Vendor Code", "<Value>853</Value>"),
        _param(256, "std:ARRAY[0..3] OF BYTE", "IPAddress",
               "<Value>[16#C0,16#A8,16#01,16#02]</Value>"),
        _param(1, "std:BOOL", "Outro", "<Value>TRUE</Value>"),
    ]))
    arquivos = _files([("Dev", "root/0", _write(tmp_path, "d", xml))], SRC_A)
    primeiro = json.dumps(di.build_inventory([SRC_A], arquivos), sort_keys=True)
    segundo = json.dumps(di.build_inventory([SRC_A], arquivos), sort_keys=True)
    assert primeiro == segundo
