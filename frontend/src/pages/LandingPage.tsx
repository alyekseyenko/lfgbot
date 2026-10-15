import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, User } from "../api";

export function LandingPage() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const navigate = useNavigate();

  useEffect(() => {
    void api.me().then(setUser).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (user) {
      navigate("/me", { replace: true });
    }
  }, [user, navigate]);

  if (user === undefined) {
    return <p className="hint landing-loading">A verificar sessão…</p>;
  }

  if (user) {
    return null;
  }

  return (
    <div className="landing landing--center">
      <div className="landing__hero">
        <h1 className="landing__title">LFG Valorant</h1>
        <p className="landing__sub">
          Entra com a tua conta Discord para ver o teu perfil — rank, progresso na comunidade e
          Riot ID para partilhar com o grupo.
        </p>
        <a className="btn landing__cta" href="/auth/discord/login">Entrar com Discord</a>
        <p className="hint landing__note">
          Já tens sessão? <Link to="/me">Abrir meu perfil</Link>
        </p>
      </div>
    </div>
  );
}
