import { useEffect, useMemo, useState } from "react";
import { api, PlayerProfile, User, ValorantPlayerCard } from "../api";
import { Panel } from "../ui/Panel";
import { PlayerCardPicker } from "../ui/PlayerCardPicker";
import { ProfileView } from "./ProfileView";

function discordAvatarUrl(user: User): string | null {
  if (!user.avatar) return null;
  return `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=128`;
}

export function MeProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [cards, setCards] = useState<ValorantPlayerCard[]>([]);
  const [riotDraft, setRiotDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [savingRiot, setSavingRiot] = useState(false);
  const [savingCard, setSavingCard] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const me = await api.me();
        setUser(me);
        const [p, catalog] = await Promise.all([api.myProfile(), api.catalogPlayerCards()]);
        setProfile(p);
        setCards(catalog);
        setRiotDraft(p.riot_id ?? "");
      } catch {
        window.location.href = "/auth/discord/login";
      }
    })();
  }, []);

  const avatarUrl = useMemo(() => (user ? discordAvatarUrl(user) : null), [user]);

  const saveRiot = async () => {
    setSavingRiot(true);
    setError(null);
    try {
      const updated = await api.patchMyProfile({ riot_id: riotDraft.trim() || null });
      setProfile(updated);
      setRiotDraft(updated.riot_id ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível guardar.");
    } finally {
      setSavingRiot(false);
    }
  };

  const selectCard = async (uuid: string | null) => {
    if (!profile || savingCard) return;
    setSavingCard(true);
    setError(null);
    try {
      const updated = await api.patchMyProfile({ player_card_uuid: uuid });
      setProfile(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível guardar o card.");
    } finally {
      setSavingCard(false);
    }
  };

  if (!profile) {
    return <p className="hint profile-loading">A carregar o teu perfil…</p>;
  }

  return (
    <div className="profile-page-wrap">
      {error && <p className="error profile-body-error">{error}</p>}
      <ProfileView
        profile={profile}
        avatarUrl={avatarUrl}
        riotEdit={{
          draft: riotDraft,
          onDraft: setRiotDraft,
          onSave: () => void saveRiot(),
          saving: savingRiot,
        }}
      >
        <Panel className="profile-card-panel">
          <h2>Player card</h2>
          <p className="hint">
            Escolhe o fundo do teu perfil. Os cards vêm do catálogo sincronizado no admin.
            {savingCard && " A guardar…"}
          </p>
          {cards.length === 0 ? (
            <p className="hint">Catálogo vazio — pede ao staff para sincronizar no admin.</p>
          ) : (
            <PlayerCardPicker
              cards={cards}
              selectedUuid={profile.player_card_uuid}
              disabled={savingCard}
              onSelect={(uuid) => void selectCard(uuid)}
            />
          )}
        </Panel>
      </ProfileView>
    </div>
  );
}
