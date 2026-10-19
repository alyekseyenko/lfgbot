from __future__ import annotations

GUIDE_EMBED_TITLE = "Guia — LFG Valorant"
GUIDE_BODY_MAX_LEN = 3900

# Texto por defeito do canal de guia (editável no dashboard → Geral).
DEFAULT_GUIDE_BODY = """**Modos**
• **Simples** — código no canal; entras no jogo pelo código.
  Sem **Entrar** / **Sair** no Discord. Fecha com **`/fechar`** (o botão Fechar
  pode estar escondido).
• **Detalhado** — lista no Discord com **Entrar** / **Sair**.

Sair ou ser removido de um pedido **não** te expulsa do servidor.

**Criar pedido**
• Painel **Criar grupo** → só **simples** (vagas + código → Publicar).
• **Detalhado** só com **`/procurar`** (escolhe tipo Detalhado): ranks validados,
  agentes, código público/privado, lista, Entrar/Sair.
• **`/procurar`** também cria simples. O modo (Comp/Unrated) segue o canal.

**Fechar o grupo**
• **`/fechar`** — o host fecha o pedido ativo (funciona mesmo sem o botão Fechar).
• Se o tempo (TTL) já passou e o grupo ainda não fechou, **`/fechar`** continua a dar.
• Pedidos **expiram sozinhos** se ninguém os fechar.
• **`/editar`** (ou o botão **Editar**, se estiver visível).

**No pedido simples**
• Host, vagas, código (e ranks no embed, se definiste).
• Roles de prioridade podem dar **destaque** (cor/título).

**No pedido detalhado**
• **Entrar** / **Sair** · código **privado** por DM após entrar.
• Host pode **remover** alguém (não é ban do servidor).

**Esperas** (fuso Lisboa; valores podem mudar)
• **Depois de fechar** o teu pedido: ~**5 min** para criar outro, ou **segundos** com role
  de prioridade (Membro/VIP, etc.). Conta a role que tens **ao fechar** — ganhar prioridade
  depois não cancela a espera em curso.
• **Sair** de pedido com código **privado** (por ti): bloqueio temporário a criar/entrar.
  **Expulsão pelo host não conta.**

**Ranks**
Detalhado: o bot valida pelas roles mapeadas no dashboard.
Simples: ranks no embed são para quem lê o canal.

**Perfil e ranking** (se a gamificação estiver ativa)
• **`/perfil`** — nível de **criador** conforme os grupos que publicaste (histórico completo).
• **`/ranking`** — top de **grupos criados** neste servidor, sem limite de tempo.

**Mais**
• **`/lfg-apagar-dados`** (RGPD).

**Chat `ABC123 +2`**
Desligado — usa o painel ou **`/procurar`**."""


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
