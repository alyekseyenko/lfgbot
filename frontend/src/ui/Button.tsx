type Props = {
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  type?: "button" | "submit";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
};

export function Button({
  children,
  variant = "primary",
  type = "button",
  disabled,
  onClick,
  className = "",
}: Props) {
  const cls = variant === "ghost" ? `btn-ghost ${className}` : `btn ${className}`;
  return (
    <button type={type} className={cls.trim()} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}
