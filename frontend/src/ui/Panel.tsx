type Props = {
  children: React.ReactNode;
  className?: string;
  id?: string;
};

export function Panel({ children, className = "", id }: Props) {
  return (
    <section className={`panel ${className}`.trim()} id={id}>
      {children}
    </section>
  );
}
