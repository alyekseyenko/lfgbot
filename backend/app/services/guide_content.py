from __future__ import annotations

GUIDE_EMBED_TITLE = "Guia — LFG Valorant"
GUIDE_BODY_MAX_LEN = 3900

# Texto por defeito do canal de guia (editável no dashboard → Geral).
DEFAULT_GUIDE_BODY = """**O essencial**
**Simples:** publica o **código** no canal — entras no jogo e convidas pelo código (só o host usa **Fechar**).
**Detalhado:** lista no Discord com **Entrar** / **Sair** (como antes).
Sair ou ser **removido do pedido** não te expulsa do Discord — só sais desse grupo.

━━━━━━━━━━━━━━━━━━━━
**Criar pedido — painel (recomendado)**
1. **Criar grupo** → **Simples** (padrão) ou **Detalhado**.
2. **Simples:** vagas + código → **Publicar já** (qualquer rank) ou escolhe ranks mín./máx.
3. **Detalhado:** ranks, agentes, código público/privado, etc.
O formulário é só para ti; o pedido fica visível no canal.

**Criar pedido — `/procurar`**
Por defeito é **simples** (`vagas` + `codigo`). Para **Entrar**/**Sair** no Discord, usa `tipo: Detalhado` e as opções extra (ranks verificados, código privado, agentes). O modo (Competitivo / Unrated) segue o canal.

━━━━━━━━━━━━━━━━━━━━
**Nos pedidos (botões)**
• **Entrar** / **Sair** — gerir a tua presença na lista.
• Código **privado** — depois de **Entrar**, o bot pode enviar-te o código por mensagem.
• O **host** pode **expulsar** alguém do pedido (botão do host) — não é ban do servidor.
• Pedidos **expiram** sozinhos (tempo máximo definido pela staff).
• **`/fechar`** — o host fecha o pedido ativo.
• **`/editar`** — alterar vagas, ranks, código, visibilidade ou agentes (com pedido aberto).

━━━━━━━━━━━━━━━━━━━━
**Tempos de espera (anti-abuso)**
Contam no **fuso de Lisboa**; reinício diário onde aplicável.

**Party com código privado**
Se **saíres voluntariamente** (botão **Sair**) de um pedido com código **privado**, ficás **temporariamente sem poder** criar ou entrar em novos pedidos. **Ser expulso pelo host não conta** para esta penalização.
• 1.ª–3.ª saída do dia → cerca de **5 min** sem novo pedido/entrada.
• 4.ª saída → cerca de **15 min**.
• 5.ª e seguintes no mesmo dia → cerca de **12 h**.
(Os moderadores podem alterar estes valores; o bot diz **até quando** estás bloqueado.)

**Depois de fechar o teu pedido (`/fechar` ou grupo cheio/fechado)**
Espera habitual para **criar outro pedido**: cerca de **5 min** (resto dos membros). Com roles como **Membro**, **Confiança** ou outros níveis de destaque → espera **muito menor** (segundos) e o teu pedido pode sair em **destaque** no canal (cor/título diferentes).

━━━━━━━━━━━━━━━━━━━━
**Roles da comunidade**
• **Membro / Confiança / VIP** (nomes conforme o servidor) — menos espera ao fechar pedidos, embed em **destaque** quando publicas, e benefícios de moderação automática ligados a essas roles.
• **Ranks verificados** — com `/procurar` ou painel, o bot valida rank pelas roles Discord mapeadas; entra só quem cumpre o intervalo pedido.

**Gamificação** (se estiver ativa)
• **`/perfil`** — nível, grupos completos, **expulsões recebidas** no LFG.
• **`/ranking`** — leaderboard semanal.

**Privacidade**
• **`/lfg-apagar-dados`** — pedir remoção dos teus dados LFG (RGPD).

━━━━━━━━━━━━━━━━━━━━
**Chat `ABC123 +2`**
Por agora **não está ativo** — usa o painel **Criar grupo** ou **`/procurar`**."""


def normalize_guide_body(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    return text[:GUIDE_BODY_MAX_LEN]


def effective_guide_body(stored: str | None) -> str:
    custom = normalize_guide_body(stored)
    if custom:
        return custom
    return DEFAULT_GUIDE_BODY
