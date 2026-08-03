"""Relatório de qualificação de repetibilidade — HTML autocontido (fase R11).

Gera o documento que um humano lê depois de um lote da fase R1: um arquivo
único, sem CDN, sem webfont e sem JS, no padrão visual Rankine Systems.

DUAS REGRAS EDITORIAIS QUE VALEM MAIS QUE O CSS
===============================================
1. **O que a evidência comprova fica separado do que exige medição.** Um lote
   de três execuções equivalentes comprova que o mecanismo é estável em três
   execuções — não que a operação é repetível, que é afirmação sobre dez. O
   relatório diz as duas coisas em lugares diferentes e nunca funde as duas.
2. **Volátil permitido aparece.** Estar na allowlist dispensa o campo de
   reprovar o lote; não dispensa de ser mostrado, com todos os valores
   observados. Um campo que alterna entre dois valores em dez execuções é um
   achado — e é exatamente o que um veredito binário esconderia.

O gerador é PURO e determinístico: mesma entrada, mesmo HTML. Nenhuma hora é
lida do relógio — `generated_at` entra como dado, para que dois relatórios do
mesmo lote sejam idênticos byte a byte e possam ser comparados.
"""

from __future__ import annotations

import html
from typing import Any

SCHEMA_VERSION = 1

# Paleta e componentes copiados do guia canônico
# (`~/.claude/PADRAO_VISUAL_RELATORIOS_RANKINE.md`) sem alteração de cor,
# tamanho ou raio. Alterar aqui desalinha este relatório de todos os outros
# documentos da empresa.
_CSS = """
:root{
  --navy:#2b2c46; --navy-2:#1e1f33; --brand-blue:#313983;
  --orange:#f58634; --orange-dk:#d96f1f;
  --slate:#52565e; --muted:#7a808a;
  --bg:#ffffff; --bg-soft:#f4f6f9; --line:#dfe3ea;
  --ok:#1f8a5b; --warn:#c9820a; --crit:#c0392b;
  --mono:ui-monospace,"Cascadia Mono","Consolas","SFMono-Regular",monospace;
  --sans:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
  color-scheme:light;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--navy);font:16px/1.65 var(--sans);-webkit-text-size-adjust:100%}
.wrap{max-width:1080px;margin:0 auto;padding:0 28px}
.hero{background:linear-gradient(135deg,var(--navy-2) 0%,var(--navy) 55%,#3a3c60 100%);color:#fff;padding:38px 0 44px;position:relative;overflow:hidden}
.hero::after{content:"";position:absolute;right:-90px;top:-90px;width:340px;height:340px;border-radius:50%;background:radial-gradient(circle,rgba(245,134,52,.22),transparent 68%)}
.hero .wrap{position:relative;z-index:1}
.hero img.logo{height:52px;width:auto;display:block}
.eyebrow{margin:26px 0 6px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--orange);font-weight:700}
.hero h1{margin:0;font-size:clamp(26px,4.2vw,40px);line-height:1.15;font-weight:700;letter-spacing:-.015em}
.hero .sub{margin:12px 0 0;font-size:17px;color:#cfd2e0;max-width:64ch}
.rule{height:4px;width:78px;background:var(--orange);margin:22px 0 0;border-radius:2px}
.meta{margin-top:26px;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px 18px;font-size:13px}
.meta div{border-left:2px solid rgba(245,134,52,.55);padding-left:11px;min-width:0}
.meta b{display:block;color:#9aa0b8;font-weight:600;font-size:11px;letter-spacing:.09em;text-transform:uppercase;margin-bottom:3px}
.meta span{color:#fff;display:block;overflow-wrap:anywhere;line-height:1.4}
.meta span.small{font-size:11.5px}
nav.toc{background:var(--bg-soft);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
nav.toc .wrap{display:flex;gap:4px;overflow-x:auto;padding-top:8px;padding-bottom:8px;scrollbar-width:thin}
nav.toc a{white-space:nowrap;color:var(--slate);text-decoration:none;font-size:13px;font-weight:600;padding:6px 11px;border-radius:5px}
nav.toc a:hover{background:#e6eaf1;color:var(--navy)}
section{padding:46px 0 8px;border-top:1px solid var(--line)}
section:first-of-type{border-top:0}
h2{font-size:13px;letter-spacing:.13em;text-transform:uppercase;color:var(--orange-dk);margin:0 0 6px;font-weight:800}
h2 .n{color:var(--muted);margin-right:9px}
h3{font-size:clamp(21px,2.6vw,28px);margin:0 0 16px;line-height:1.25;letter-spacing:-.01em}
h4{font-size:17px;margin:30px 0 10px}
p{margin:0 0 14px;max-width:74ch}
.lead{font-size:18px;color:var(--slate);max-width:70ch}
strong{font-weight:700}
code{font-family:var(--mono);font-size:.88em;background:var(--bg-soft);border:1px solid var(--line);border-radius:4px;padding:1px 5px}
a{color:var(--brand-blue)}
ul,ol{max-width:74ch;padding-left:22px}
li{margin:6px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:14px;margin:22px 0 8px}
@media(min-width:760px){.kpis.k3{grid-template-columns:repeat(3,1fr)}.kpis.k4{grid-template-columns:repeat(4,1fr)}}
.kpi{background:var(--bg-soft);border:1px solid var(--line);border-top:3px solid var(--orange);border-radius:7px;padding:15px 16px}
.kpi .v{font-size:29px;font-weight:800;line-height:1.05;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.kpi .l{font-size:12.5px;color:var(--slate);margin-top:5px;line-height:1.4}
.kpi.blue{border-top-color:var(--brand-blue)}
.kpi.gray{border-top-color:#9aa2b1}
.box{border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:0 7px 7px 0;background:var(--bg-soft);padding:15px 18px;margin:20px 0}
.box p:last-child{margin-bottom:0}
.box .t{font-weight:800;font-size:12px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:7px;color:var(--slate)}
.box.ok{border-left-color:var(--ok)} .box.ok .t{color:var(--ok)}
.box.warn{border-left-color:var(--warn)} .box.warn .t{color:var(--warn)}
.box.crit{border-left-color:var(--crit);background:#fdf3f2} .box.crit .t{color:var(--crit)}
.box.info{border-left-color:var(--brand-blue)} .box.info .t{color:var(--brand-blue)}
.tw{overflow-x:auto;margin:18px 0;border:1px solid var(--line);border-radius:7px}
table{border-collapse:collapse;width:100%;font-size:14.5px;min-width:520px}
th{background:var(--navy);color:#fff;text-align:left;padding:10px 13px;font-size:12px;letter-spacing:.05em;text-transform:uppercase;font-weight:700;white-space:nowrap}
td{padding:9px 13px;border-top:1px solid var(--line);vertical-align:top}
tbody tr:nth-child(even){background:#fafbfd}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tfoot td{font-weight:700;background:#eef1f6;border-top:2px solid var(--navy)}
caption{caption-side:bottom;text-align:left;padding:10px 13px;font-size:13px;color:var(--muted);line-height:1.55;background:#fff;border-top:1px solid var(--line)}
.chip{display:inline-block;font-size:11px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;padding:2.5px 8px;border-radius:20px;white-space:nowrap}
.c-crit{background:#fbe4e1;color:#a5281a}
.c-high{background:#fdeccd;color:#8a5a05}
.c-med{background:#e2e9f7;color:#2c3f7a}
.c-ok{background:#dbf1e6;color:#146143}
.c-open{background:#eceef2;color:#5b6270}
.steps{counter-reset:s;list-style:none;padding:0;margin:20px 0;max-width:none}
.steps li{counter-increment:s;position:relative;padding:0 0 20px 46px;border-left:2px solid var(--line);margin:0 0 0 15px}
.steps li:last-child{border-left-color:transparent;padding-bottom:0}
.steps li::before{content:counter(s);position:absolute;left:-15px;top:-2px;width:28px;height:28px;border-radius:50%;background:var(--navy);color:#fff;font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center}
.steps li b{display:block;font-size:16px;margin-bottom:3px}
.steps li span{color:var(--slate);font-size:14.5px}
footer{background:var(--navy-2);color:#c9ccdb;margin-top:56px;padding:30px 0 34px;font-size:13.5px}
footer img.logo{height:34px;width:auto;display:block;margin-bottom:18px}
footer .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px}
footer b{color:#fff;display:block;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:5px}
footer a{color:var(--orange)}
@media print{
  nav.toc{display:none}
  body{font-size:12pt}
  section{page-break-inside:avoid}
  .hero{background:var(--navy-2) !important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""


def _e(valor: Any) -> str:
    """Escapa para HTML. Tudo que vem do relatório passa por aqui — nome de
    diretório é dado externo, e dado externo não entra cru em documento."""
    return html.escape("" if valor is None else str(valor), quote=True)


def _chip(texto: str, classe: str) -> str:
    return '<span class="chip %s">%s</span>' % (classe, _e(texto))


def _nome_curto(caminho: str) -> str:
    return str(caminho).replace("\\", "/").rstrip("/").split("/")[-1] or caminho


def _tabela_execucoes(equivalencia: dict) -> str:
    linhas = []
    referencia = equivalencia.get("reference")
    for geracao in equivalencia.get("per_generation", []):
        caminho = geracao.get("generation", "")
        eh_referencia = caminho == referencia
        if eh_referencia:
            estado = _chip("Referência", "c-med")
            detalhe = ("equivalente a si mesma por definição, não por medição")
        elif geracao.get("equivalent"):
            estado = _chip("Equivalente", "c-ok")
            detalhe = "nenhuma divergência nas camadas comparadas"
        else:
            estado = _chip("Diverge", "c-crit")
            divergencias = geracao.get("divergences") or []
            detalhe = "<br>".join(_e(d) for d in divergencias[:4])
            if len(divergencias) > 4:
                detalhe += "<br>… e mais %d" % (len(divergencias) - 4)
        camadas = ", ".join(geracao.get("layers_compared") or []) or "—"
        linhas.append(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (_e(_nome_curto(caminho)), estado, _e(camadas), detalhe))
    return "\n".join(linhas)


def _tabela_volateis(equivalencia: dict) -> str:
    linhas = []
    for campo in equivalencia.get("volatile_distribution", []):
        distintos = campo.get("distinct_values", 0)
        observados = campo.get("observed_in", 0)
        if distintos == observados and observados > 1:
            leitura = "varia a cada execução, como esperado"
            chip = _chip("Esperado", "c-ok")
        elif distintos == 1:
            leitura = "constante nas execuções observadas"
            chip = _chip("Constante", "c-med")
        else:
            leitura = ("assume %d valor(es) em %d execução(ões) — alternância "
                       "merece explicação" % (distintos, observados))
            chip = _chip("Alterna", "c-high")
        linhas.append(
            '<tr><td><code>%s</code></td><td class="num">%d</td>'
            '<td class="num">%d</td><td>%s %s</td></tr>'
            % (_e(campo.get("field")), distintos, observados, chip, _e(leitura)))
    return "\n".join(linhas)


def _lista(itens, vazio: str) -> str:
    itens = list(itens or [])
    if not itens:
        return "<p>%s</p>" % _e(vazio)
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % _e(i) for i in itens)


def render_qualification_report(
    result: dict,
    *,
    generated_at: str,
    qualification_id: str | None = None,
    template_profile: str | None = None,
    product_version: str | None = None,
    logo_data_uri: str | None = None,
) -> str:
    """HTML autocontido a partir de `QualificationResult.to_dict()` ou de
    `RepeatabilityResult.to_dict()`.

    `generated_at` é OBRIGATÓRIO e entra como dado: o gerador não lê o
    relógio, para que dois relatórios do mesmo lote sejam idênticos e
    comparáveis.

    `logo_data_uri` é opcional porque o ativo da marca vive fora deste
    repositório. Sem ele o documento sai sem logo, e não com um logo
    inventado.
    """
    if not isinstance(result, dict):
        raise TypeError("result: esperado dict de relatório, recebido %s"
                        % type(result).__name__)

    equivalencia = result.get("equivalence") or result
    qualificado = bool(result.get("qualified", equivalencia.get("repeatable")))
    solicitadas = result.get("requested_runs", equivalencia.get("count", 0))
    concluidas = result.get("completed_runs", equivalencia.get("count", 0))
    piso = equivalencia.get("minimum_required", 0)
    equivalentes = equivalencia.get("equivalent_count", 0)
    total_geracoes = len(equivalencia.get("per_generation", []))
    violacoes = equivalencia.get("independence_violations", []) or []
    problemas = list(result.get("problems", []) or [])
    problemas += [p for p in (equivalencia.get("problems") or [])
                  if p not in problemas]
    identificador = (qualification_id or result.get("qualification_id")
                     or "(sem identificador)")

    veredito_chip = (_chip("Qualificado", "c-ok") if qualificado
                     else _chip("Reprovado", "c-crit"))

    logo_capa = ('<img class="logo" src="%s" alt="Rankine Systems">'
                 % _e(logo_data_uri) if logo_data_uri else "")
    logo_rodape = ('<img class="logo" src="%s" alt="Rankine Systems">'
                   % _e(logo_data_uri) if logo_data_uri else "")

    # Caixas do sumário: o que a evidência comprova e o que ela não comprova.
    caixas = []
    if not qualificado and concluidas and equivalentes == total_geracoes \
            and not violacoes and concluidas < piso:
        caixas.append(
            '<div class="box warn"><div class="t">1 &middot; Estável, e ainda '
            'não qualificado</div><p>As %d execuções concluídas são '
            'equivalentes entre si e independentes. Isso comprova estabilidade '
            'do mecanismo <strong>nestas %d execuções</strong> — não '
            'repetibilidade, que é afirmação sobre %d. O veredito não '
            'arredonda.</p></div>' % (concluidas, concluidas, piso))
    if violacoes:
        caixas.append(
            '<div class="box crit"><div class="t">%d &middot; Execuções não '
            'independentes</div><p>Duas ou mais gerações nasceram com os '
            'mesmos GUIDs de objeto. Execuções que compartilham GUID não são '
            'independentes, e comparar uma com a outra não prova nada — pode '
            'ser a mesma execução contada duas vezes.</p>%s</div>'
            % (len(caixas) + 1, _lista(violacoes, "")))
    if concluidas < solicitadas:
        caixas.append(
            '<div class="box crit"><div class="t">%d &middot; Lote incompleto'
            '</div><p>%d de %d execuções concluíram. Uma execução '
            'inconsistente reprova a qualificação mesmo que as demais '
            'passem.</p></div>' % (len(caixas) + 1, concluidas, solicitadas))
    if qualificado:
        caixas.append(
            '<div class="box ok"><div class="t">1 &middot; Lote qualificado'
            '</div><p>As %d execuções concluíram, são equivalentes entre si e '
            'independentes, e o número atinge o piso normativo de %d.</p>'
            '</div>' % (concluidas, piso))
    if not caixas:
        caixas.append(
            '<div class="box"><div class="t">1 &middot; Sem achado '
            'classificado</div><p>O lote não produziu achado que se encaixe '
            'nas classes conhecidas. Isso é, em si, um achado sobre o '
            'relatório.</p></div>')

    secoes_toc = [
        ("s1", "Sumário"), ("s2", "Método"), ("s3", "Execuções"),
        ("s4", "Voláteis"), ("s5", "Limites"),
    ]

    partes: list[str] = []
    partes.append("<!doctype html>")
    partes.append('<html lang="pt-BR"><head><meta charset="utf-8">')
    partes.append('<meta name="viewport" content="width=device-width,'
                  'initial-scale=1">')
    partes.append("<title>Qualificação de repetibilidade — %s</title>"
                  % _e(identificador))
    partes.append("<style>%s</style></head><body>" % _CSS)

    # --- capa ---------------------------------------------------------------
    partes.append('<header class="hero"><div class="wrap">')
    partes.append(logo_capa)
    partes.append('<div class="eyebrow">Relatório técnico &middot; '
                  'Qualificação de repetibilidade</div>')
    partes.append("<h1>%s: %d de %d execuções concluídas, %s</h1>"
                  % (_e(identificador), concluidas, solicitadas,
                     "lote qualificado" if qualificado else "lote reprovado"))
    partes.append('<div class="rule"></div>')
    partes.append('<p class="sub">Veredito de um lote da fase R1, apurado '
                  'sobre o conjunto: equivalência de cada geração contra a '
                  'referência e independência conferida entre todos os pares. '
                  'Nenhum número desta página foi lido do produto durante a '
                  'geração do relatório — todos vêm dos artefatos das '
                  'execuções.</p>')
    partes.append('<div class="meta">')
    partes.append("<div><b>Qualificação</b><span>%s</span></div>"
                  % _e(identificador))
    partes.append("<div><b>Template profile</b><span class=\"small\">%s</span>"
                  "</div>" % _e(template_profile or "(não informado)"))
    partes.append("<div><b>Produto</b><span>%s</span></div>"
                  % _e(product_version or "(não informado)"))
    partes.append("<div><b>Emitido em</b><span>%s</span></div>"
                  % _e(generated_at))
    partes.append("<div><b>Natureza</b><span>Apuração offline sobre "
                  "artefatos</span></div>")
    partes.append("</div></div></header>")

    # --- toc ----------------------------------------------------------------
    partes.append('<nav class="toc"><div class="wrap">')
    for ancora, rotulo in secoes_toc:
        partes.append('<a href="#%s">%s</a>' % (ancora, _e(rotulo)))
    partes.append("</div></nav>")

    partes.append('<main class="wrap">')

    # --- 01 sumário ---------------------------------------------------------
    partes.append('<section id="s1"><h2><span class="n">01</span>Sumário '
                  "executivo</h2>")
    partes.append("<h3>%s &nbsp; %s</h3>"
                  % (("Lote qualificado" if qualificado
                      else "Lote reprovado"), veredito_chip))
    partes.append('<p class="lead">O veredito é do CONJUNTO. Uma execução '
                  "inconsistente reprova a qualificação mesmo que todas as "
                  "outras passem, e execuções equivalentes que não sejam "
                  "independentes não provam repetibilidade.</p>")
    partes.append('<div class="kpis k4">')
    partes.append('<div class="kpi"><div class="v">%d/%d</div><div class="l">'
                  "execuções concluídas sobre solicitadas</div></div>"
                  % (concluidas, solicitadas))
    partes.append('<div class="kpi blue"><div class="v">%d/%d</div>'
                  '<div class="l">gerações equivalentes à referência</div>'
                  "</div>" % (equivalentes, total_geracoes))
    partes.append('<div class="kpi %s"><div class="v">%d</div><div class="l">'
                  "violações de independência entre pares</div></div>"
                  % ("gray" if not violacoes else "", len(violacoes)))
    partes.append('<div class="kpi gray"><div class="v">%d</div>'
                  '<div class="l">piso normativo de execuções (R1)</div>'
                  "</div>" % piso)
    partes.append("</div>")
    partes.extend(caixas)
    partes.append("</section>")

    # --- 02 método ----------------------------------------------------------
    partes.append('<section id="s2"><h2><span class="n">02</span>Método</h2>')
    partes.append("<h3>Equivalência contra referência, independência entre "
                  "todos os pares</h3>")
    partes.append("<p>As duas relações têm naturezas opostas, e por isso são "
                  "apuradas de formas diferentes.</p>")
    partes.append('<ol class="steps">')
    partes.append("<li><b>Equivalência é igualdade de valor canônico</b>"
                  "<span>Textos persistidos, assinatura da árvore e diff "
                  "estrutural. Igualdade é transitiva: comparar cada geração "
                  "contra uma referência basta.</span></li>")
    partes.append("<li><b>Independência é anti-reflexiva e não transitiva</b>"
                  "<span>GUIDs distintos. A ≠ B e B ≠ C não implicam A ≠ C — "
                  "por isso a conferência é feita entre todos os pares, e não "
                  "só contra a referência.</span></li>")
    partes.append("<li><b>Volátil permitido é mostrado, não escondido</b>"
                  "<span>A lista de campos é literal. Estar nela dispensa de "
                  "reprovar, não de aparecer com todos os valores "
                  "observados.</span></li>")
    partes.append("</ol>")
    if problemas:
        partes.append('<div class="box warn"><div class="t">Problemas '
                      "registrados na apuração</div>%s</div>"
                      % _lista(problemas, ""))
    partes.append("</section>")

    # --- 03 execuções -------------------------------------------------------
    partes.append('<section id="s3"><h2><span class="n">03</span>Execuções'
                  "</h2>")
    partes.append("<h3>%d de %d gerações equivalentes à referência</h3>"
                  % (equivalentes, total_geracoes))
    partes.append('<div class="tw"><table>')
    partes.append("<caption>Cada linha é uma geração do lote. "
                  "<strong>Equivalente</strong> significa que as camadas "
                  "comparadas bateram — não que o projeto gerado esteja "
                  "correto, o que é outra pergunta, respondida pelo build e "
                  "pela verificação de cada execução. A referência não é "
                  "comparada consigo mesma: seria disparar a regra de GUIDs "
                  "distintos e produzir uma divergência sem significado."
                  "</caption>")
    partes.append("<thead><tr><th>Geração</th><th>Estado</th>"
                  "<th>Camadas comparadas</th><th>Detalhe</th></tr></thead>")
    partes.append("<tbody>%s</tbody>" % _tabela_execucoes(equivalencia))
    partes.append("</table></div>")
    partes.append("</section>")

    # --- 04 voláteis --------------------------------------------------------
    partes.append('<section id="s4"><h2><span class="n">04</span>Campos '
                  "voláteis</h2>")
    volateis = equivalencia.get("volatile_distribution") or []
    partes.append("<h3>%d campo(s) declarados voláteis, todos exibidos</h3>"
                  % len(volateis))
    if volateis:
        partes.append('<div class="tw"><table>')
        partes.append("<caption>Estes campos <strong>não</strong> reprovam o "
                      "lote — eles estão numa allowlist literal, campo a "
                      "campo. A tabela existe porque a allowlist decide o "
                      "veredito, não a visibilidade: um campo que alterna "
                      "entre poucos valores em muitas execuções é um achado "
                      "que o veredito binário esconderia.</caption>")
        partes.append('<thead><tr><th>Campo</th><th class="num">Valores '
                      'distintos</th><th class="num">Execuções</th>'
                      "<th>Leitura</th></tr></thead>")
        partes.append("<tbody>%s</tbody>" % _tabela_volateis(equivalencia))
        partes.append("</table></div>")
    else:
        partes.append("<p>Nenhum campo volátil foi observado nos artefatos "
                      "deste lote. Isso pode significar que os artefatos de "
                      "conclusão não estavam presentes — ausência de "
                      "observação não é ausência de variação.</p>")
    partes.append("</section>")

    # --- 05 limites ---------------------------------------------------------
    partes.append('<section id="s5"><h2><span class="n">05</span>Limites</h2>')
    partes.append("<h3>O que este lote estabelece, e o que continua exigindo "
                  "medição</h3>")
    partes.append('<div class="tw"><table>')
    partes.append("<caption>A coluna da esquerda é o que os artefatos "
                  "sustentam. A da direita é o que continua sem evidência "
                  "depois deste lote — e nenhuma linha da esquerda autoriza "
                  "uma conclusão da direita.</caption>")
    partes.append("<thead><tr><th>A evidência estabelece</th>"
                  "<th>Continua exigindo medição</th></tr></thead><tbody>")
    partes.append("<tr><td>Que %d execuções produziram artefatos comparáveis "
                  "e equivalentes entre si.</td><td>Que a operação é "
                  "repetível: a fase exige %d execuções independentes, e "
                  "%s.</td></tr>"
                  % (equivalentes, piso,
                     "esse número foi atingido" if concluidas >= piso
                     else "esse número não foi atingido"))
    partes.append("<tr><td>Que as gerações comparadas não compartilham GUIDs "
                  "de objeto.</td><td>Que o projeto gerado funciona no CLP. "
                  "Nada aqui mede ciclo, tempo de varredura ou comportamento "
                  "em runtime — isso está fora do escopo do produto.</td>"
                  "</tr>")
    partes.append("<tr><td>Que os artefatos exigidos estavam presentes em "
                  "cada execução concluída.</td><td>Que o mesmo vale em outra "
                  "instalação, outra máquina ou outra versão do MasterTool. "
                  "Capacidade provada numa versão não se presume provada em "
                  "outra.</td></tr>")
    partes.append("</tbody></table></div>")
    partes.append('<div class="box info"><div class="t">Sobre este '
                  "documento</div><p>Gerado offline a partir dos artefatos do "
                  "lote, sem abrir o MasterTool. O gerador é determinístico: "
                  "a mesma entrada produz o mesmo arquivo, e a hora de emissão "
                  "entra como dado em vez de ser lida do relógio, para que "
                  "dois relatórios do mesmo lote sejam comparáveis byte a "
                  "byte.</p></div>")
    partes.append("</section>")

    partes.append("</main>")

    # --- rodapé -------------------------------------------------------------
    partes.append('<footer><div class="wrap">')
    partes.append(logo_rodape)
    partes.append('<div class="cols">')
    partes.append("<div><b>Documento</b>Qualificação de repetibilidade — %s"
                  "<br>Emitido em %s</div>" % (_e(identificador),
                                               _e(generated_at)))
    partes.append("<div><b>Natureza da apuração</b>Offline, sobre artefatos "
                  "de execução. Nenhuma leitura do produto durante a "
                  "geração.</div>")
    partes.append("<div><b>Rankine Systems Ltda.</b>"
                  '<a href="https://rankinesystems.com.br">'
                  "rankinesystems.com.br</a></div>")
    partes.append("</div></div></footer>")
    partes.append("</body></html>")

    return "\n".join(partes) + "\n"
