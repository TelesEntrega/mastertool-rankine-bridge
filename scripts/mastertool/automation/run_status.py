# -*- coding: utf-8 -*-
"""Escrita de `status.json` + `status-history.jsonl` (lado interno do runner
supervisionado). Contrato: `docs/16-supervised-runner-contract.md`, secao 4.

Reaproveita `common/file_io.py` para toda a escrita de arquivo (append_text/
write_text), nao reimplementa I/O de baixo nivel.

Compatibilidade: IronPython 2.7 (sem f-strings, pathlib, type hints,
`os.replace`).
"""
from __future__ import print_function

import datetime
import json
import os

from common import file_io

# Os 11 estados do contrato (secao 4), na ordem de progresso. 'created' e
# 'mastertool_started' sao escritos pelo HOST -- o runner interno nunca os
# escreve, mas eles continuam validos aqui porque o mesmo StatusWriter/
# vocabulario de estados e compartilhado como referencia (e porque um
# consumidor externo pode querer validar um status.json inteiro, incluindo
# os estados escritos pelo host, contra esta mesma lista).
VALID_STATES = (
    "created",
    "mastertool_started",
    "script_started",
    "provenance_validated",
    "project_identity_validated",
    "scanning",
    "exporting",
    # 'probing_ladder_dynamic_surface' e um estado DEDICADO (ao contrario do
    # probe 16, que reusa 'scanning'). Motivo: o probe 17 tem um GATE DE
    # VALIDADE proprio -- o controle 'textual_declaration' -- cujo resultado
    # decide se a fase L1 avança ou fica marcada como inconclusiva. Misturar
    # essa transicao com 'scanning' apagaria essa distincao no
    # status-history.jsonl, que e o registro de auditoria da execucao: um
    # leitor externo nao conseguiria distinguir "sondando estrutura generica"
    # de "sondando a superficie dinamica cujo resultado pode ser
    # inconclusivo" so olhando o historico.
    "probing_ladder_dynamic_surface",
    # Canal Extender/providers/descriptors -- fronteira operacional propria,
    # com gate distinto dos outros dois (Extender acessivel -> canal
    # enumeravel -> controle reencontrado). Um estado generico exigiria
    # consultar campos auxiliares para saber qual operacao estava em curso
    # quando uma execucao parou.
    "probing_ladder_extender_surface",
    # Assinatura de export_xml -- gate proprio: comprovar a assinatura
    # COMPLETA sem invocar o metodo.
    "probing_plcopen_export_signature",
    # Primeira operacao que ESCREVE. Estado proprio para o
    # status-history.jsonl distinguir "sondou" de "exportou" -- a diferenca
    # importa numa auditoria.
    "exporting_plcopen_xml",
    "validating",
    "completed",
    "failed",
    "needs_interaction",
)

TERMINAL_STATES = ("completed", "failed", "needs_interaction")

SCHEMA_VERSION = 1


class StatusError(Exception):
    """Estado desconhecido (fora de VALID_STATES) passado para set_state()."""
    pass


class StatusWriter(object):
    """Escreve `status.json` (estado corrente) e `status-history.jsonl`
    (append-only, um registro por transicao) dentro de `run_dir`.

    Por que a escrita de status.json NAO e atomica de verdade (contrato,
    secao 4): IronPython 2.7 nao tem `os.replace` (introduzido no Python
    3.3). No Windows, `os.rename` levanta excecao se o destino ja existir --
    entao o procedimento obrigatorio e (1) escrever `status.json.tmp`, (2)
    remover `status.json` se ele existir, (3) `os.rename(tmp, status.json)`.
    Entre os passos (2) e (3) existe uma janela real em que `status.json` NAO
    EXISTE no disco -- se o processo morrer exatamente ali (o MasterTool
    fechado a forca, por exemplo), um leitor externo (o host, que faz
    polling) veria o arquivo ausente e nao saberia se isso significa "runner
    ainda nao comecou" ou "runner morreu no meio de uma escrita". Por isso
    `status-history.jsonl` e a fonte de verdade confiavel nesse cenario: cada
    linha e gravada ANTES da troca do status.json corrente, e o arquivo
    NUNCA e truncado nem reescrito (so append) -- entao mesmo que o
    status.json esteja ausente ou desatualizado no momento em que o host o
    le, a ultima linha do historico sempre reflete a ultima transicao que de
    fato foi concluida. Nao usamos `System.IO.File.Replace` (.NET) para
    tornar a troca atomica porque isso adicionaria uma superficie de
    dependencia nova, nao aprovada, so para fechar uma janela que o log
    append-only ja mitiga suficientemente (contrato, secao 4).
    """

    def __init__(self, run_dir, run_id):
        self.run_dir = run_dir
        self.run_id = run_id
        self.status_path = os.path.join(run_dir, "status.json")
        self.status_tmp_path = os.path.join(run_dir, "status.json.tmp")
        self.history_path = os.path.join(run_dir, "status-history.jsonl")

    def set_state(self, state, detail=None, error=None, traceback_text=None):
        """Registra uma transicao de estado. Levanta StatusError se `state`
        nao estiver em VALID_STATES (erro de programacao do chamador -- isso
        NAO deve ser silenciado). Falhas de I/O ao gravar em disco, ao
        contrario, NUNCA sobem como excecao daqui: uma aquisicao em
        andamento nao pode ser derrubada so porque o disco de status esta
        temporariamente indisponivel. Sempre retorna o registro montado
        (mesmo que a escrita em disco tenha falhado), para o chamador poder
        inspecionar/logar por conta propria."""
        if state not in VALID_STATES:
            raise StatusError(
                "Estado desconhecido: '%s'. Estados validos: %s"
                % (state, ", ".join(VALID_STATES)))

        record = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "state": state,
            "updated_at": datetime.datetime.now().isoformat(),
            "detail": detail,
            "error": error,
            "traceback": traceback_text,
        }

        # 0) ESPELHA na aba "Mensagens de script" do MasterTool.
        #
        # ACHADO REAL da execucao 2026-07-24_21-21-01: o runner nao tinha
        # NENHUM print(), diferente de todos os probes. Com a UI visivel --
        # cujo unico proposito e supervisao humana -- o operador via a aba de
        # Mensagens VAZIA e concluiu, com razao, que o script nao havia
        # rodado. O estado estava correto no disco, mas quem supervisiona nao
        # olha disco: olha a tela.
        #
        # E o primeiro passo (antes do historico) de proposito: se a gravacao
        # em disco falhar por completo, a tela continua sendo evidencia de
        # progresso. print() nunca derruba a aquisicao.
        try:
            line = "[%s] %s" % (state.upper(), detail or "")
            if error:
                line = line + " | ERRO: %s" % (error,)
            print(line.rstrip())
        except Exception:
            pass

        # 1) historico append-only -- fonte de verdade confiavel mesmo se o
        # passo 2 (troca do status.json) falhar ou for interrompido no meio.
        try:
            self._append_history(record)
        except Exception:
            pass  # nunca derruba a aquisicao por causa de uma falha de log

        # 2) status.json.tmp -> remove status.json -> rename. Falha aqui
        # tambem nao derruba a aquisicao -- exceto que para o estado
        # terminal 'failed' tentamos gravar de novo (o chamador quer o
        # maximo de chance possivel do host saber que a aquisicao falhou).
        try:
            self._write_status_json(record)
        except Exception:
            if state == "failed":
                try:
                    self._write_status_json(record)
                except Exception:
                    pass

        return record

    def _append_history(self, record):
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        file_io.append_text(self.history_path, line + "\n")

    def _write_status_json(self, record):
        text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True)
        file_io.write_text(self.status_tmp_path, text + "\n")
        if os.path.exists(self.status_path):
            os.remove(self.status_path)
        os.rename(self.status_tmp_path, self.status_path)
