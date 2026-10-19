export type AdminSection =
  | "geral"
  | "embeds"
  | "mapeamentos"
  | "niveis"
  | "catalogo"
  | "moderacao"
  | "metricas";

export type EmbedTab = "painel" | "pedidos" | "destaque";

export type EmbedPedidosTab = "cores" | "textos" | "midia" | "visibilidade";

export type EmbedPedidosMode = "simples" | "detalhado";

export const EMBED_PEDIDOS_MODE_TABS: {
  id: EmbedPedidosMode;
  label: string;
  hint: string;
}[] = [
  {
    id: "simples",
    label: "Modo simples",
    hint: "Código, vagas, rank — fecha com /fechar",
  },
  {
    id: "detalhado",
    label: "Modo detalhado",
    hint: "Entrar/Sair, agentes, lista de jogadores",
  },
];

export type LfgEmbedSimpleSettings = {
  color_source?: "mode" | "host_rank" | "min_rank" | "max_rank";
  competitive_color?: string;
  unrated_color?: string;
  inactive_color?: string;
  decorative?: boolean;
  footer_brand?: string | null;
  custom_texts?: Record<string, string>;
  show_author?: boolean;
  show_timestamp?: boolean;
  show_rank_thumbnail?: boolean;
  lobby_thumbnail_url?: string | null;
  show_title?: boolean;
  show_hint?: boolean;
  show_host_line?: boolean;
  host_as_mention?: boolean;
  show_party_code?: boolean;
  show_slots?: boolean;
  show_rank?: boolean;
  show_expires?: boolean;
  show_footer?: boolean;
  show_footer_rank_hint?: boolean;
  show_close_button?: boolean;
  show_edit_button?: boolean;
};

export type LfgEmbedPanelSettings = {
  show_title?: boolean;
  show_lead?: boolean;
  show_body?: boolean;
  show_cta?: boolean;
  show_guide?: boolean;
  show_footer?: boolean;
  show_thumbnail?: boolean;
  show_banner?: boolean;
};

export const EMBED_VISIBILITY_PANEL: { key: keyof LfgEmbedPanelSettings; label: string }[] = [
  { key: "show_title", label: "Título" },
  { key: "show_lead", label: "Texto curto no topo (lead)" },
  { key: "show_body", label: "Texto principal / descrição" },
  { key: "show_cta", label: "Texto extra no fundo (CTA)" },
  { key: "show_guide", label: "Linha do canal do guia" },
  { key: "show_footer", label: "Rodapé" },
  { key: "show_thumbnail", label: "Miniatura (imagem à direita)" },
  { key: "show_banner", label: "Banner (imagem grande)" },
];

export const DEFAULT_LFG_EMBED_PANEL_VISIBILITY: Record<keyof LfgEmbedPanelSettings, boolean> = {
  show_title: true,
  show_lead: true,
  show_body: true,
  show_cta: true,
  show_guide: true,
  show_footer: true,
  show_thumbnail: true,
  show_banner: true,
};

export const LFG_EMBED_PANEL_MINIMAL: Partial<LfgEmbedPanelSettings> = {
  show_title: true,
  show_lead: false,
  show_body: false,
  show_cta: false,
  show_guide: false,
  show_footer: false,
  show_thumbnail: false,
  show_banner: false,
};

export type LfgEmbedDetailedSettings = {
  show_title?: boolean;
  show_host_line?: boolean;
  host_as_mention?: boolean;
  show_party_code?: boolean;
  show_slots?: boolean;
  show_rank?: boolean;
  show_expires?: boolean;
  show_footer?: boolean;
  show_footer_rank_hint?: boolean;
  show_cta?: boolean;
  show_code_visibility?: boolean;
  show_agents?: boolean;
  show_players?: boolean;
  show_banner_image?: boolean;
  show_host_rank_tags?: boolean;
};

export const EMBED_VISIBILITY_SIMPLE: { key: keyof LfgEmbedSimpleSettings; label: string }[] =
  [
    { key: "show_title", label: "Título (modo / VIP)" },
    { key: "show_hint", label: "Texto de ajuda sob o host" },
    {
      key: "show_host_line",
      label: "Linha «Criado por @nome» na descrição",
    },
    {
      key: "host_as_mention",
      label:
        "Host clicável (@menção no texto acima do embed — o Discord não clica dentro do embed)",
    },
    { key: "show_party_code", label: "Campo código da party (bloco para copiar)" },
    { key: "show_slots", label: "Campo vagas" },
    { key: "show_rank", label: "Campo rank" },
    { key: "show_expires", label: "Campo expira" },
    { key: "show_footer", label: "Rodapé (marca, ID, expira)" },
    { key: "show_footer_rank_hint", label: "Nota «sem rank verificado» no rodapé" },
    {
      key: "show_close_button",
      label: "Botão Fechar no pedido ( /fechar continua sempre )",
    },
    {
      key: "show_edit_button",
      label: "Botão Editar no pedido ( /editar continua sempre )",
    },
    { key: "show_author", label: "Cabeçalho «Host · nome»" },
    { key: "show_timestamp", label: "Data/hora no embed" },
    { key: "show_rank_thumbnail", label: "Miniatura de rank / VIP" },
  ];

export const EMBED_VISIBILITY_DETAILED: {
  key: keyof LfgEmbedDetailedSettings;
  label: string;
}[] = [
  { key: "show_title", label: "Título (modo · estado / VIP)" },
  { key: "show_host_line", label: "Linha «Criado por @nome» na descrição" },
  {
    key: "host_as_mention",
    label: "Host clicável (@menção no texto acima do embed)",
  },
  { key: "show_cta", label: "Texto «Usa os botões abaixo»" },
  { key: "show_party_code", label: "Código da party" },
  { key: "show_slots", label: "Vagas (barra ou número)" },
  { key: "show_rank", label: "Ranks" },
  { key: "show_expires", label: "Expira" },
  { key: "show_code_visibility", label: "Campo público/privado" },
  { key: "show_agents", label: "Agentes procurados" },
  { key: "show_players", label: "Lista de jogadores" },
  { key: "show_footer", label: "Rodapé" },
  { key: "show_footer_rank_hint", label: "Nota rank no rodapé" },
  { key: "show_banner_image", label: "Imagem banner no pedido" },
  { key: "show_host_rank_tags", label: "Tags de rank do host na linha" },
];

/** Mirrors backend `LfgEmbedSimpleSettings` / `normalize_lfg_embed_simple` defaults. */
export const DEFAULT_LFG_EMBED_SIMPLE_VISIBILITY: Record<
  keyof Pick<
    LfgEmbedSimpleSettings,
    | "show_title"
    | "show_hint"
    | "show_host_line"
    | "host_as_mention"
    | "show_party_code"
    | "show_slots"
    | "show_rank"
    | "show_expires"
    | "show_footer"
    | "show_footer_rank_hint"
    | "show_close_button"
    | "show_edit_button"
    | "show_author"
    | "show_timestamp"
    | "show_rank_thumbnail"
  >,
  boolean
> = {
  show_title: true,
  show_hint: true,
  show_host_line: true,
  host_as_mention: false,
  show_party_code: true,
  show_slots: true,
  show_rank: true,
  show_expires: true,
  show_footer: true,
  show_footer_rank_hint: true,
  show_close_button: true,
  show_edit_button: true,
  show_author: false,
  show_timestamp: false,
  show_rank_thumbnail: true,
};

/** Mirrors backend `LfgEmbedDetailedSettings` defaults. */
export const DEFAULT_LFG_EMBED_DETAILED_VISIBILITY: Record<
  keyof LfgEmbedDetailedSettings,
  boolean
> = {
  show_title: true,
  show_host_line: true,
  host_as_mention: false,
  show_party_code: true,
  show_slots: true,
  show_rank: true,
  show_expires: true,
  show_footer: true,
  show_footer_rank_hint: true,
  show_cta: true,
  show_code_visibility: true,
  show_agents: true,
  show_players: true,
  show_banner_image: true,
  show_host_rank_tags: true,
};

export const LFG_EMBED_SIMPLE_MINIMAL: Partial<LfgEmbedSimpleSettings> = {
  show_title: false,
  show_hint: false,
  show_host_line: true,
  host_as_mention: true,
  show_party_code: true,
  show_slots: true,
  show_rank: true,
  show_expires: false,
  show_footer: false,
  show_footer_rank_hint: false,
  show_close_button: false,
  show_edit_button: false,
  show_author: false,
  show_timestamp: false,
  show_rank_thumbnail: false,
  decorative: false,
};

const SIMPLE_EMBED_TEXT_KEYS = new Set([
  "lobby_inactive_lead",
  "lobby_simple_hint",
  "author_prefix",
  "host_line_prefix",
  "footer_suffix",
  "field_slots",
  "field_expires",
  "field_ranks",
  "field_party_code",
]);

export const ADMIN_SECTIONS: { id: AdminSection; label: string; hint: string }[] = [
  { id: "geral", label: "Geral", hint: "Canais, opções e auditoria" },
  { id: "embeds", label: "Embeds LFG", hint: "Cores, textos e multimédia" },
  { id: "mapeamentos", label: "Mapeamentos", hint: "Ranks e roles Valorant" },
  { id: "niveis", label: "Níveis criador", hint: "Grupos criados e roles (estrutura)" },
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
  { id: "visibilidade", label: "Visibilidade" },
  { id: "cores", label: "Cores" },
  { id: "textos", label: "Textos" },
  { id: "midia", label: "Multimédia" },
];

/** Corpo fixo do painel (entre lead e CTA) quando não há descrição custom completa. */
export const PANEL_EMBED_BODY =
  "**Criar grupo** → vagas + código → **Publicar**.";

/** Valores por omissão (alinhados com o bot). */
export const LFG_EMBED_TEXT_DEFAULTS: Record<string, string> = {
  panel_title: "🎯 LFG — Criar grupo",
  panel_lead: "**Procura team?**",
  panel_cta: "",
  lobby_cta_open: "👇 **Usa os botões abaixo** para entrar ou sair.",
  lobby_inactive_lead: "**Este grupo já não está ativo.**",
  lobby_empty_players: "_Ninguém na lista — **Entrar** para te juntares._",
  lobby_private_code_hint: "_Oculto — carrega em **Entrar** para receber o código._",
  lobby_simple_hint: "Junta-te no jogo com o código.",
  author_prefix: "Host",
  host_line_prefix: "Criado por",
  footer_suffix: "· Expira à hora indicada (Lisboa)",
  field_slots: "Vagas",
  field_expires: "Expira",
  field_code_visibility: "Código",
  field_ranks: "Ranks",
  field_agents: "Roles procurados",
  field_players: "Jogadores",
  field_party_code: "🔑 Código",
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
    intro:
      "Frases nos pedidos. A linha do host fica «Criado por @nome»; o código da party é o campo de baixo (bloco copiável).",
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
    key: "lobby_simple_hint",
    label: "Nota sob o host (modo simples)",
    max: 512,
    multiline: true,
    group: "pedido",
    hint: "Deixa vazio para omitir a linha.",
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
    key: "host_line_prefix",
    label: "Prefixo da linha do host",
    max: 64,
    group: "pedido",
    hint: "Com @menção ligada: «Criado por @user» no texto da mensagem (clicável). Sem @menção: a mesma frase na descrição do embed.",
  },
  {
    key: "author_prefix",
    label: "Prefixo do cabeçalho (autor)",
    max: 32,
    group: "pedido",
    hint: "Só se o cabeçalho «Host · nome» estiver ligado na visibilidade. Não substitui a linha «Criado por».",
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
    label: "Título do código da party",
    max: 256,
    group: "campos",
    hint: "Título do campo por cima do bloco copiável. Padrão: 🔑 Código.",
  },
];

export function pedidosEmbedTextFields(mode: EmbedPedidosMode): EmbedTextFieldDef[] {
  if (mode === "detalhado") {
    return EMBED_TEXT_FIELDS.filter(
      (f) => f.group !== "painel" && f.key !== "lobby_simple_hint",
    );
  }
  return EMBED_TEXT_FIELDS.filter((f) => SIMPLE_EMBED_TEXT_KEYS.has(f.key));
}

export function pedidosEmbedTextSections(mode: EmbedPedidosMode) {
  const keys = new Set(pedidosEmbedTextFields(mode).map((f) => f.group));
  return EMBED_TEXT_SECTIONS.filter((s) => keys.has(s.id));
}
