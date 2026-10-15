import type { EmbedTextFieldDef } from "../embedAdminConfig";

type Props = {
  field: EmbedTextFieldDef;
  value: string;
  isCustomized: boolean;
  onChange: (value: string) => void;
  onReset: () => void;
};

export function EmbedTextFieldRow({ field, value, isCustomized, onChange, onReset }: Props) {
  const len = value.length;
  const multiline = field.multiline || field.key === "panel_description";

  return (
    <div className="embed-text-card">
      <div className="embed-text-card__head">
        <div>
          <strong className="embed-text-card__title">{field.label}</strong>
          {field.hint && <p className="embed-text-card__hint">{field.hint}</p>}
        </div>
        <div className="embed-text-card__actions">
          {isCustomized && <span className="embed-text-badge">Personalizado</span>}
          <button type="button" className="secondary embed-text-reset" onClick={onReset}>
            Repor padrão
          </button>
        </div>
      </div>
      {multiline ? (
        <textarea
          className="embed-text-card__input"
          maxLength={field.max}
          rows={field.key === "panel_description" ? 10 : 4}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={field.label}
        />
      ) : (
        <input
          className="embed-text-card__input"
          type="text"
          maxLength={field.max}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={field.label}
        />
      )}
      <p className="embed-text-card__meta">
        {len} / {field.max} caracteres (limite do Discord)
      </p>
    </div>
  );
}
