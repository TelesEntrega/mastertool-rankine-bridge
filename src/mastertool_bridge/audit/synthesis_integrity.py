"""Integridade de uma síntese multiagente — a guarda contra o resultado que
parece completo e não é.

MOTIVO, MEDIDO
==============
Na auditoria de 2026-08-01 o consolidador recebeu os dados das seis frentes
cortados em 120.000 caracteres. O corte não falhou: ele produziu um documento
bem-formado, com sumário, tabelas e conclusões — faltando três fases inteiras.
Nada avisou. O risco não é perder texto; é **publicar uma síntese aparentemente
válida sobre um conjunto incompleto**, porque quem lê não tem como saber o que
não chegou.

A regra deste módulo é que a síntese não é publicável enquanto a cardinalidade
não fechar. Não emite aviso: RECUSA. Um aviso num relatório longo é lido por
quem já sabe o que procurar, que é exatamente quem não precisa dele.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SynthesisManifest:
    """O que a síntese afirma sobre a sua própria entrada.

    `input_truncated` é declarado por quem monta o payload, e conferido contra
    `input_character_count` e `truncation_limit`: uma entrada maior que o
    limite com `input_truncated=False` é contradição, e é precisamente a forma
    que o defeito original teve — o corte aconteceu e ninguém o declarou.
    """

    expected_agent_results: int
    loaded_agent_results: int
    expected_phase_ids: tuple[str, ...]
    observed_phase_ids: tuple[str, ...]
    input_character_count: int
    input_truncated: bool
    truncation_limit: int | None = None
    journal_result_ids: tuple[str, ...] = ()
    cache_result_ids: tuple[str, ...] = ()
    verdict_origins: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_agent_results": self.expected_agent_results,
            "loaded_agent_results": self.loaded_agent_results,
            "expected_phase_ids": list(self.expected_phase_ids),
            "observed_phase_ids": list(self.observed_phase_ids),
            "input_character_count": self.input_character_count,
            "input_truncated": self.input_truncated,
            "truncation_limit": self.truncation_limit,
            "journal_result_ids": list(self.journal_result_ids),
            "cache_result_ids": list(self.cache_result_ids),
            "verdict_origins": [list(v) for v in self.verdict_origins],
        }


@dataclass
class SynthesisIntegrityResult:
    problems: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)

    @property
    def publishable(self) -> bool:
        """DERIVADO. Uma síntese com qualquer problema de cardinalidade não é
        'publicável com ressalva': ela descreve um conjunto que não é o que
        diz descrever."""
        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "publishable": self.publishable,
            "problems": list(self.problems),
            "checks_run": list(self.checks_run),
        }


def _duplicados(itens: tuple[str, ...]) -> list[str]:
    vistos: set[str] = set()
    repetidos: set[str] = set()
    for item in itens:
        if item in vistos:
            repetidos.add(item)
        vistos.add(item)
    return sorted(repetidos)


def validate_synthesis(manifest: Any) -> SynthesisIntegrityResult:
    """Recusa a síntese que não puder provar que viu tudo o que devia.

    Nunca levanta: entrada degenerada vira problema. Quem decide não publicar
    é o chamador — mas `publishable` já é a resposta.
    """
    resultado = SynthesisIntegrityResult()
    if not isinstance(manifest, SynthesisManifest):
        resultado.problems.append(
            "manifesto: esperado SynthesisManifest, recebido %s"
            % type(manifest).__name__)
        return resultado

    # --- cardinalidade de agentes -------------------------------------------
    resultado.checks_run.append("agent_cardinality")
    if manifest.loaded_agent_results != manifest.expected_agent_results:
        faltando = manifest.expected_agent_results - manifest.loaded_agent_results
        resultado.problems.append(
            "resultados de agente: esperados %d, carregados %d (%s %d)"
            % (manifest.expected_agent_results, manifest.loaded_agent_results,
               "faltam" if faltando > 0 else "sobram", abs(faltando)))

    # --- cobertura de fase ---------------------------------------------------
    resultado.checks_run.append("phase_coverage")
    esperadas = list(manifest.expected_phase_ids)
    observadas = list(manifest.observed_phase_ids)

    ausentes = [f for f in esperadas if f not in observadas]
    if ausentes:
        # O defeito original, exatamente: três fases que não chegaram e um
        # documento que se apresentou como cobrindo o roadmap inteiro.
        resultado.problems.append(
            "fase(s) esperada(s) ausente(s) na síntese: " + ", ".join(ausentes))

    desconhecidas = [f for f in observadas if f not in esperadas]
    if desconhecidas:
        resultado.problems.append(
            "fase(s) observada(s) fora do conjunto esperado: "
            + ", ".join(sorted(set(desconhecidas))))

    repetidas = _duplicados(tuple(observadas))
    if repetidas:
        resultado.problems.append(
            "fase(s) observada(s) mais de uma vez: " + ", ".join(repetidas))

    # --- truncamento ---------------------------------------------------------
    resultado.checks_run.append("truncation")
    if manifest.input_truncated:
        resultado.problems.append(
            "entrada truncada: uma síntese sobre entrada cortada não é "
            "completa, mesmo quando o texto produzido parece inteiro")
    elif (manifest.truncation_limit is not None
            and manifest.input_character_count > manifest.truncation_limit):
        resultado.problems.append(
            "truncamento NÃO declarado: %d caracteres de entrada contra limite "
            "de %d, com input_truncated=False"
            % (manifest.input_character_count, manifest.truncation_limit))

    # --- journal x cache -----------------------------------------------------
    resultado.checks_run.append("journal_cache_agreement")
    journal = set(manifest.journal_result_ids)
    cache = set(manifest.cache_result_ids)
    if journal or cache:
        so_no_journal = sorted(journal - cache)
        so_no_cache = sorted(cache - journal)
        if so_no_journal:
            resultado.problems.append(
                "resultado(s) no journal e ausente(s) no cache: "
                + ", ".join(so_no_journal))
        if so_no_cache:
            resultado.problems.append(
                "resultado(s) no cache e ausente(s) no journal: "
                + ", ".join(so_no_cache))

    # --- rastreabilidade do veredito ----------------------------------------
    resultado.checks_run.append("verdict_traceability")
    conhecidos = journal | cache
    if manifest.verdict_origins and conhecidos:
        orfaos = sorted({origem for _v, origem in manifest.verdict_origins
                         if origem not in conhecidos})
        if orfaos:
            resultado.problems.append(
                "veredito(s) sem origem rastreável entre os resultados "
                "carregados: " + ", ".join(orfaos))

    return resultado


def assert_publishable(manifest: Any) -> None:
    """Para quem prefere falhar alto — o consolidador, tipicamente."""
    resultado = validate_synthesis(manifest)
    if not resultado.publishable:
        raise ValueError(
            "síntese não publicável: " + "; ".join(resultado.problems))
