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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import type { WhatsAppContact, WhatsAppIntegration } from "@/lib/api"

function ContactDialog({
  open,
  onOpenChange,
  mode,
  contact,
  integrations,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "create" | "edit"
  contact?: WhatsAppContact | null
  integrations: WhatsAppIntegration[]
  onSave: (data: {
    integration_id: string
    external_id?: string
    phone_number: string
    name?: string
    is_blocked?: boolean
  }) => Promise<void>
}) {
  const [integrationId, setIntegrationId] = React.useState("")
  const [phone, setPhone] = React.useState("")
  const [name, setName] = React.useState("")
  const [externalId, setExternalId] = React.useState("")
  const [isBlocked, setIsBlocked] = React.useState(false)
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!open) {
      return
    }
    setIntegrationId(
      contact?.integration_id ?? integrations[0]?.id ?? "",
    )
    setPhone(contact?.phone_number ?? "")
    setName(contact?.name ?? "")
    setExternalId(contact?.external_id ?? "")
    setIsBlocked(contact?.is_blocked ?? false)
    setError(null)
  }, [open, contact, integrations])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedPhone = phone.trim()
    if (!integrationId) {
      setError("Select an integration.")
      return
    }
    if (!trimmedPhone) {
      setError("Phone number is required.")
      return
    }
    setIsPending(true)
    setError(null)
    try {
      await onSave({
        integration_id: integrationId,
        phone_number: trimmedPhone,
        name: name.trim() || undefined,
        external_id: externalId.trim() || undefined,
        is_blocked: isBlocked,
      })
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
              {mode === "create" ? "New contact" : "Edit contact"}
            </DialogTitle>
            <DialogDescription>
              A contact is a person on WhatsApp that interacts with this
              company.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-3">
            <div className="flex flex-col gap-2">
              <Label>Integration</Label>
              <Select
                items={integrations.map((integration) => ({
                  value: integration.id,
                  label: integration.name,
                }))}
                value={integrationId}
                onValueChange={(value) => setIntegrationId(String(value))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {integrations.map((integration) => (
                    <SelectItem key={integration.id} value={integration.id}>
                      {integration.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {integrations.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Create an integration first.
                </p>
              ) : null}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="contact-phone">Phone number</Label>
                <Input
                  id="contact-phone"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  placeholder="+15551234567"
                  autoFocus
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="contact-name">Name</Label>
                <Input
                  id="contact-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Jane Doe"
                />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="contact-external">External ID</Label>
              <Input
                id="contact-external"
                value={externalId}
                onChange={(event) => setExternalId(event.target.value)}
                placeholder="Provider contact reference"
              />
            </div>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={isBlocked}
                onChange={(event) => setIsBlocked(event.target.checked)}
                className="size-3.5 accent-primary"
              />
              Blocked
            </label>
            {error ? <p className="text-xs text-destructive">{error}</p> : null}
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

export { ContactDialog }
