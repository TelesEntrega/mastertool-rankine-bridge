"""R9.2 — ingestão da tabela de pontos de controle.

DUAS CAMADAS, E A SEPARAÇÃO É O PONTO
=====================================
`ingest_rows` recebe LINHAS e não conhece xlsx. `read_xlsx` lê o arquivo e não
conhece semântica. Isso torna a semântica testável com fixture sintética — sem
gerar planilha em teste — e mantém dado de cliente longe do repositório.

O QUE FOI MEDIDO NO CORPUS REAL, E QUE DECIDIU AS REGRAS
========================================================
* **A tabela não começa em A1.** Cabeçalho na linha 4, primeira coluna em `B`.
  Localizar o cabeçalho por conteúdo, e não por posição fixa, é o que evita
  reescrever o ingestor a cada revisão do arquivo.

* **Equipamento vem em linha-cabeçalho de seção**, não em coluna: uma linha
  com só a primeira célula preenchida. Quem lê carrega estado. Um ponto que
  apareça antes de qualquer seção fica com equipamento `absent` — nunca
  atribuído ao primeiro que aparecer.

* **Colunas de segurança existem e estão vazias**, em todas as revisões do
  arquivo. `absent`, nunca zero. Zero afirmaria que foi contado e deu nada.

* **Divergência de classificação.** Dispositivos claramente de segurança
  (barreira, botão de emergência) aparecem tipados como entrada digital comum.
  O ingestor REGISTRA a divergência e não escolhe lado: escolher seria decidir
  classificação de segurança por heurística de nome.
"""

from __future__ import annotations

import re
from typing import Any

from mastertool_bridge.plant.model import (
    IO_CLASSES,
    Equipment,
    Fact,
    Gap,
    IOPoint,
    Origin,
    PlantModel,
)

SCHEMA_VERSION = 1

# Cabeçalho da fonte → classe do modelo. Mapa LITERAL: uma coluna nova é
# decisão de contrato, e não descoberta por semelhança de nome.
COLUMN_TO_CLASS = {
    "ED": "digital_input",
    "SD": "digital_output",
    "EDS": "safety_digital_input",
    "SDS": "safety_digital_output",
    "EA": "analog_input",
    "SA": "analog_output",
    "ED-CPS": "safety_controller_input",
    "SD-CPS": "safety_controller_output",
}

# Colunas de identidade e descrição, pelo texto que aparece na fonte.
COL_ITEM = "ITEM"
COL_TAG = "TAG"
COL_DESC = "DESCRICAO"
COL_LOC = "LOCALIZACAO"
COL_PROTO = "PROTOCOLO"

# Termos que indicam FUNÇÃO de segurança no texto descritivo. Eles NÃO
# reclassificam nada — servem só para detectar a divergência entre o que o
# texto descreve e a coluna em que o ponto foi contado.
_TERMOS_DE_SEGURANCA = (
    "emergenc", "barreira", "safety", "cortina", "intertrav", "scanner",
    "rele de seguranca", "nr-12", "nr12",
)


def _sem_acento(texto: str) -> str:
    """Normalização mínima para comparar cabeçalho e procurar termos.

    A fonte real mistura acentuação e caixa entre revisões; comparar o texto
    cru faria o ingestor quebrar por causa de um `Ç`.
    """
    tabela = str.maketrans("ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç",
                           "AAAAAEEEEIIIIOOOOOUUUUCaaaaaeeeeiiiiooooouuuuc")
    return texto.translate(tabela)


def _chave(texto: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", _sem_acento(texto or "").upper())


def _inteiro(texto: str):
    try:
        return int(float(str(texto).strip()))
    except (TypeError, ValueError):
        return None


def find_header(rows) -> tuple:
    """`(indice, mapa coluna->campo)` do cabeçalho, localizado por CONTEÚDO.

    Procurar por posição fixa amarraria o ingestor a uma revisão do arquivo.
    O cabeçalho é a primeira linha que contém `TAG` e pelo menos uma coluna de
    contagem — os dois juntos, porque `TAG` sozinho aparece em outros lugares.
    """
    for indice, linha in enumerate(rows):
        chaves = {_chave(v): k for k, v in linha.items() if v}
        if COL_TAG not in chaves:
            continue
        if not any(c in chaves for c in COLUMN_TO_CLASS):
            continue
        return indice, chaves
    return -1, {}


def _origem(documento, aba, versao, celula) -> Origin:
    return Origin(document=documento, sheet=aba, version=versao,
                  locator=celula)


def ingest_rows(rows, *, document: str, sheet: str | None = None,
                version: str | None = None,
                project: str = "planta") -> PlantModel:
    """Constrói o modelo a partir de linhas já lidas.

    `rows` é uma sequência de dicionários `coluna -> texto`, onde `coluna` é a
    letra da planilha. A letra vai para a `origin` de cada fato: sem ela, um
    humano não consegue abrir o arquivo e olhar para a mesma célula.
    """
    modelo = PlantModel(project=project, source_version=version)

    indice, chaves = find_header(rows)
    if indice < 0:
        modelo.gaps.append(Gap(
            kind="source_unreadable", subject=document,
            detail="cabeçalho não localizado: nenhuma linha tem TAG e ao "
                   "menos uma coluna de contagem",
            origin=_origem(document, sheet, version, "?")))
        return modelo

    def coluna(campo):
        return chaves.get(campo)

    presentes = {c: coluna(c) for c in COLUMN_TO_CLASS if coluna(c)}
    ausentes_de_cabecalho = [c for c in COLUMN_TO_CLASS if c not in presentes]

    secao = None
    secao_origem = None
    por_equipamento: dict = {}
    vistos: dict = {}
    contagem_por_classe = {c: 0 for c in IO_CLASSES}

    for numero, linha in enumerate(rows[indice + 1:], start=indice + 2):
        preenchidas = {k: v for k, v in linha.items() if str(v).strip()}
        if not preenchidas:
            continue

        # LINHA DE SEÇÃO: só a coluna do item preenchida. É assim que o
        # equipamento chega — posicionalmente, e por isso a origem é gravada.
        col_item = coluna(COL_ITEM)
        col_tag = coluna(COL_TAG)
        if len(preenchidas) == 1 and col_item in preenchidas:
            secao = str(preenchidas[col_item]).strip()
            secao_origem = _origem(document, sheet, version,
                                   "%s%d" % (col_item, numero))
            por_equipamento.setdefault(secao, [])
            continue

        if not col_tag or not str(linha.get(col_tag, "")).strip():
            continue
        tag = str(linha[col_tag]).strip()

        if tag in vistos:
            modelo.diagnostics.append({
                "code": "duplicate_tag", "subject": tag,
                "message": "TAG repetida nas linhas %d e %d; a identidade de "
                           "um ponto não pode ser ambígua"
                           % (vistos[tag], numero)})
        vistos[tag] = numero

        def fato_texto(campo, obrigatorio=True):
            col = coluna(campo)
            bruto = str(linha.get(col, "")).strip() if col else ""
            if bruto:
                return Fact(value=bruto, state="confirmed",
                            origin=_origem(document, sheet, version,
                                           "%s%d" % (col, numero)))
            if not obrigatorio:
                return Fact(value=None, state="absent")
            return Fact(value=None, state="absent",
                        note="coluna %s vazia na linha %d" % (campo, numero))

        contagens: dict = {}
        for cabecalho, classe in COLUMN_TO_CLASS.items():
            col = presentes.get(cabecalho)
            if col is None:
                # A coluna nem existe no cabeçalho: ausência de esquema, e não
                # de dado. Os dois estados são diferentes.
                contagens[classe] = Fact(
                    value=None, state="absent",
                    note="coluna %s ausente do cabeçalho" % cabecalho)
                continue
            valor = _inteiro(linha.get(col, ""))
            if valor is None:
                contagens[classe] = Fact(
                    value=None, state="absent",
                    note="coluna %s existe e está vazia nesta linha" % cabecalho)
            else:
                contagens[classe] = Fact(
                    value=valor, state="confirmed",
                    origin=_origem(document, sheet, version,
                                   "%s%d" % (col, numero)))
                contagem_por_classe[classe] += valor

        equipamento = (Fact(value=secao, state="confirmed", origin=secao_origem)
                       if secao else
                       Fact(value=None, state="absent",
                            note="ponto apareceu antes de qualquer linha de "
                                 "seção; atribuí-lo ao primeiro equipamento "
                                 "seria inventar o dono"))

        descricao = fato_texto(COL_DESC)
        ponto = IOPoint(
            tag=tag,
            description=descricao,
            equipment=equipamento,
            location=fato_texto(COL_LOC, obrigatorio=False),
            io_counts=contagens,
            protocol=fato_texto(COL_PROTO, obrigatorio=False),
            diagnostics=tuple(_divergencia_de_seguranca(
                tag, descricao, secao, contagens, document, sheet, version,
                numero)),
        )
        modelo.points.append(ponto)
        if secao:
            por_equipamento[secao].append(tag)

    for nome, tags in por_equipamento.items():
        modelo.equipment.append(Equipment(
            name=nome,
            origin=_origem(document, sheet, version, "seção"),
            point_tags=tuple(sorted(tags))))

    modelo.gaps.extend(_lacunas(modelo, contagem_por_classe, presentes,
                                ausentes_de_cabecalho, document, sheet,
                                version))
    for ponto in modelo.points:
        for d in ponto.diagnostics:
            modelo.diagnostics.append(d)
    return modelo


def _divergencia_de_seguranca(tag, descricao, secao, contagens, documento,
                              aba, versao, numero) -> list:
    """O texto descreve função de segurança e a contagem diz outra coisa?

    NÃO reclassifica. Decidir que um ponto é de segurança porque a descrição
    tem a palavra "barreira" seria classificar segurança por heurística de
    nome — e a consequência de errar não é simétrica.
    """
    texto = _sem_acento(str(descricao.value or "")).lower()
    contexto = _sem_acento(str(secao or "")).lower()
    parece = any(t in texto or t in contexto for t in _TERMOS_DE_SEGURANCA)
    if not parece:
        return []
    classificado = any(f.usable and f.value
                       for c, f in contagens.items()
                       if c.startswith("safety_"))
    if classificado:
        return []
    return [{
        "code": "safety_classification_divergence",
        "subject": tag,
        "row": numero,
        "message": ("a descrição indica função de segurança e o ponto está "
                    "contado apenas em colunas não-seguras. O ingestor não "
                    "reclassifica: a decisão é de engenharia"),
    }]


def _lacunas(modelo, contagem_por_classe, presentes, ausentes_de_cabecalho,
             documento, aba, versao) -> list:
    lacunas = []

    # COLUNA EXISTE E NUNCA FOI PREENCHIDA. Este é o caso que motivou o
    # estado `absent` separado de zero: a fonte declara a classe no cabeçalho
    # e não traz um único valor.
    for cabecalho, col in sorted(presentes.items()):
        classe = COLUMN_TO_CLASS[cabecalho]
        if contagem_por_classe.get(classe):
            continue
        lacunas.append(Gap(
            kind="declared_but_empty_column",
            subject=cabecalho,
            detail=("a coluna %s existe no cabeçalho e não tem uma única "
                    "linha preenchida. Isso é ausência de DADO, não ausência "
                    "de classe — e não pode ser lido como zero" % cabecalho),
            origin=_origem(documento, aba, versao, "%s (coluna)" % col),
            blocks_generation=classe in (
                "safety_digital_input", "safety_digital_output",
                "safety_controller_input", "safety_controller_output")))

    for cabecalho in ausentes_de_cabecalho:
        lacunas.append(Gap(
            kind="column_absent_from_schema", subject=cabecalho,
            detail="a coluna %s não existe nesta revisão da fonte" % cabecalho,
            origin=_origem(documento, aba, versao, "cabeçalho"),
            blocks_generation=False))

    sem_dono = [p.tag for p in modelo.points if not p.equipment.usable]
    if sem_dono:
        lacunas.append(Gap(
            kind="points_without_equipment", subject="equipamento",
            detail="%d ponto(s) sem seção: %s" % (len(sem_dono),
                                                  ", ".join(sorted(sem_dono))),
            origin=_origem(documento, aba, versao, "seções")))
    return lacunas


# =============================================================================
# adaptador de arquivo — a única parte que conhece xlsx
# =============================================================================

def read_xlsx(path, sheet_index: int = 0) -> tuple:
    """`(rows, sheet_name)` de uma planilha, sem dependência externa.

    Lê `sharedStrings` E strings inline: o corpus real usa inline, e um leitor
    que só tratasse `sharedStrings` devolveria uma tabela vazia sem erro
    nenhum — que é a pior forma de falhar.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(str(path)) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        abas = [s.get("name") for s in wb.iter(ns + "sheet")]
        nome = abas[sheet_index] if sheet_index < len(abas) else None

        compartilhadas = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            compartilhadas = ["".join(t.text or "" for t in si.iter(ns + "t"))
                              for si in ss.iter(ns + "si")]
        planilha = ET.fromstring(
            z.read("xl/worksheets/sheet%d.xml" % (sheet_index + 1)))

    def valor(celula):
        inline = "".join(t.text or "" for t in celula.iter(ns + "t"))
        if inline:
            return inline
        v = celula.find(ns + "v")
        if v is None:
            return ""
        if celula.get("t") == "s":
            try:
                return compartilhadas[int(v.text)]
            except (TypeError, ValueError, IndexError):
                return ""
        return v.text or ""

    linhas = []
    for linha in planilha.iter(ns + "row"):
        atual = {}
        for celula in linha:
            texto = valor(celula).strip()
            if texto:
                letra = "".join(c for c in (celula.get("r") or "")
                                if c.isalpha())
                atual[letra] = texto
        linhas.append(atual)
    return linhas, nome


def ingest_xlsx(path, *, project: str = "planta",
                version: str | None = None) -> PlantModel:
    """Conveniência: lê o arquivo e ingere. Nenhuma semântica mora aqui."""
    import os

    linhas, aba = read_xlsx(path)
    return ingest_rows(linhas, document=os.path.basename(str(path)),
                       sheet=aba, version=version, project=project)
