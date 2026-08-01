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

import type {
  ConversationStatus,
  WhatsAppContact,
  WhatsAppConversation,
  WhatsAppIntegration,
} from "@/lib/api"

function ConversationDialog({
  open,
  onOpenChange,
  mode,
  conversation,
  integrations,
  contacts,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "create" | "edit"
  conversation?: WhatsAppConversation | null
  integrations: WhatsAppIntegration[]
  contacts: WhatsAppContact[]
  onSave: (data: {
    instance_id: string
    contact_id?: string
    title?: string
    status?: ConversationStatus
  }) => Promise<void>
}) {
  const [integrationId, setIntegrationId] = React.useState("")
  const [contactId, setContactId] = React.useState("")
  const [title, setTitle] = React.useState("")
  const [status, setStatus] = React.useState<ConversationStatus>("open")
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const integrationContacts = React.useMemo(() => {
    if (!integrationId) {
      return contacts
    }
    return contacts.filter((contact) => contact.instance_id === integrationId)
  }, [contacts, integrationId])

  React.useEffect(() => {
    if (!open) {
      return
    }
    setIntegrationId(
      conversation?.instance_id ?? integrations[0]?.id ?? "",
    )
    setContactId(conversation?.contact_id ?? "")
    setTitle(conversation?.title ?? "")
    setStatus(conversation?.status ?? "open")
    setError(null)
  }, [open, conversation, integrations])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!integrationId) {
      setError("Select an instance.")
      return
    }
    setIsPending(true)
    setError(null)
    try {
      await onSave({
        instance_id: integrationId,
        contact_id: contactId || undefined,
        title: title.trim() || undefined,
        status,
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
              {mode === "create" ? "New conversation" : "Edit conversation"}
            </DialogTitle>
            <DialogDescription>
              A conversation threads messages between a contact and this
              company.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-3">
            <div className="flex flex-col gap-2">
              <Label>Instance</Label>
              <Select
                items={integrations.map((integration) => ({
                  value: integration.id,
                  label: integration.name,
                }))}
                value={integrationId}
                onValueChange={(value) => {
                  setIntegrationId(String(value))
                  setContactId("")
                }}
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
            </div>
            <div className="flex flex-col gap-2">
              <Label>Contact</Label>
              <Select
                items={integrationContacts.map((contact) => ({
                  value: contact.id,
                  label:
                    contact.name ??
                    contact.phone_number ??
                    contact.id,
                }))}
                value={contactId}
                onValueChange={(value) => setContactId(String(value))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="No contact" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No contact</SelectItem>
                  {integrationContacts.map((contact) => (
                    <SelectItem key={contact.id} value={contact.id}>
                      {contact.name ?? contact.phone_number}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="conversation-title">Title</Label>
              <Input
                id="conversation-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Support ticket #42"
                autoFocus
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Status</Label>
              <Select
                items={[
                  { value: "open", label: "Open" },
                  { value: "pending", label: "Pending" },
                  { value: "closed", label: "Closed" },
                ]}
                value={status}
                onValueChange={(value) => setStatus(value as ConversationStatus)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>
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

export { ConversationDialog }
