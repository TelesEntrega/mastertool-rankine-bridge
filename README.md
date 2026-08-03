# mastertool-rankine-bridge

Núcleo da ponte entre o **MasterTool** (Altus — IEC XE 3.63/3.70 e MasterTool X /
MT9000 4.1.0.11) e Python 3.

Este repositório contém a **biblioteca**: leitura e validação de export,
indexação IEC 61131-3, análise estática, o *planner* offline de autoria, o
modelo de segurança em fases, o pacote de evidência e o comparador de gerações.
Tudo offline e determinístico, com fixture sintética.

## O que este repositório NÃO contém, e por quê

Duas coisas ficam na árvore interna, de propósito:

- **Os instrumentos de campo** — os probes IronPython 2.7 que rodam *dentro* do
  MasterTool e os wrappers PowerShell que os lançam. Cada um carrega o caminho
  de instalação de uma máquina e o nome do projeto contra o qual foi exercido.
- **Os registros de execução** — a documentação que descreve, passo a passo, as
  sessões supervisionadas contra o produto real. Eles existem e são datados,
  mas descrevem por definição os programas usados como teste: hash, árvore de
  projeto, nome de objeto.

**Consequência que precisa ser dita:** o que está aqui é o **mecanismo, sem a
evidência de campo**. As capacidades de autoria descritas no código foram
medidas em execuções reais contra o MasterTool X, com build limpo e verificação
por reabertura independente — mas esses registros não estão publicados, e
portanto **não são verificáveis a partir deste repositório**. Quem precisar
auditá-los precisa da árvore interna.

Nada aqui promove maturidade de capacidade. Promoção acima de `discovered`
exige execução real do produto com operador humano presente — isso é sessão de
campo, nunca CI.

## O que dá para fazer com o que está aqui

```bash
pip install -e .
pytest

mastertool-bridge --help
```

A CLI cobre validação de export, indexação, análise, documentação, comparação
de projetos, verificação de alteração inesperada, empacotamento de evidência e
emissão de spec de reversão. Os comandos que **executam** algo contra o produto
não estão aqui: eles vivem nos wrappers da árvore interna.

## Segurança

O modelo é de fases com allowlist literal e fechada
(`scripts/mastertool/common/safety.py`). Fora de uma fase aberta, toda operação
mutante é recusada. Operações online — download para controlador, force,
atuação sobre equipamento — são proibidas incondicionalmente, sem fase e sem
allowlist que as alcance.

Este software opera sobre artefatos de projeto de sistemas de controle
industrial. Ele não executa operação online, não realiza download para
controlador, não atua sobre equipamento físico e não certifica função de
segurança. Toda alteração que ele proponha ou gere exige revisão e aprovação de
engenheiro responsável antes de qualquer uso em planta.

## Licença

Ver [`LICENSE`](LICENSE).
