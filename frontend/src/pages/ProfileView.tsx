import { PlayerProfile } from "../api";
import { Button } from "../ui/Button";
import { Panel } from "../ui/Panel";
import { RiotIdBadge } from "../ui/RiotIdBadge";

type RiotEdit = {
  draft: string;
  onDraft: (value: string) => void;
  onSave: () => void;
  saving: boolean;
};

type Props = {
  profile: PlayerProfile;
  avatarUrl?: string | null;
  riotEdit?: RiotEdit;
  children?: React.ReactNode;
};

export function ProfileView({ profile, avatarUrl, riotEdit, children }: Props) {
  const hero = profile.player_card_wide_url;

  return (
    <div className="profile-page">
      <div
        className="profile-hero profile-hero--tall"
        style={hero ? { backgroundImage: `url(${hero})` } : undefined}
      >
        <div className="profile-hero__overlay profile-hero__overlay--card">
          {avatarUrl && (
            <img className="profile-avatar" src={avatarUrl} alt="" width={112} height={112} />
          )}
          <div className="profile-hero__identity">
            <h1>{profile.name}</h1>
            {profile.rank_label && (
              <p className="profile-rank">
                {profile.rank_icon_url && (
                  <img src={profile.rank_icon_url} alt="" className="profile-rank__icon" />
                )}
                {profile.rank_label}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="profile-body fullscreen-main">
      {riotEdit ? (
        <Panel className="profile-riot-edit">
          <h2>Riot ID</h2>
          <p className="hint">Nome#TAG — visível para outros membros com sessão Discord.</p>
          <div className="row profile-riot-row">
            <input
              className="riot-input"
              value={riotEdit.draft}
              onChange={(e) => riotEdit.onDraft(e.target.value)}
              placeholder="Zecas#EUW"
            />
            <Button disabled={riotEdit.saving} onClick={riotEdit.onSave}>Guardar</Button>
          </div>
        </Panel>
      ) : (
        profile.riot_id && <RiotIdBadge riotId={profile.riot_id} />
      )}

      <div className="profile-grid">
        <Panel>
          <h2>Nível LFG</h2>
          <p className="profile-level">{profile.stats.level}</p>
          <p className="hint">{profile.stats.next_level_hint}</p>
        </Panel>
        <Panel>
          <h2>Estatísticas</h2>
          <ul className="profile-stats">
            <li><span>Como host</span><strong>{profile.stats.host_completions}</strong></li>
            <li><span>Como jogador</span><strong>{profile.stats.player_completions}</strong></li>
            <li><span>Total</span><strong>{profile.stats.total_completions}</strong></li>
            <li><span>Expulsões</span><strong>{profile.stats.kicks_received}</strong></li>
          </ul>
        </Panel>
        <Panel className="profile-recent-panel">
          <h2>Atividade recente</h2>
          {profile.recent.length === 0 ? (
            <p className="hint">Ainda sem partidas concluídas pelo bot.</p>
          ) : (
            <ul className="profile-recent">
              {profile.recent.map((r) => (
                <li key={`${r.awarded_at}-${r.kind}`}>
                  <span>{r.mode}</span>
                  <span className="profile-recent__kind">{r.kind}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      {children}
      </div>
    </div>
  );
}
