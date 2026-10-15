import { useMemo, useState } from "react";
import type { ValorantPlayerCard } from "../api";

type Props = {
  cards: ValorantPlayerCard[];
  selectedUuid: string | null;
  disabled?: boolean;
  onSelect: (uuid: string | null) => void;
};

export function PlayerCardPicker({ cards, selectedUuid, disabled, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? cards.filter((c) => c.display_name.toLowerCase().includes(q))
      : cards;
    return list.slice(0, 36);
  }, [cards, query]);

  return (
    <div className="player-card-picker">
      <label className="player-card-picker__search">
        Pesquisar card
        <input
          type="search"
          value={query}
          disabled={disabled}
          placeholder="Nome do card…"
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      <div className="player-card-picker__grid" role="listbox" aria-label="Player cards">
        <button
          type="button"
          className={`player-card-tile${selectedUuid === null ? " player-card-tile--active" : ""}`}
          disabled={disabled}
          onClick={() => onSelect(null)}
        >
          <span className="player-card-tile__label">Padrão</span>
        </button>
        {filtered.map((card) => (
          <button
            key={card.uuid}
            type="button"
            role="option"
            aria-selected={selectedUuid === card.uuid}
            className={`player-card-tile${selectedUuid === card.uuid ? " player-card-tile--active" : ""}`}
            disabled={disabled}
            title={card.display_name}
            onClick={() => onSelect(card.uuid)}
          >
            {card.small_art_url ? (
              <img src={card.small_art_url} alt="" loading="lazy" />
            ) : (
              <span className="player-card-tile__label">{card.display_name.slice(0, 8)}</span>
            )}
          </button>
        ))}
      </div>
      {query && filtered.length === 0 && <p className="hint">Nenhum card com esse nome.</p>}
    </div>
  );
}
