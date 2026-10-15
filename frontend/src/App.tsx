import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AdminApp } from "./AdminApp";
import { LandingPage } from "./pages/LandingPage";
import { MeProfilePage } from "./pages/MeProfilePage";
import { PublicProfilePage } from "./pages/PublicProfilePage";
import { AppShell } from "./ui/AppShell";

function SiteRoutes() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/me" element={<MeProfilePage />} />
        <Route path="/u/:discordId" element={<PublicProfilePage />} />
      </Routes>
    </AppShell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="/*" element={<SiteRoutes />} />
      </Routes>
    </BrowserRouter>
  );
}
