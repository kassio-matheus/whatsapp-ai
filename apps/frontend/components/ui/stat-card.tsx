import type * as React from "react"

import { Card } from "@workspace/ui/components/card"
import { cn } from "@workspace/ui/lib/utils"

function StatCard({
  label,
  value,
  icon,
  hint,
  className,
}: {
  label: string
  value: React.ReactNode
  icon?: React.ReactNode
  hint?: string
  className?: string
}) {
  return (
    <Card size="sm" className={cn("p-0", className)}>
      <div className="flex items-start justify-between gap-2 px-(--card-spacing) py-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-xs text-muted-foreground">{label}</span>
          <span className="text-xl font-medium tabular-nums">{value}</span>
          {hint ? (
            <span className="truncate text-xs text-muted-foreground">{hint}</span>
          ) : null}
        </div>
        {icon ? (
          <div className="flex size-8 shrink-0 items-center justify-center rounded-none border bg-muted/40 ring-1 ring-foreground/10 [&_svg]:size-4">
            {icon}
          </div>
        ) : null}
      </div>
    </Card>
  )
}

export { StatCard }
