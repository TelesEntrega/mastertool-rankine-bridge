"""Relatórios para leitura humana — HTML autocontido, padrão Rankine Systems.

Puros e determinísticos: recebem dado já apurado e devolvem texto. Nenhum
relatório lê o relógio, abre o MasterTool ou consulta a rede — o que eles
mostram vem inteiro do que lhes foi passado.
"""

from mastertool_bridge.reports.qualification_report import (  # noqa: F401
    render_qualification_report,
)
