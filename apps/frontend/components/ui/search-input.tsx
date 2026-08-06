"use client"

import * as React from "react"
import { LoaderCircle, Search, X } from "lucide-react"

import { Input } from "@workspace/ui/components/input"
import { cn } from "@workspace/ui/lib/utils"

export type SearchInputProps = React.ComponentProps<typeof Input> & {
  value: string
  onValueChange?: (value: string) => void
  /** Shows an inline spinner on the right while a search is in flight. */
  loading?: boolean
  /**
   * A keyboard shortcut (e.g. "/" ) that focuses the field from anywhere,
   * as long as the user is not already typing in another field.
   */
  shortcut?: string
  /** The surrounding container gains extra padding for the search icon. */
  containerClassName?: string
}

export function SearchInput({
  value,
  onValueChange,
  loading = false,
  shortcut,
  containerClassName,
  className,
  placeholder = "Search…",
  onFocus,
  onBlur,
  ...props
}: SearchInputProps) {
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const [focused, setFocused] = React.useState(false)

  React.useEffect(() => {
    if (!shortcut) return
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey || event.altKey) && event.key !== shortcut) {
        return
      }
      if (event.key !== shortcut) return
      const active = document.activeElement as HTMLElement | null
      if (
        active?.tagName === "INPUT" ||
        active?.tagName === "TEXTAREA" ||
        active?.isContentEditable
      ) {
        return
      }
      event.preventDefault()
      inputRef.current?.focus()
      inputRef.current?.select()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [shortcut])

  const showClear = Boolean(value) && !loading
  const showShortcut = !value && !loading && Boolean(shortcut)

  return (
    <div className={cn("relative", containerClassName)} aria-busy={loading || undefined}>
      <Search
        className={cn(
          "pointer-events-none absolute start-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors",
          focused && "text-ring",
        )}
      />
      <Input
        ref={inputRef}
        value={value}
        onChange={(event) => onValueChange?.(event.target.value)}
        placeholder={placeholder}
        className={cn("ps-8 pe-8", focused && "border-ring", className)}
        onFocus={(event) => {
          setFocused(true)
          onFocus?.(event)
        }}
        onBlur={(event) => {
          setFocused(false)
          onBlur?.(event)
        }}
        {...props}
      />
      {loading ? (
        <LoaderCircle className="absolute end-2.5 top-1/2 size-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
      ) : null}
      {showClear ? (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => {
            onValueChange?.("")
            inputRef.current?.focus()
          }}
          className="absolute end-1.5 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded-none text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/50"
        >
          <X className="size-3.5" />
        </button>
      ) : null}
      {showShortcut ? (
        <kbd className="pointer-events-none absolute end-2.5 top-1/2 hidden -translate-y-1/2 rounded-none border border-border bg-muted/40 px-1.5 py-px font-mono text-[9px] leading-4 text-muted-foreground sm:inline-flex">
          {shortcut}
        </kbd>
      ) : null}
    </div>
  )
}