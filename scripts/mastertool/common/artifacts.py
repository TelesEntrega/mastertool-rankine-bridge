# -*- coding: utf-8 -*-
"""Mecanismo comum de escrita de artefatos das operacoes supervisionadas.

Extrai a duplicacao COMPROVADA entre os probes 16-19: os quatro ultimos
arquivos de `_write_artifacts` eram identicos linha a linha nos quatro, e o
probe 20 repetia a mesma sequencia com uma regra propria de checksums.

    diagnostics.json
    safety-declaration.json
    report.md
    checksums.sha256   <- SEMPRE por ultimo, cobre os anteriores

Este modulo unifica COMO os arquivos sao produzidos, nunca o que eles
SIGNIFICAM. Nao existe schema generico de safety declaration aqui: cada
operacao passa a sua ja montada, e as duas classes continuam separadas --
read-only exige toda operacao de escrita `False`, a exportacao controlada
exige que a escrita autorizada e a chamada unica de `export_xml` sejam
registradas como `True`. Um schema que aceitasse as duas formas aceitaria uma
exportacao silenciosa e um probe que escreveu.

O que continua fora daqui, sob responsabilidade de cada operacao:
`manifest.json`, `invocation.json`, `target-identity.json`,
`control-validation.json`, `created-artifacts.json`, `extension-items.json` e
todo o resto especifico do canal investigado.

Compatibilidade: IronPython 2.7 (roda DENTRO do MasterTool). Sem f-strings,
sem type hints, sem `pathlib`, sem dataclasses.
"""

from __future__ import print_function

import os

from common import checksums, file_io

# Os quatro artefatos comuns, na ordem de escrita. `checksums.sha256` fecha a
# lista porque precisa cobrir os anteriores.
COMMON_ARTIFACT_FILENAMES = (
    "diagnostics.json",
    "safety-declaration.json",
    "report.md",
    "checksums.sha256",
)

CHECKSUMS_FILENAME = "checksums.sha256"

TEMP_SUFFIX = ".tmp"


class ArtifactWriteError(Exception):
    """Falha ao gravar um artefato, com o caminho e a causa preservados.

    Erro estruturado em vez de excecao crua: quem chama precisa saber QUAL
    arquivo falhou para registrar diagnostico, e a causa original nao pode se
    perder no caminho."""

    def __init__(self, path, cause):
        self.path = path
        self.cause = cause
        Exception.__init__(
            self, "falha ao gravar %s: %s: %s"
            % (path, type(cause).__name__, cause))


def _replace_via_temp(path, write_body):
    """Grava via arquivo temporario e so entao substitui o destino.

    Mesmo procedimento ja documentado em `docs/16-supervised-runner-contract.md`
    para `status.json`, e pela mesma razao: IronPython 2.7 NAO tem
    `os.replace` (Python 3.3+) e no Windows `os.rename` levanta excecao se o
    destino existir.

    A sequencia e: escrever `.tmp` -> remover o destino anterior -> renomear o
    `.tmp`. Entre remover e renomear existe uma janela em que o destino NAO
    existe; um processo interrompido ali deixa o arquivo ausente. O nome destas
    funcoes diz `via_temp` justamente por isso -- prometer substituicao
    indivisivel seria descrever um comportamento que este procedimento nao tem.

    A garantia real e mais estreita, e ainda assim util: o destino nunca fica
    com conteudo pela METADE. Ou tem o conteudo anterior, ou tem o novo
    completo. Para o caso da janela, a defesa e outra -- o
    `status-history.jsonl` append-only, gravado ANTES de cada troca.

    Em qualquer falha o temporario e removido, para nao deixar `.tmp` orfao no
    diretorio de artefatos -- que seria coletado pelo `checksums.sha256` da
    proxima escrita e viraria artefato fantasma.
    """
    temp_path = path + TEMP_SUFFIX
    try:
        write_body(temp_path)
    except Exception as exc:
        _remove_quietly(temp_path)
        raise ArtifactWriteError(path, exc)

    try:
        if os.path.exists(path):
            os.remove(path)
        os.rename(temp_path, path)
    except Exception as exc:
        _remove_quietly(temp_path)
        raise ArtifactWriteError(path, exc)
    return path


def _remove_quietly(path):
    """Remocao best-effort do temporario. Falhar aqui nao pode mascarar o erro
    original -- por isso a excecao e engolida, e SO aqui."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def write_json_via_temp(path, data):
    """JSON determinístico (`sort_keys=True`, `indent=2`), gravado num `.tmp` e
    so entao movido sobre o destino (ver `_replace_via_temp` para o que isso
    garante e o que nao garante). Serializacao identica a `file_io.write_json`
    -- os bytes produzidos sao os mesmos, so o caminho ate o disco muda."""
    def _body(temp_path):
        file_io.write_json(temp_path, data)
    return _replace_via_temp(path, _body)


def write_text_via_temp(path, text):
    """Texto UTF-8 gravado num `.tmp` e so entao movido sobre o destino, com os
    mesmos bytes que `file_io.write_text` produziria."""
    def _body(temp_path):
        file_io.write_text(temp_path, text)
    return _replace_via_temp(path, _body)


def write_checksums(root_dir, output_path, exclude_dirs=None):
    """`hash  caminho/relativo` para os arquivos sob `root_dir`, ordenado.

    `exclude_dirs` recebe caminhos de diretorio que NAO devem ser percorridos.
    O probe 20 usa isso para manter `export-root/` fora: aquele conteudo foi
    produzido pela API do MasterTool, tem hashes proprios em
    `created-artifacts.json`, e cobrir os dois com o mesmo arquivo confundiria
    "o que o probe gravou" com "o que a API produziu".

    O proprio arquivo de checksums e sempre excluido -- ele ainda nao existe
    quando os hashes sao calculados, e incluir-se-ia a si mesmo.

    Um arquivo ilegivel vira uma linha `ERRO`, nunca uma excecao: o inventario
    precisa registrar o que nao pode ser medido, em vez de abortar a escrita
    de todos os outros.
    """
    normalized_excludes = []
    for entry in (exclude_dirs or ()):
        normalized_excludes.append(os.path.abspath(entry))
    norm_output = os.path.abspath(output_path)

    lines = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if os.path.abspath(dirpath) in normalized_excludes:
            dirnames[:] = []
            continue
        dirnames[:] = [
            d for d in sorted(dirnames)
            if os.path.abspath(os.path.join(dirpath, d)) not in normalized_excludes
        ]
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.abspath(full) == norm_output:
                continue
            if name.endswith(TEMP_SUFFIX):
                # Temporario orfao de uma falha anterior nao e artefato.
                continue
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            try:
                digest = checksums.sha256_file(full)
                lines.append("%s  %s" % (digest, rel))
            except Exception as exc:
                lines.append("ERRO  %s  (%s)" % (rel, exc))
    return write_text_via_temp(output_path, "\n".join(lines) + "\n")


def write_common_artifacts(output_dir, diagnostics, safety_declaration,
                           report_markdown, checksums_exclude_dirs=None):
    """Grava os QUATRO artefatos comuns, sempre nesta ordem.

    `safety_declaration` chega PRONTA de quem chama: este modulo nao sabe, e
    nao deve saber, se a operacao e read-only ou de escrita controlada.
    `diagnostics` vazio e valido -- significa "nada a registrar", que e
    diferente de "nao verificamos".

    Devolve a lista dos caminhos gravados, na ordem em que foram gravados.
    """
    file_io.ensure_dir(output_dir)
    written = []
    written.append(write_json_via_temp(
        os.path.join(output_dir, "diagnostics.json"), diagnostics))
    written.append(write_json_via_temp(
        os.path.join(output_dir, "safety-declaration.json"), safety_declaration))
    written.append(write_text_via_temp(
        os.path.join(output_dir, "report.md"), report_markdown))
    written.append(write_checksums(
        output_dir, os.path.join(output_dir, CHECKSUMS_FILENAME),
        exclude_dirs=checksums_exclude_dirs))
    return written
