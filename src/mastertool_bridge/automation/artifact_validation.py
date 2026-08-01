"""Validação (host, offline) do que o runner interno produziu em `output/`
(contrato `docs/16-supervised-runner-contract.md`, seções 4/6/7).

Funções puras sobre caminhos de disco — nenhuma delas toca o MasterTool, e
todas são testáveis com `tmp_path` (nenhum `datetime.now()` na lógica de
avaliação, mesma filosofia de `cli_probe_verify.py`).

DECISÃO DE DESIGN (ambiguidade do contrato — reportada, não "corrigida" por
conta própria): a seção 1 do contrato define `output/` como diretório
único com "todos os artefatos de aquisição", mas NÃO nomeia os arquivos que
`scan_project_tree`/`export_text`/`inventory_graphic_objects` gravam nele
(esses nomes são detalhe de implementação do runner interno, desenvolvido
em paralelo por outro agente). Os dois artefatos cujo nome o contrato
efetivamente fixa são `run-report.json` (seção 7, a declaração final) e
`checksums.sha256` (seção 6.1, sempre gerado pela sequência de gravação de
artefatos). Este módulo por isso valida esses dois por nome fixo, e aceita
uma lista adicional opcional de nomes esperados (`extra_required_filenames`)
para quando o chamador souber, por config concreto, quais artefatos por
operação devem existir — sem inventar nomes que o contrato não fixa.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mastertool_bridge.automation.result_models import ArtifactValidationResult

RUN_REPORT_FILENAME = "run-report.json"
CHECKSUMS_FILENAME = "checksums.sha256"

# As 6 chaves EXATAS da declaração final (seção 7 do contrato). Todas devem
# estar presentes e valer `False` — qualquer uma ausente ou `True` reprova.
FINAL_DECLARATION_KEYS = (
    "project_saved",
    "build_called",
    "online_operation",
    "download_called",
    "force_called",
    "original_project_touched",
)

DEFAULT_REQUIRED_FILENAMES = (RUN_REPORT_FILENAME, CHECKSUMS_FILENAME)

# Fase L1 (`docs/16-supervised-runner-contract.md`, seção 3.1) — quando
# `operations.probe_ladder_surface` está ligada, o runner interno grava este
# subdiretório dentro de `output/` com os artefatos da sondagem de
# superfície de API sobre um único objeto POU.
LADDER_PROBE_DIRNAME = "ladder-surface-probe"

# Fase L1, probe 17 — sondagem da superfície DINÂMICA. Diretório separado do
# probe 16 de propósito: são duas sondagens independentes (reflexão CLR vs
# `dir()`/`hasattr()` do IronPython), podem ser ligadas isoladamente, e
# misturar os artefatos impediria comparar os dois métodos — que é
# exatamente o ponto da fase.
LADDER_DYNAMIC_PROBE_DIRNAME = "ladder-dynamic-surface"

# Fase L1, probe 18 — canal `Extender`/providers/descriptors. Terceiro
# diretório próprio pelo mesmo motivo dos anteriores: são canais distintos e
# misturar os artefatos impediria comparar os métodos.
LADDER_EXTENDER_PROBE_DIRNAME = "ladder-extender-probe"

# Fase L1, probe 19 — assinatura de `export_xml`, SEM invocação.
PLCOPEN_SIGNATURE_PROBE_DIRNAME = "plcopen-signature-probe"

# Fase L1, exportação controlada — PRIMEIRA operação que escreve.
PLCOPEN_EXPORT_DIRNAME = "plcopen-export"
PLCOPEN_EXPORT_ROOT_DIRNAME = "export-root"

PLCOPEN_EXPORT_REQUIRED_FILENAMES = (
    "invocation.json",
    "filesystem-before.json",
    "filesystem-after.json",
    "created-artifacts.json",
    "diagnostics.json",
    "safety-declaration.json",
    "checksums.sha256",
    "report.md",
    # Registra QUEM criou o export-root e em que ponto do ciclo de vida —
    # o artefato arquivado não pode depender de memória.
    "export-root-preparation.json",
    # docs/19-contratos-de-execucao.md, seção 4 — a exportação passou a
    # arquivar a identidade do alvo em artefato próprio e checksummado,
    # igual às quatro operações read-only.
    "target-identity.json",
)

# Artefatos que passaram a ser obrigatórios DEPOIS que algumas runs já
# tinham sido arquivadas. Ausência em uma run NOVA continua sendo erro (o
# nome permanece em `PLCOPEN_EXPORT_REQUIRED_FILENAMES`, acima) — mas a
# ausência numa REVISÃO de run arquivada (`host_validation_revision.py`) é
# só aviso: a run é legitimamente anterior à mudança que introduziu o
# artefato, e não pode ser corrigida retroativamente sem refazer a
# aquisição (proibido — ver docstring de `host_validation_revision.py`).
PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER = (
    "target-identity.json",
)

# A declaração da exportação tem schema PRÓPRIO: aqui a escrita é esperada,
# então reusar `LADDER_PROBE_SAFETY_DECLARATION_KEYS` (que exige tudo False)
# reprovaria uma execução correta. Honestidade tem forma diferente conforme
# o que a operação faz.
PLCOPEN_EXPORT_SAFETY_TRUE_KEYS = ("export_xml_called", "filesystem_output_written")
PLCOPEN_EXPORT_SAFETY_FALSE_KEYS = (
    "project_save_called", "project_build_called", "text_document_write_called",
    "import_called", "online_operation", "download_called", "force_called",
)

PLCOPEN_SIGNATURE_PROBE_REQUIRED_FILENAMES = (
    "manifest.json",
    "target-identity.json",
    "export-xml-overloads.json",
    # Escopo Application em arquivo próprio: a matriz de decisão da primeira
    # exportação depende de saber, por escopo, se há sobrecarga invocável.
    "active-application-overloads.json",
    "import-xml-overloads.json",
    "export-scope.json",
    "export-reporter-type.json",
    "conflict-resolve-enum.json",
    "diagnostics.json",
    "safety-declaration.json",
    "checksums.sha256",
    "report.md",
)

LADDER_EXTENDER_PROBE_REQUIRED_FILENAMES = (
    "manifest.json",
    "target-identity.json",
    "extender-member.json",
    "extender-runtime-type.json",
    "extender-interfaces.json",
    "extender-properties.json",
    "extender-methods.json",
    "extension-items.json",
    "extension-item-types.json",
    # Decide se o canal foi validado: sem ele não há veredito verificável.
    "known-control-discovery.json",
    "ladder-candidate-members.json",
    "diagnostics.json",
    "safety-declaration.json",
    "checksums.sha256",
    "report.md",
)

LADDER_DYNAMIC_PROBE_REQUIRED_FILENAMES = (
    "manifest.json",
    "target-identity.json",
    "clr-members.json",
    "dynamic-dir-members.json",
    "dynamic-only-members.json",
    "shared-members.json",
    "whitelist-hasattr-results.json",
    "safe-getter-results.json",
    "ladder-candidate-members.json",
    # O artefato que decide se a fase avança: sem ele não há como saber se a
    # superfície dinâmica foi validada pelo controle `textual_declaration`.
    "control-validation.json",
    "diagnostics.json",
    "safety-declaration.json",
    "checksums.sha256",
    "report.md",
)

LADDER_PROBE_REQUIRED_FILENAMES = (
    "manifest.json",
    "target-identity.json",
    "runtime-types.json",
    "interfaces.json",
    "properties.json",
    "methods.json",
    "safe-getter-results.json",
    "candidate-representation-members.json",
    "diagnostics.json",
    "safety-declaration.json",
    "checksums.sha256",
    "report.md",
)

LADDER_PROBE_SAFETY_DECLARATION_FILENAME = "safety-declaration.json"

# As 10 chaves EXATAS da declaração de segurança da sondagem Ladder
# (contrato, seção 3.1). Todas devem estar presentes e valer `False` —
# qualquer uma ausente ou `True` reprova. Não confundir com
# `FINAL_DECLARATION_KEYS` (as 6 chaves de `run-report.json`, seção 7): são
# duas declarações diferentes, de escopos diferentes.
LADDER_PROBE_SAFETY_DECLARATION_KEYS = (
    "text_document_read",
    "text_document_write",
    "export_called",
    "import_called",
    "save_called",
    "build_called",
    "online_operation",
    "download_called",
    "force_called",
    "project_modified",
)


def check_plcopen_export_safety_declaration(export_dir: Path) -> list[str]:
    """A declaração da exportação é a única do projeto em que campos `True`
    são esperados. Verifica os dois lados: o que DEVE ser verdadeiro (houve
    chamada e houve escrita) e o que NÃO pode ser (save/build/import/online/
    download/force). Uma declaração toda `False` aqui seria tão errada quanto
    uma declaração `True` nos probes read-only."""
    path = Path(export_dir) / "safety-declaration.json"
    if not path.is_file():
        return [f"safety-declaration.json ausente em {export_dir.name}/"]
    try:
        declaration = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"safety-declaration.json inválida: {exc}"]

    problems: list[str] = []
    if "write_called" in declaration:
        problems.append(
            "safety-declaration usa `write_called` genérico — proibido nesta "
            "operação: um XML É escrito, e a chave sugeriria o contrário.")
    for key in PLCOPEN_EXPORT_SAFETY_FALSE_KEYS:
        if declaration.get(key) is not False:
            problems.append(
                f"safety-declaration.{key} deveria ser False (recebido: "
                f"{declaration.get(key)!r})")
    if declaration.get("export_xml_call_count") not in (0, 1):
        problems.append(
            "safety-declaration.export_xml_call_count deve ser 0 ou 1 (uma "
            f"execução, uma invocação) — recebido: "
            f"{declaration.get('export_xml_call_count')!r}")
    scope = declaration.get("filesystem_output_scope")
    if declaration.get("filesystem_output_written") is True and scope != (
            "authorized_disposable_export_root"):
        problems.append(
            f"escrita declarada fora do escopo autorizado: {scope!r}")
    return problems


def check_no_output_escaped_export_root(export_dir: Path) -> list[str]:
    """`created-artifacts.json` só pode listar caminhos RELATIVOS que
    permaneçam dentro de `export-root`. Um caminho absoluto ou com `..` seria
    saída escapada — a falha operacional `output_escaped_export_root`."""
    path = Path(export_dir) / "created-artifacts.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"created-artifacts.json inválida: {exc}"]

    entries = payload.get("entries", payload) if isinstance(payload, dict) else payload
    problems: list[str] = []
    for entry in entries or []:
        rel = (entry or {}).get("relative_path") or ""
        normalized = rel.replace("\\", "/")
        if (normalized.startswith("/") or ".." in normalized.split("/")
                or (len(rel) > 1 and rel[1] == ":")):
            problems.append(
                f"output_escaped_export_root: entrada fora do diretório "
                f"autorizado: {rel!r}")
    return problems


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checksums(output_dir: Path) -> tuple[bool, list[str]]:
    """Confere `output_dir/checksums.sha256` (formato `hash  caminho/rel`,
    uma entrada por linha, gerado por `common/checksums.write_checksums_file`
    no lado interno) contra os arquivos realmente presentes em disco.

    Reprova (retorna `ok=False`) se: o arquivo não existir, alguma linha
    tiver formato inválido, algum arquivo referenciado estiver ausente, ou
    algum hash não bater."""
    output_dir = Path(output_dir)
    checksums_path = output_dir / CHECKSUMS_FILENAME
    errors: list[str] = []

    if not checksums_path.is_file():
        return False, [f"checksums.sha256 ausente: {checksums_path}"]

    try:
        lines = checksums_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return False, [f"checksums.sha256 ilegível: {exc}"]

    checked_any = False
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        # Formato "hash  caminho/relativo" (duas ou mais espaços entre
        # hash e caminho — mesmo formato produzido por
        # common/checksums.write_checksums_file).
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(f"linha malformada em checksums.sha256: {line!r}")
            continue
        digest_expected, rel_path = parts
        if digest_expected.upper() == "ERRO":
            # O gerador interno também usa este arquivo para registrar
            # falha ao calcular hash de um arquivo específico — reprova.
            errors.append(f"checksums.sha256 registra erro de geração: {line!r}")
            continue
        target = output_dir / rel_path
        checked_any = True
        if not target.is_file():
            errors.append(f"arquivo listado em checksums.sha256 ausente: {rel_path}")
            continue
        digest_actual = _sha256_file(target)
        if digest_actual.lower() != digest_expected.lower():
            errors.append(
                f"checksum não fecha para {rel_path}: "
                f"esperado={digest_expected} obtido={digest_actual}")

    if not checked_any and not errors:
        errors.append("checksums.sha256 vazio — nada para conferir")

    return (len(errors) == 0), errors


def check_errors_json_empty(output_dir: Path) -> tuple[bool, list[str]]:
    """Procura, recursivamente, qualquer `errors.json` sob `output_dir`
    (padrão usado pelos módulos `common/` reaproveitados — scanner,
    exportador textual, inventário gráfico) e reprova se algum deles não
    for uma lista JSON vazia. Ausência de `errors.json` não reprova (o
    contrato não garante que ele sempre exista)."""
    output_dir = Path(output_dir)
    problems: list[str] = []
    if not output_dir.is_dir():
        return True, []

    for path in sorted(output_dir.rglob("errors.json")):
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"errors.json ilegível ({path}): {exc}")
            continue
        if not isinstance(content, list):
            problems.append(f"errors.json não é uma lista JSON ({path})")
        elif content:
            problems.append(f"errors.json não está vazio ({path}): {len(content)} erro(s)")

    return (len(problems) == 0), problems


def check_final_declaration(output_dir: Path) -> tuple[dict | None, list[str]]:
    """Lê `output/run-report.json` (seção 7 do contrato) e confere que as 6
    chaves estão presentes e valem `False`. Fail-closed: chave ausente,
    chave extra desconhecida como `True`, ou arquivo ilegível reprovam."""
    output_dir = Path(output_dir)
    report_path = output_dir / RUN_REPORT_FILENAME
    if not report_path.is_file():
        return None, [f"run-report.json ausente: {report_path}"]

    try:
        declaration = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"run-report.json ilegível: {exc}"]

    if not isinstance(declaration, dict):
        return None, ["run-report.json não é um objeto JSON"]

    errors: list[str] = []
    for key in FINAL_DECLARATION_KEYS:
        if key not in declaration:
            errors.append(f"run-report.json sem a chave obrigatória: {key}")
        elif declaration[key] is not False:
            errors.append(
                f"run-report.json declara {key}={declaration[key]!r} (esperado: False)")

    return declaration, errors


def check_ladder_probe_safety_declaration(ladder_probe_dir: Path) -> tuple[dict | None, list[str]]:
    """Lê `<ladder_probe_dir>/safety-declaration.json` (contrato, seção 3.1)
    e confere que as 10 chaves estão presentes e valem `False`. Fail-closed:
    chave ausente, chave `True`, ou arquivo ilegível/ausente reprovam —
    mesmo critério de `check_final_declaration`, aplicado a uma declaração
    diferente (a da sondagem Ladder, não a de `run-report.json`)."""
    ladder_probe_dir = Path(ladder_probe_dir)
    declaration_path = ladder_probe_dir / LADDER_PROBE_SAFETY_DECLARATION_FILENAME
    if not declaration_path.is_file():
        return None, [f"safety-declaration.json ausente: {declaration_path}"]

    try:
        declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"safety-declaration.json ilegível: {exc}"]

    if not isinstance(declaration, dict):
        return None, ["safety-declaration.json não é um objeto JSON"]

    errors: list[str] = []
    for key in LADDER_PROBE_SAFETY_DECLARATION_KEYS:
        if key not in declaration:
            errors.append(f"safety-declaration.json sem a chave obrigatória: {key}")
        elif declaration[key] is not False:
            errors.append(
                f"safety-declaration.json declara {key}={declaration[key]!r} "
                "(esperado: False)")

    return declaration, errors


def validate_output_artifacts(
    output_dir: Path,
    operations: dict | None = None,
    extra_required_filenames: tuple[str, ...] = (),
    *,
    archived_revision: bool = False,
) -> ArtifactValidationResult:
    """Orquestra as checagens desta módulo em um único
    `ArtifactValidationResult`. `operations` é aceito para uso futuro por
    chamadores que conheçam nomes de artefato por operação (ver docstring
    do módulo); hoje só é usado para registrar nas observações quais
    operações estavam habilitadas.

    `archived_revision`: `True` quando o chamador é
    `host_validation_revision.revise_run()` — revisão host-side de uma run
    JÁ arquivada, nunca uma execução nova. Nesse modo, a ausência de um
    artefato listado em `PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER` (hoje só
    `target-identity.json`) não vira erro: vira aviso, porque a run pode ser
    legitimamente anterior à mudança que passou a exigi-lo, e não pode ser
    corrigida retroativamente sem refazer a aquisição (proibido). Para uma
    run NOVA (`archived_revision=False`, o padrão — usado por
    `supervised_run.py`), a ausência continua erro, sem exceção."""
    output_dir = Path(output_dir)
    errors: list[str] = []
    warnings: list[str] = []
    checked_files: list[str] = []

    if not output_dir.is_dir():
        return ArtifactValidationResult(
            ok=False, errors=[f"output_dir inexistente: {output_dir}"],
            warnings=[], checked_files=[], final_declaration=None)

    required = tuple(DEFAULT_REQUIRED_FILENAMES) + tuple(extra_required_filenames)
    for filename in required:
        candidate = output_dir / filename
        if candidate.is_file():
            checked_files.append(filename)
        else:
            errors.append(f"artefato esperado ausente em output/: {filename}")

    checksums_ok, checksum_errors = verify_checksums(output_dir)
    if not checksums_ok:
        errors.extend(checksum_errors)

    errors_json_ok, errors_json_problems = check_errors_json_empty(output_dir)
    if not errors_json_ok:
        errors.extend(errors_json_problems)

    declaration, declaration_errors = check_final_declaration(output_dir)
    if declaration_errors:
        errors.extend(declaration_errors)

    # Fase L1 (contrato, seção 3.1): quando `probe_ladder_surface` estiver
    # ligada, output/ladder-surface-probe/ com seus 12 artefatos e a
    # declaração de segurança de 10 chaves (todas False) também são
    # obrigatórios. `operations` é o dict cru da seção `operations` do
    # `run-config.json` (mesma forma de `RunOperations.to_dict()`).
    if operations and operations.get("probe_ladder_surface"):
        ladder_dir = output_dir / LADDER_PROBE_DIRNAME
        for filename in LADDER_PROBE_REQUIRED_FILENAMES:
            candidate = ladder_dir / filename
            rel = f"{LADDER_PROBE_DIRNAME}/{filename}"
            if candidate.is_file():
                checked_files.append(rel)
            else:
                errors.append(
                    f"artefato esperado ausente em output/{LADDER_PROBE_DIRNAME}/: {filename}")

        _ladder_safety_declaration, ladder_safety_errors = (
            check_ladder_probe_safety_declaration(ladder_dir))
        if ladder_safety_errors:
            errors.extend(ladder_safety_errors)

    # Fase L1, probe 17: mesma exigência, diretório próprio. A declaração de
    # segurança é conferida pela MESMA função — o probe 17 grava as mesmas 10
    # chaves, e uma segunda verificação paralela poderia divergir em silêncio.
    if operations and operations.get("probe_ladder_dynamic_surface"):
        dynamic_dir = output_dir / LADDER_DYNAMIC_PROBE_DIRNAME
        for filename in LADDER_DYNAMIC_PROBE_REQUIRED_FILENAMES:
            candidate = dynamic_dir / filename
            rel = f"{LADDER_DYNAMIC_PROBE_DIRNAME}/{filename}"
            if candidate.is_file():
                checked_files.append(rel)
            else:
                errors.append(
                    "artefato esperado ausente em "
                    f"output/{LADDER_DYNAMIC_PROBE_DIRNAME}/: {filename}")

        _dynamic_safety_declaration, dynamic_safety_errors = (
            check_ladder_probe_safety_declaration(dynamic_dir))
        if dynamic_safety_errors:
            errors.extend(dynamic_safety_errors)

    # Fase L1, probe 18: mesma exigência, diretório próprio, MESMA função de
    # verificação da declaração de segurança (as 10 chaves são idênticas —
    # uma segunda verificação paralela poderia divergir em silêncio).
    if operations and operations.get("probe_ladder_extender_surface"):
        extender_dir = output_dir / LADDER_EXTENDER_PROBE_DIRNAME
        for filename in LADDER_EXTENDER_PROBE_REQUIRED_FILENAMES:
            candidate = extender_dir / filename
            rel = f"{LADDER_EXTENDER_PROBE_DIRNAME}/{filename}"
            if candidate.is_file():
                checked_files.append(rel)
            else:
                errors.append(
                    "artefato esperado ausente em "
                    f"output/{LADDER_EXTENDER_PROBE_DIRNAME}/: {filename}")

        _extender_safety_declaration, extender_safety_errors = (
            check_ladder_probe_safety_declaration(extender_dir))
        if extender_safety_errors:
            errors.extend(extender_safety_errors)

    # Fase L1, probe 19: mesma exigência, diretório próprio. A declaração de
    # segurança continua com as 10 chaves TODAS False — esta fatia não
    # escreve XML; a mudança de perfil vem na fatia de exportação.
    if operations and operations.get("probe_plcopen_export_signature"):
        signature_dir = output_dir / PLCOPEN_SIGNATURE_PROBE_DIRNAME
        for filename in PLCOPEN_SIGNATURE_PROBE_REQUIRED_FILENAMES:
            candidate = signature_dir / filename
            rel = f"{PLCOPEN_SIGNATURE_PROBE_DIRNAME}/{filename}"
            if candidate.is_file():
                checked_files.append(rel)
            else:
                errors.append(
                    "artefato esperado ausente em "
                    f"output/{PLCOPEN_SIGNATURE_PROBE_DIRNAME}/: {filename}")

        _signature_safety, signature_safety_errors = (
            check_ladder_probe_safety_declaration(signature_dir))
        if signature_safety_errors:
            errors.extend(signature_safety_errors)

    if operations and operations.get("export_plcopen_xml"):
        export_dir = output_dir / PLCOPEN_EXPORT_DIRNAME
        for filename in PLCOPEN_EXPORT_REQUIRED_FILENAMES:
            candidate = export_dir / filename
            rel = f"{PLCOPEN_EXPORT_DIRNAME}/{filename}"
            if candidate.is_file():
                checked_files.append(rel)
            elif archived_revision and filename in PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER:
                # Run arquivada ANTES de o artefato passar a ser exigido. Não
                # pode ser corrigida retroativamente sem refazer a aquisição, e
                # refazer é proibido — então vira aviso nomeado, nunca erro.
                # Numa run NOVA este mesmo nome continua caindo no `else`.
                warnings.append(
                    f"artefato ausente em output/{PLCOPEN_EXPORT_DIRNAME}/: {filename} — "
                    "introduzido depois desta run ser arquivada; ausência esperada em "
                    "revisão histórica, não reprova.")
            else:
                errors.append(
                    f"artefato esperado ausente em output/{PLCOPEN_EXPORT_DIRNAME}/: {filename}")

        errors.extend(check_plcopen_export_safety_declaration(export_dir))
        errors.extend(check_no_output_escaped_export_root(export_dir))

    ok = len(errors) == 0
    return ArtifactValidationResult(
        ok=ok, errors=errors, warnings=warnings,
        checked_files=checked_files, final_declaration=declaration)
