import type * as React from "react"

import { Card } from "@workspace/ui/components/card"
import { cn } from "@workspace/ui/lib/utils"

function StatCard({
  label,
  value,
  icon,
  hint,
  className,
  index = 0,
}: {
  label: string
  value: React.ReactNode
  icon?: React.ReactNode
  hint?: string
  className?: string
  index?: number
}) {
  return (
    <Card
      size="sm"
      className={cn(
        "stagger-enter p-0 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm",
        className,
      )}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-start justify-between gap-2 px-(--card-spacing) py-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-xs text-muted-foreground">{label}</span>
          <span className="text-xl font-medium tabular-nums transition-colors duration-300">
            {value}
          </span>
          {hint ? (
            <span className="truncate text-xs text-muted-foreground">{hint}</span>
          ) : null}
        </div>
        {icon ? (
          <div className="flex size-8 shrink-0 items-center justify-center rounded-none border bg-muted/40 ring-1 ring-foreground/10 transition-all duration-200 group-hover:scale-105 [&_svg]:size-4">
            {icon}
          </div>
        ) : null}
      </div>
    </Card>
  )
}

export { StatCard }
