"use client"

import * as React from "react"
import { LoaderCircle } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import { TimezoneSelect } from "@/components/companies/timezone-select"

function CompanyDialog({
  open,
  onOpenChange,
  mode,
  initialName = "",
  initialTimezone = "UTC",
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "create" | "rename"
  initialName?: string
  initialTimezone?: string
  onSave: (name: string, timezone: string) => Promise<void>
}) {
  const [name, setName] = React.useState(initialName)
  const [timezone, setTimezone] = React.useState(initialTimezone)
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (open) {
      setName(initialName)
      setTimezone(initialTimezone)
      setError(null)
    }
  }, [open, initialName, initialTimezone])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError("Name is required.")
      return
    }
    setIsPending(true)
    setError(null)
    try {
      await onSave(trimmed, timezone)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={(event) => void handleSubmit(event)}>
          <DialogHeader>
            <DialogTitle>
              {mode === "create" ? "Create company" : "Update company"}
            </DialogTitle>
            <DialogDescription>
              {mode === "create"
                ? "Create a new workspace. You will become its owner and only you can manage it."
                : "Update the company name and timezone."}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="company-name">Name</Label>
              <Input
                id="company-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Acme Inc."
                autoFocus
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="company-timezone">Timezone</Label>
              <TimezoneSelect
                value={timezone}
                onValueChange={setTimezone}
              />
              <p className="text-xs text-muted-foreground">
                All timestamps shown for this company will be converted to this
                timezone.
              </p>
            </div>
            {error ? (
              <p className="text-xs text-destructive">{error}</p>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={isPending}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? <LoaderCircle className="animate-spin" /> : null}
              {mode === "create" ? "Create" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export { CompanyDialog }
