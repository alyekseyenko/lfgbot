import { useEffect, useMemo, useRef, useState } from "react";
import type { DiscordRole } from "./api";

type Props = {
  roles: DiscordRole[];
  value: string;
  onChange: (roleId: string) => void;
  placeholder?: string;
};

export function RoleSearchSelect({ roles, value, onChange, placeholder }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = value ? roles.find((r) => r.id === value) : undefined;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const sorted = [...roles].sort((a, b) => b.position - a.position);
    if (!q) return sorted;
    return sorted.filter((r) => r.name.toLowerCase().includes(q));
  }, [roles, query]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="role-search" ref={rootRef}>
      <button
        type="button"
        className="role-search-trigger"
        onClick={() => setOpen((v) => !v)}
      >
        {selected ? selected.name : placeholder ?? "Escolher role…"}
      </button>
      {open && (
        <div className="role-search-panel">
          <input
            type="search"
            className="role-search-input"
            placeholder="Pesquisar role…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <ul className="role-search-list">
            <li>
              <button
                type="button"
                className="role-search-option"
                onClick={() => {
                  onChange("");
                  setOpen(false);
                  setQuery("");
                }}
              >
                — Nenhuma —
              </button>
            </li>
            {filtered.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className={`role-search-option${r.id === value ? " active" : ""}`}
                  onClick={() => {
                    onChange(r.id);
                    setOpen(false);
                    setQuery("");
                  }}
                >
                  {r.name}
                </button>
              </li>
            ))}
            {filtered.length === 0 && (
              <li className="role-search-empty">Sem resultados.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

type MultiProps = {
  roles: DiscordRole[];
  value: string[];
  onChange: (ids: string[]) => void;
};

export function RoleMultiSearchSelect({ roles, value, onChange }: MultiProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  const selectedRoles = useMemo(
    () => roles.filter((r) => value.includes(r.id)),
    [roles, value],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const available = roles.filter((r) => !value.includes(r.id));
    const sorted = [...available].sort((a, b) => b.position - a.position);
    if (!q) return sorted;
    return sorted.filter((r) => r.name.toLowerCase().includes(q));
  }, [roles, query, value]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const remove = (id: string) => onChange(value.filter((x) => x !== id));

  const add = (id: string) => {
    if (!value.includes(id)) onChange([...value, id]);
    setQuery("");
    setOpen(false);
  };

  return (
    <div className="role-search role-multi" ref={rootRef}>
      <div className="role-chips">
        {selectedRoles.length === 0 && (
          <span className="role-chips-empty">Nenhuma role selecionada.</span>
        )}
        {selectedRoles.map((r) => (
          <span key={r.id} className="role-chip">
            {r.name}
            <button type="button" aria-label="Remover" onClick={() => remove(r.id)}>
              ×
            </button>
          </span>
        ))}
      </div>
      <button type="button" className="role-search-trigger secondary" onClick={() => setOpen((v) => !v)}>
        Adicionar role…
      </button>
      {open && (
        <div className="role-search-panel">
          <input
            type="search"
            className="role-search-input"
            placeholder="Pesquisar (ex.: Relíquias, Staff)…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <ul className="role-search-list">
            {filtered.map((r) => (
              <li key={r.id}>
                <button type="button" className="role-search-option" onClick={() => add(r.id)}>
                  {r.name}
                </button>
              </li>
            ))}
            {filtered.length === 0 && (
              <li className="role-search-empty">Sem resultados.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
