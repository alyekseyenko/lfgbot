import type { ValorantAgent } from "../api";

type Props = {
  agent: ValorantAgent;
  compact?: boolean;
};

export function AgentPortraitCard({ agent, compact }: Props) {
  const src = agent.full_portrait_url || agent.display_icon_url;
  return (
    <article className={`agent-portrait${compact ? " agent-portrait--compact" : ""}`}>
      {src ? <img src={src} alt="" loading="lazy" /> : <div className="agent-portrait__placeholder" />}
      <div className="agent-portrait__label">
        <span className="agent-portrait__role">{agent.role_name}</span>
        <strong>{agent.display_name}</strong>
      </div>
    </article>
  );
}
