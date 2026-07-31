"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import {
  Ban,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  UserRound,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card } from "@workspace/ui/components/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"

import { useApp } from "@/components/app-provider"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { ContactDialog } from "@/components/whatsapp/contact-dialog"
import {
  api,
  ApiClientError,
  type WhatsAppContact,
  type WhatsAppIntegration,
} from "@/lib/api"

export default function ContactsPage() {
  const params = useParams<{ companyId: string }>()
  const { token } = useApp()
  const companyId = params.companyId

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [contacts, setContacts] = React.useState<WhatsAppContact[]>([])
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editing, setEditing] = React.useState<WhatsAppContact | null>(null)
  const [deleting, setDeleting] = React.useState<WhatsAppContact | null>(null)

  const load = React.useCallback(
    async (showLoader = false) => {
      if (!token) {
        return
      }
      if (showLoader) {
        setIsLoading(true)
      }
      try {
        const result = await api.listContacts(token, {
          company_id: companyId,
          limit: 200,
        })
        setContacts(result)
        setError(null)
      } catch (err) {
        if (err instanceof ApiClientError) {
          setError(err.message)
        } else {
          setError("Failed to load contacts.")
        }
      } finally {
        setIsLoading(false)
      }
    },
    [token, companyId],
  )

  const [integrations, setIntegrations] = React.useState<WhatsAppIntegration[]>([])

  React.useEffect(() => {
    void load(true)
  }, [load])

  React.useEffect(() => {
    if (!token) {
      return
    }
    void api
      .listIntegrations(token, companyId)
      .then(setIntegrations)
      .catch(() => undefined)
  }, [token, companyId])

  async function handleDelete() {
    if (!token || !deleting) {
      return
    }
    await api.deleteContact(deleting.id, token)
    setContacts((previous) =>
      previous.filter((contact) => contact.id !== deleting.id),
    )
    setDeleting(null)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Contacts"
        description="People who interact with this company on WhatsApp."
      >
        <Button
          onClick={() => {
            setEditing(null)
            setDialogOpen(true)
          }}
        >
          <Plus />
          New contact
        </Button>
      </PageHeader>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <LoaderCircle className="size-5 animate-spin" />
        </div>
      ) : error ? (
        <Card className="p-0">
          <EmptyState
            title="Something went wrong"
            description={error}
            action={
              <Button variant="outline" onClick={() => void load(true)}>
                Retry
              </Button>
            }
          />
        </Card>
      ) : contacts.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={<UserRound />}
            title="No contacts yet"
            description="Add a contact manually or wait for inbound messages to arrive."
            action={
              <Button
                onClick={() => {
                  setEditing(null)
                  setDialogOpen(true)
                }}
              >
                <Plus />
                New contact
              </Button>
            }
          />
        </Card>
      ) : (
        <Card className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {contacts.map((contact) => (
                <TableRow key={contact.id}>
                  <TableCell>
                    <span className="flex items-center gap-2 font-medium">
                      <span className="flex size-6 items-center justify-center rounded-full bg-muted text-[10px]">
                        {(contact.name ?? contact.phone_number)[0]?.toUpperCase() ?? "?"}
                      </span>
                      {contact.name ?? "Unnamed"}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {contact.phone_number}
                  </TableCell>
                  <TableCell>
                    {contact.is_blocked ? (
                      <Badge variant="destructive">
                        <Ban />
                        Blocked
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Active</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(contact.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button variant="ghost" size="icon-sm">
                            <MoreHorizontal />
                          </Button>
                        }
                      />
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => {
                            setEditing(contact)
                            setDialogOpen(true)
                          }}
                        >
                          <Pencil />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          variant="destructive"
                          onClick={() => setDeleting(contact)}
                        >
                          <Trash2 />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <ContactDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode={editing ? "edit" : "create"}
        contact={editing}
        integrations={integrations}
        onSave={async (data) => {
          if (!token) {
            return
          }
          if (editing) {
            const updated = await api.updateContact(editing.id, data, token)
            setContacts((previous) =>
              previous.map((item) => (item.id === updated.id ? updated : item)),
            )
          } else {
            const created = await api.createContact(data, token)
            setContacts((previous) => [...previous, created])
          }
        }}
      />

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleting(null)
          }
        }}
        title="Delete contact"
        description={`Delete ${deleting?.name ?? "this contact"}? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />
    </div>
  )
}
