# Determinismo de W1.4 — medição

> Registro de execução. `run-022` a `run-025`, comparadas contra `run-019`.
> Fecha a lacuna nomeada na seção Limites de `docs/37` e `docs/39` — *"a
> operação não foi repetida sobre cópias novas"* — e listada em `docs/38` como
> pendência do contrato. A fase `W1_4_INTEGRATED_BUILD` foi **reaberta** para
> isto, com a **mesma** allowlist.

## 1. Veredito

### A mesma especificação produz o mesmo projeto — e nunca o mesmo arquivo

Cinco gerações da mesma especificação, cada uma sobre uma cópia nova do mesmo
template, produziram **cinco arquivos de bytes distintos** e **um único
projeto**. Os dez pares possíveis são equivalentes nas três camadas de
conteúdo, sem nenhuma divergência.

A distinção não é sutil: quem comparar `.project` por hash vai concluir que a
fábrica não é determinista, e vai estar olhando para GUID de objeto e
timestamp — sorteados a cada gravação, sem significado de engenharia.

## 2. Números medidos

| Grandeza | Valor |
| --- | --- |
| Gerações | **5** (`run-019`, `022`, `023`, `024`, `025`) |
| Base de todas | `TemplateExemplo_v1.project`, `59662579…d1815f5` |
| Pares comparados | **10** |
| Pares equivalentes | **10** — zero divergências |
| Hashes `.project` distintos | **5 de 5** |
| GUIDs de objeto que diferem, por par | **4** |
| Nós na árvore persistida | **44** em todas |
| Linhas de compilador | **5**, idênticas em todas |
| Status do build | `build_verified` em todas |

<caption>

**Como ler:** "5 hashes distintos" e "10 pares equivalentes" nas mesmas linhas
não se contradizem — é exatamente o resultado. Se os hashes fossem iguais, a
comparação estaria olhando o mesmo arquivo duas vezes e não provaria nada; é
por isso que a divergência dos GUIDs entra como **contraprova** e não como
defeito.

</caption>

## 3. O critério, e por que não é o arquivo

O `.project` inteiro reprovaria **sempre**. Um critério que reprova sempre não
distingue projeto igual de projeto diferente — não mede nada, apenas parece
rigoroso.

O critério é o conteúdo, em três camadas independentes, e divergência em
qualquer uma reprova:

| # | Camada | O que compara |
| --- | --- | --- |
| 1 | Texto **relido do disco** (`postsave`) | SHA-256 das três declarações |
| 2 | Árvore persistida | posição, nome e tipo dos 44 nós |
| 3 | Diff estrutural | cada geração contra o **próprio** preflight |

<caption>

**Como ler:** a camada 1 lê do disco, e não da memória de quem escreveu.
Comparar a memória do autor com a memória do autor provaria apenas que a
variável não mudou entre duas linhas.

</caption>

## 4. Duas armadilhas que o comparador fecha

### Um comparador que passa à toa é pior que comparador nenhum

**Assinatura vazia.** A primeira versão montava a assinatura da árvore com o
campo `route`, que o artefato não tem. As 44 posições casaram como `None`, e o
comparador disse "determinista". Eu escrevi o defeito e ele passou. Os campos
passaram a ser verificados como presentes, e a ausência **reprova** — porque um
falso "igual" parece evidência.

**Gerações não independentes.** Se os `object_guid` das duas árvores forem
idênticos, os artefatos vieram da mesma execução, e a igualdade é tautologia
sobre um arquivo e ele mesmo. O comparador exige que ao menos um GUID difira.

## 5. Dois defeitos de evidência que as execuções expuseram

### O melhor desfecho era relatado como o pior

`Wait-Process -Id` lança em dois casos **opostos** — processo ainda vivo depois
do timeout, e processo que já encerrou. Os dez wrappers tratavam os dois como o
primeiro. Na `run-022`, o probe terminou sozinho por `system.exit(0)` e o host
anunciou *"[TIMEOUT] A janela não fechou. Provavelmente há um diálogo aberto"*
sobre um processo que não existia mais.

Esse aviso é o **único** canal que diz ao operador que há um diálogo modal
esperando por ele. Um aviso que dispara no caso limpo ensina o leitor a
ignorá-lo — justamente para que não seja lido na vez em que for verdadeiro.

A correção é de **pergunta**, não de tipo de exceção: "a janela fechou?" é sobre
o processo (`HasExited`); o `catch` responde se o cmdlet reclamou.

### O instrumento estava medindo a si mesmo

`print` num script do MasterTool não vai para stdout: vai para o *message store*
do produto. O banner do probe 40 caía na **mesma** coleção de onde saem as
mensagens do compilador. A `run-023` mediu `message_count: 8`, das quais **três
eram o próprio probe se lendo**.

A direção do erro era segura — mensagem a mais só poderia reprovar à toa. Mas a
classificação é por substring: bastaria o probe imprimir uma linha com a palavra
"erro" para o build ser reprovado pelo texto do próprio probe.

Agora há linha de base antes do build, por **multiconjunto**. Descontar não é
apagar: as oito continuam gravadas, marcadas com `pre_existing`, e as duas
contagens aparecem lado a lado — *"mensagens do build: 5 (total no armazém: 8;
pré-existentes: 3)"*.

### O próprio desconto abriu um buraco, fechado no mesmo commit

Com tudo filtrado, a lista fica vazia — e vazia lia como `build_verified`.
Silêncio virando sucesso. Novo status `no_build_messages`, que bloqueia
promoção.

**Zero mensagem não é aprovação, e isso é medido:** as cinco gerações emitiram
as mesmas cinco linhas. Este compilador sempre fala.

## 6. A fase foi reaberta, e não criada

Reabrir saiu barato **precisamente porque encerrar nunca apagou a allowlist** —
ela ficou no mapa como registro. Se o fechamento tivesse removido a entrada,
medir determinismo exigiria reescrever a autorização, e a segunda execução não
seria comparável com a primeira: a especificação autorizada teria mudado entre
as duas.

Nada mudou na allowlist. Se algo precisasse mudar, não seria a mesma fase.

## 7. Limites

**O que a evidência comprova:** que cinco execuções da mesma especificação,
sobre cópias novas do mesmo template, na mesma máquina, com a mesma instalação
`4.1.0.11`, produzem projetos de conteúdo idêntico nas três camadas medidas, e
que os arquivos resultantes nunca são iguais byte a byte.

**O que NÃO está comprovado:**

- **Determinismo entre máquinas ou instalações.** Todas as cinco rodaram na
  mesma máquina, com a mesma versão. Outra instalação é outra medição.
- **Determinismo de outras especificações.** O que se repetiu foi *esta* cadeia
  — GVL, PROGRAM, três textos, `save_as`, `build`. FB, FUNCTION e DUT não
  entraram em geração alguma.
- **Determinismo do vínculo de W2.** `add` na lista da task não foi repetido.
- **Que o conteúdo idêntico implica comportamento idêntico no CLP.** Download e
  online seguem permanentemente proibidos; a afirmação máxima honesta continua
  sendo *"o projeto declara"*.
- **Que os GUIDs de objeto são irrelevantes para o produto.** Eles foram
  excluídos da comparação por serem sorteados — não por medição de que nada os
  consome.

## 8. Estado

`W1_4_INTEGRATED_BUILD` foi **encerrada de novo**, em commit próprio.
`CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.
