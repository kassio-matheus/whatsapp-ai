"use client"

import * as React from "react"
import { ListFilter, X } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { cn } from "@workspace/ui/lib/utils"

import { SearchInput } from "@/components/ui/search-input"

export type ToolbarFilter = {
  id: string
  label: string
  value: string
  onValueChange: (value: string) => void
  options: { value: string; label: string }[]
  /** Label shown for the "no filter" option. */
  allLabel: string
  className?: string
}

export function DataToolbar({
  search,
  onSearchChange,
  searchPlaceholder = "Search…",
  searchLoading = false,
  searchShortcut,
  filters = [],
  resultCount,
  totalCount,
  onReset,
  children,
}: {
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder?: string
  searchLoading?: boolean
  searchShortcut?: string
  filters?: ToolbarFilter[]
  resultCount: number
  totalCount: number
  onReset: () => void
  /** Extra actions rendered on the right side (e.g. "New" buttons). */
  children?: React.ReactNode
}) {
  const activeFilters = filters.filter(
    (filter) => filter.value && filter.value !== "all"
  )
  const hasSearch = search.trim().length > 0
  const isFiltering = hasSearch || activeFilters.length > 0

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
          <SearchInput
            value={search}
            onValueChange={onSearchChange}
            placeholder={searchPlaceholder}
            loading={searchLoading}
            shortcut={searchShortcut}
            containerClassName="w-full sm:max-w-xs"
          />
          {filters.map((filter) => (
            <Select
              key={filter.id}
              items={filter.options}
              value={filter.value}
              onValueChange={(value) => filter.onValueChange(String(value))}
            >
              <SelectTrigger className={cn("w-full sm:w-44", filter.className)}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {filter.options.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}
        </div>
        {children ? (
          <div className="flex shrink-0 items-center gap-2">{children}</div>
        ) : null}
      </div>

      {isFiltering ? (
        <div className="flex flex-wrap items-center gap-1.5 animate-fade-in">
          <ListFilter className="size-3.5 shrink-0 text-muted-foreground" />
          {hasSearch ? (
            <FilterChip
              label={`"${search.trim()}"`}
              onClear={() => onSearchChange("")}
            />
          ) : null}
          {activeFilters.map((filter) => {
            const option = filter.options.find(
              (item) => item.value === filter.value
            )
            return (
              <FilterChip
                key={filter.id}
                label={`${filter.label}: ${option?.label ?? filter.value}`}
                onClear={() => filter.onValueChange("all")}
              />
            )
          })}
          <span className="ms-auto text-[11px] text-muted-foreground tabular-nums">
            {resultCount} of {totalCount} results
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px] text-muted-foreground"
            onClick={onReset}
          >
            <X className="size-3" />
            Clear
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="inline-flex animate-pop items-center gap-1 border border-border bg-muted/60 px-2 py-0.5 text-[10px] text-muted-foreground">
      {label}
      <button
        type="button"
        aria-label={`Remove ${label}`}
        onClick={onClear}
        className="text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/50"
      >
        <X className="size-3" />
      </button>
    </span>
  )
}