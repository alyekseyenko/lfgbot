import { Link, useLocation } from "react-router-dom";
import { api, User } from "../api";
import { useEffect, useState } from "react";

type Props = {
  children: React.ReactNode;
};

export function AppShell({ children }: Props) {
  const location = useLocation();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    void api.me().then(setUser).catch(() => setUser(null));
  }, [location.pathname]);

  return (
    <div className="app-shell app-shell--site">
      <header className="app-shell__nav">
        <Link to="/" className="app-shell__brand">LFG Valorant</Link>
        <nav className="app-shell__links" aria-label="Principal">
          {user ? (
            <>
              <Link to="/me">Meu perfil</Link>
              <Link to="/admin">Admin</Link>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void api.logout().then(() => setUser(null))}
              >
                Sair
              </button>
            </>
          ) : (
            <a className="btn btn-sm" href="/auth/discord/login">Entrar</a>
          )}
        </nav>
      </header>
      <main className="app-shell__main">{children}</main>
    </div>
  );
}
