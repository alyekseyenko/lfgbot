import { Button } from "./Button";

type Props = {
  riotId: string;
};

export function RiotIdBadge({ riotId }: Props) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(riotId);
    } catch {
      /* ignorar */
    }
  };

  return (
    <div className="riot-id-block">
      <div>
        <p className="riot-id-block__title">Riot ID</p>
        <p className="riot-id-block__value">{riotId}</p>
        <p className="hint">Para adicionar no jogo</p>
      </div>
      <Button variant="ghost" onClick={() => void copy()}>Copiar</Button>
    </div>
  );
}
