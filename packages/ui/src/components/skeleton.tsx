import { cn } from "@workspace/ui/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "shimmer rounded-none bg-linear-to-r from-muted via-muted-foreground/50 to-muted",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
