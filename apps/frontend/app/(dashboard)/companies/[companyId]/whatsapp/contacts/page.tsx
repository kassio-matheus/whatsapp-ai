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
import { WhatsAppSectionTabs } from "@/components/whatsapp/whatsapp-section-tabs"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { DataToolbar } from "@/components/ui/filter-bar"
import { PageHeader } from "@/components/ui/page-header"
import { ContactDialog } from "@/components/whatsapp/contact-dialog"
import {
  api,
  ApiClientError,
  type WhatsAppContact,
  type WhatsAppIntegration,
} from "@/lib/api"
import { formatDate } from "@/lib/format"
import { useDebouncedValue } from "@/lib/use-debounced-value"

export default function ContactsPage() {
  const params = useParams<{ companyId: string }>()
  const { token, companies } = useApp()
  const companyId = params.companyId
  const timezone = React.useMemo(
    () =>
      companies.find((company) => company.id === companyId)?.timezone ??
      "UTC",
    [companies, companyId]
  )

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [contacts, setContacts] = React.useState<WhatsAppContact[]>([])
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editing, setEditing] = React.useState<WhatsAppContact | null>(null)
  const [deleting, setDeleting] = React.useState<WhatsAppContact | null>(null)
  const [search, setSearch] = React.useState("")
  const [statusFilter, setStatusFilter] = React.useState("all")
  const [searching, setSearching] = React.useState(false)

  // Guards which async response is allowed to write state (protects against
  // an older, slower request overwriting a newer one).
  const loadSeqRef = React.useRef(0)
  // Guards the loading spinner independently of the ref above. Only calls
  // made with showLoader=true bump this one.
  //
  // Why this needs to be separate: this page fires two effects on mount —
  // `load(true)` from the initial-load effect, and `load(false)` from the
  // search effect below (trimmedSearch starts out as "", so that effect ran
  // unconditionally on mount too). Both are async and race. Since they used
  // to share one counter, whichever of the two resolved *second* would bump
  // the counter past what the showLoader=true call captured, so that call's
  // `finally` block would see `loadSeqRef.current !== seq` and skip
  // `setIsLoading(false)` — even though setContacts(result) had already run
  // with the right data. The page would then sit on the spinner forever:
  // the fetch succeeded, the state was correct, nothing errored, but nobody
  // ever told the UI to stop loading. Splitting the counters, and (below)
  // skipping the search effect's very first run, removes both the race and
  // the redundant duplicate request it was racing against.
  const loaderSeqRef = React.useRef(0)

  const load = React.useCallback(
    async (
      showLoader = false,
      filters?: { name?: string; phone_number?: string }
    ) => {
      if (!token) {
        return
      }
      const seq = ++loadSeqRef.current
      const loaderSeq = showLoader ? ++loaderSeqRef.current : null
      if (showLoader) {
        setIsLoading(true)
      }
      if (filters?.name || filters?.phone_number) {
        setSearching(true)
      }
      try {
        const result = await api.listContacts(token, {
          company_id: companyId,
          name: filters?.name,
          phone_number: filters?.phone_number,
          limit: 200,
        })
        if (loadSeqRef.current === seq) {
          setContacts(result)
          setError(null)
          setSearching(false)
        }
      } catch (err) {
        if (loadSeqRef.current === seq) {
          if (err instanceof ApiClientError) {
            setError(err.message)
          } else {
            setError("Failed to load contacts.")
          }
          setSearching(false)
        }
      } finally {
        if (loaderSeq !== null && loaderSeqRef.current === loaderSeq) {
          setIsLoading(false)
        }
      }
    },
    [token, companyId]
  )

  React.useEffect(() => {
    void load(true)
  }, [load])

  const debouncedSearch = useDebouncedValue(search, 300)
  const trimmedSearch = debouncedSearch.trim()

  // Skip the very first run: the mount effect above already triggers the
  // initial (unfiltered) load, so firing this one too on mount would just
  // be a redundant duplicate request racing the first one.
  const skipFirstSearchRef = React.useRef(true)
  React.useEffect(() => {
    if (skipFirstSearchRef.current) {
      skipFirstSearchRef.current = false
      return
    }
    if (trimmedSearch) {
      void load(false, {
        name: trimmedSearch,
        phone_number: trimmedSearch,
      })
    } else {
      void load(false)
    }
  }, [trimmedSearch, load])

  const visibleContacts = React.useMemo(() => {
    if (statusFilter === "blocked") {
      return contacts.filter((contact) => contact.is_blocked)
    }
    if (statusFilter === "active") {
      return contacts.filter((contact) => !contact.is_blocked)
    }
    return contacts
  }, [contacts, statusFilter])

  const [integrations, setIntegrations] = React.useState<WhatsAppIntegration[]>(
    []
  )

  React.useEffect(() => {
    if (!token) {
      return
    }
    void api
      .listInstances(token, { company_id: companyId })
      .then(setIntegrations)
      .catch(() => undefined)
  }, [token, companyId])

  async function handleDelete() {
    if (!token || !deleting) {
      return
    }
    await api.deleteContact(deleting.id, token)
    setContacts((previous) =>
      previous.filter((contact) => contact.id !== deleting.id)
    )
    setDeleting(null)
  }

  return (
    <div className="flex flex-col gap-4">
      <WhatsAppSectionTabs companyId={companyId} active="contacts" />
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

      <div className="flex flex-col gap-2">
        <DataToolbar
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search by name or phone…"
          searchLoading={searching}
          searchShortcut="/"
          filters={[
            {
              id: "status",
              label: "Status",
              value: statusFilter,
              onValueChange: (value) => setStatusFilter(value),
              options: [
                { value: "all", label: "All statuses" },
                { value: "active", label: "Active" },
                { value: "blocked", label: "Blocked" },
              ],
              allLabel: "All statuses",
            },
          ]}
          resultCount={visibleContacts.length}
          totalCount={contacts.length}
          onReset={() => {
            setSearch("")
            setStatusFilter("all")
          }}
        />
      </div>

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
      ) : visibleContacts.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={<UserRound />}
            title="No matching contacts"
            description="Try a different search term or filter."
            action={
              <Button
                variant="outline"
                onClick={() => {
                  setSearch("")
                  setStatusFilter("all")
                }}
              >
                Clear filters
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
              {visibleContacts.map((contact, index) => (
                <TableRow
                  key={contact.id}
                  className="stagger-enter"
                  style={{ animationDelay: `${index * 40}ms` }}
                >
                  <TableCell>
                    <span className="flex items-center gap-2 font-medium">
                      <span className="flex size-6 items-center justify-center rounded-full bg-muted text-[10px]">
                        {(contact.name || contact.phone_number)[0]?.toUpperCase() ??
                          "?"}
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
                    {formatDate(contact.created_at, timezone)}
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
              previous.map((item) => (item.id === updated.id ? updated : item))
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