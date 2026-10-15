import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, PlayerProfile } from "../api";
import { ProfileView } from "./ProfileView";

export function PublicProfilePage() {
  const { discordId } = useParams<{ discordId: string }>();
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!discordId) return;
    void api
      .profile(discordId)
      .then(setProfile)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Perfil não encontrado."),
      );
  }, [discordId]);

  if (error) return <p className="error">{error}</p>;
  if (!profile) return <p className="hint">A carregar…</p>;
  return (
    <div className="profile-page-wrap">
      <ProfileView profile={profile} />
    </div>
  );
}
