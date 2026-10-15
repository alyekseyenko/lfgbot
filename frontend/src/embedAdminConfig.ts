export type AdminSection =
  | "geral"
  | "embeds"
  | "mapeamentos"
  | "catalogo"
  | "moderacao"
  | "metricas";

export type EmbedTab = "painel" | "pedidos" | "destaque";

export type EmbedPedidosTab = "cores" | "textos" | "midia";

export const ADMIN_SECTIONS: { id: AdminSection; label: string; hint: string }[] = [
  { id: "geral", label: "Geral", hint: "Canais, opções e auditoria" },
  { id: "embeds", label: "Embeds LFG", hint: "Cores, textos e multimédia" },
  { id: "mapeamentos", label: "Mapeamentos", hint: "Ranks e roles Valorant" },
  { id: "catalogo", label: "Catálogo", hint: "Sincronização Valorant API" },
  { id: "moderacao", label: "Moderação", hint: "Penalizações e roles isentas" },
  { id: "metricas", label: "Métricas", hint: "Estatísticas do servidor" },
];

export const EMBED_TABS: { id: EmbedTab; label: string; hint: string }[] = [
  {
    id: "painel",
    label: "Painel «Criar grupo»",
    hint: "Mensagem fixa no canal com o botão",
  },
  {
    id: "pedidos",
    label: "Pedidos publicados",
    hint: "Embed quando alguém publica um grupo",
  },
  { id: "destaque", label: "Destaque VIP", hint: "Hosts com roles isentas" },
];

export const EMBED_PEDIDOS_TABS: { id: EmbedPedidosTab; label: string }[] = [
  { id: "cores", label: "Cores" },
  { id: "textos", label: "Textos" },
  { id: "midia", label: "Multimédia" },
];

/** Corpo fixo do painel (entre lead e CTA) quando não há descrição custom completa. */
export const PANEL_EMBED_BODY =
  "Clica em **Criar grupo**.\n\n" +
  "**1.** Vagas e código da party (o essencial)\n" +
  "**2.** Ranks opcionais em dropdown (mín. / máx., como as roles)\n" +
  "**3.** **Publicar** — o pedido fica neste canal com Entrar / Sair\n\n" +
  "O formulário é só para ti; o grupo é público.\n" +
  "Ainda podes escrever no chat (`ABC123 +2`) ou usar `/procurar` para mais opções.";

/** Valores por omissão (alinhados com o bot). */
export const LFG_EMBED_TEXT_DEFAULTS: Record<string, string> = {
  panel_title: "🎯 LFG — Criar grupo",
  panel_lead: "**Procura team? Publica aqui em segundos.**",
  panel_cta: "▸ Clica em **Criar grupo** para começar.",
  lobby_cta_open: "👇 **Usa os botões abaixo** para entrar ou sair.",
  lobby_inactive_lead: "**Este grupo já não está ativo.**",
  lobby_empty_players: "_Ninguém na lista — **Entrar** para te juntares._",
  lobby_private_code_hint: "_Oculto — carrega em **Entrar** para receber o código._",
  author_prefix: "Host",
  footer_suffix: "· Expira à hora indicada (Lisboa)",
  field_slots: "Vagas",
  field_expires: "Expira",
  field_code_visibility: "Código",
  field_ranks: "Ranks",
  field_agents: "Roles procurados",
  field_players: "Jogadores",
  field_party_code: "Código da party",
};

export function defaultPanelDescription(): string {
  return `${LFG_EMBED_TEXT_DEFAULTS.panel_lead}\n\n${PANEL_EMBED_BODY}\n\n${LFG_EMBED_TEXT_DEFAULTS.panel_cta}`;
}

export function defaultEmbedText(key: string): string {
  if (key === "panel_description") {
    return defaultPanelDescription();
  }
  return LFG_EMBED_TEXT_DEFAULTS[key] ?? "";
}

export function effectivePanelDescription(custom: Record<string, string>): string {
  const full = custom.panel_description?.trim();
  if (full) {
    return full;
  }
  const lead = custom.panel_lead?.trim() || LFG_EMBED_TEXT_DEFAULTS.panel_lead;
  const cta = custom.panel_cta?.trim() || LFG_EMBED_TEXT_DEFAULTS.panel_cta;
  return `${lead}\n\n${PANEL_EMBED_BODY}\n\n${cta}`;
}

export function effectiveEmbedText(custom: Record<string, string>, key: string): string {
  if (key === "panel_description") {
    return effectivePanelDescription(custom);
  }
  const stored = custom[key]?.trim();
  if (stored) {
    return stored;
  }
  return defaultEmbedText(key);
}

export function isEmbedTextCustomized(custom: Record<string, string>, key: string): boolean {
  if (key === "panel_description") {
    return Boolean(custom.panel_description?.trim());
  }
  return Boolean(custom[key]?.trim());
}

export type EmbedTextFieldDef = {
  key: string;
  label: string;
  max: number;
  multiline?: boolean;
  group: "painel" | "pedido" | "campos";
  hint?: string;
};

export const EMBED_TEXT_SECTIONS: {
  id: EmbedTextFieldDef["group"];
  title: string;
  intro: string;
}[] = [
  {
    id: "painel",
    title: "Painel «Criar grupo» no canal",
    intro:
      "Mensagem fixa com o botão de criar pedido. «Descrição completa» substitui lead + passos + CTA de uma vez.",
  },
  {
    id: "pedido",
    title: "Pedidos publicados",
    intro: "Frases que aparecem nos embeds quando alguém cria um grupo.",
  },
  {
    id: "campos",
    title: "Títulos dos campos",
    intro:
      "Nomes das colunas no embed (vagas, expira, etc.). Com estilo chamativo, o bot pode acrescentar emojis se deixares estes títulos simples.",
  },
];

export const EMBED_TEXT_FIELDS: EmbedTextFieldDef[] = [
  {
    key: "panel_title",
    label: "Título",
    max: 256,
    group: "painel",
    hint: "Barra superior do embed do painel.",
  },
  {
    key: "panel_description",
    label: "Descrição completa (opcional)",
    max: 4096,
    multiline: true,
    group: "painel",
    hint: "Se editares isto, ignoramos lead, passos e CTA separados.",
  },
  {
    key: "panel_lead",
    label: "Frase de abertura",
    max: 512,
    multiline: true,
    group: "painel",
    hint: "Só usada quando a descrição completa está vazia ou reposta ao padrão composto.",
  },
  {
    key: "panel_cta",
    label: "Chamada no final",
    max: 512,
    multiline: true,
    group: "painel",
  },
  {
    key: "lobby_cta_open",
    label: "Convite a usar os botões (pedido aberto)",
    max: 1024,
    multiline: true,
    group: "pedido",
  },
  {
    key: "lobby_inactive_lead",
    label: "Grupo fechado ou expirado",
    max: 512,
    multiline: true,
    group: "pedido",
  },
  {
    key: "lobby_empty_players",
    label: "Sem jogadores na lista",
    max: 1024,
    multiline: true,
    group: "pedido",
  },
  {
    key: "lobby_private_code_hint",
    label: "Código de party privado",
    max: 1024,
    multiline: true,
    group: "pedido",
  },
  {
    key: "author_prefix",
    label: "Prefixo do host",
    max: 32,
    group: "pedido",
    hint: "Aparece como «Prefixo · NomeDoHost».",
  },
  {
    key: "footer_suffix",
    label: "Sufixo do rodapé",
    max: 128,
    group: "pedido",
    hint: "Depois da marca e do ID curto do pedido.",
  },
  {
    key: "field_slots",
    label: "Vagas",
    max: 256,
    group: "campos",
  },
  {
    key: "field_expires",
    label: "Expira",
    max: 256,
    group: "campos",
  },
  {
    key: "field_code_visibility",
    label: "Visibilidade do código",
    max: 256,
    group: "campos",
  },
  {
    key: "field_ranks",
    label: "Ranks",
    max: 256,
    group: "campos",
  },
  {
    key: "field_agents",
    label: "Roles procurados",
    max: 256,
    group: "campos",
  },
  {
    key: "field_players",
    label: "Jogadores",
    max: 256,
    group: "campos",
  },
  {
    key: "field_party_code",
    label: "Código da party",
    max: 256,
    group: "campos",
  },
];
