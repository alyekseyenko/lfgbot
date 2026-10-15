type Ability = {
  slot: string;
  display_name: string;
  display_icon: string | null;
};

type Props = {
  abilities: Ability[];
};

export function AbilityStrip({ abilities }: Props) {
  if (!abilities.length) return null;
  return (
    <div className="ability-strip" aria-label="Habilidades">
      {abilities.map((a) => (
        <div key={a.slot || a.display_name} className="ability-strip__item" title={a.display_name}>
          {a.display_icon ? <img src={a.display_icon} alt="" /> : <span>{a.display_name.slice(0, 1)}</span>}
        </div>
      ))}
    </div>
  );
}
