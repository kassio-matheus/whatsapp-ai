import { ShieldCheck } from "lucide-react"
import type * as React from "react"

import { cn } from "@workspace/ui/lib/utils"

import { ThemeToggle } from "@/components/theme-toggle"

function AuthLayout({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className="relative flex min-h-svh items-center justify-center bg-muted/40 px-4 py-10">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className={cn("flex w-full max-w-md flex-col gap-6", className)}>
        <div className="flex flex-col items-center gap-2">
          <div className="flex size-11 items-center justify-center rounded-none border bg-background ring-1 ring-foreground/10">
            <ShieldCheck className="size-5 text-primary" />
          </div>
          <span className="text-sm font-medium tracking-tight">API</span>
        </div>
        {children}
      </div>
    </div>
  )
}

export { AuthLayout }
