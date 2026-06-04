import type { ReactNode } from "react";

export function Panel({
  title,
  action,
  children,
  className = "",
  testId
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <section
      className={`min-h-0 border border-terminal-border bg-terminal-panel shadow-terminal ${className}`}
      data-testid={testId}
      aria-label={title}
    >
      <div className="flex h-9 items-center justify-between border-b border-terminal-border px-3">
        <h2 className="font-mono text-xs font-semibold uppercase tracking-normal text-terminal-muted">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
