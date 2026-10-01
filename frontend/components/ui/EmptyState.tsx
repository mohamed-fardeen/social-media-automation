"use client";

import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  action,
  className,
  icon,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-3 rounded-lg border border-dashed border-ink-600 bg-ink-900/40 p-8",
        className,
      )}
    >
      {icon && (
        <div className="grid h-9 w-9 place-items-center rounded-md border border-ink-600 bg-ink-800 text-ink-200">
          {icon}
        </div>
      )}
      <div>
        <h3 className="text-base font-medium text-ink-50">{title}</h3>
        <p className="mt-1 max-w-md text-sm text-ink-200">{description}</p>
      </div>
      {action}
    </div>
  );
}
