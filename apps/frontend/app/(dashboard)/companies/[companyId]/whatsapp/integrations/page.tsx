"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import {
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Smartphone,
  Trash2,
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
import {
  IntegrationActiveToggle,
  IntegrationDialog,
} from "@/components/whatsapp/integration-dialog"
import { WhatsAppSectionTabs } from "@/components/whatsapp/whatsapp-section-tabs"
import {
  api,
  ApiClientError,
  type WhatsAppIntegration,
} from "@/lib/api"

export default function IntegrationsPage() {
  const params = useParams<{ companyId: string }>()
  const { token } = useApp()
  const companyId = params.companyId

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [integrations, setIntegrations] = React.useState<WhatsAppIntegration[]>([])
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editing, setEditing] = React.useState<WhatsAppIntegration | null>(null)
  const [deleting, setDeleting] = React.useState<WhatsAppIntegration | null>(null)

  const load = React.useCallback(
    async (showLoader = false) => {
      if (!token) {
        return
      }
      if (showLoader) {
        setIsLoading(true)
      }
      try {
        const result = await api.listIntegrations(token, companyId)
        setIntegrations(result)
        setError(null)
      } catch (err) {
        if (err instanceof ApiClientError) {
          setError(err.message)
        } else {
          setError("Failed to load integrations.")
        }
      } finally {
        setIsLoading(false)
      }
    },
    [token, companyId],
  )

  React.useEffect(() => {
    void load(true)
  }, [load])

  async function handleDelete() {
    if (!token || !deleting) {
      return
    }
    await api.deleteIntegration(deleting.id, token)
    setIntegrations((previous) =>
      previous.filter((integration) => integration.id !== deleting.id),
    )
    setDeleting(null)
  }

  return (
    <div className="flex flex-col gap-4">
      <WhatsAppSectionTabs companyId={companyId} active="integrations" />
      <PageHeader
        title="Integration"
        description="WhatsApp channels connected to this company."
      >
        <Button
          onClick={() => {
            setEditing(null)
            setDialogOpen(true)
          }}
        >
          <Plus />
          New integration
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
      ) : integrations.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={<Smartphone />}
            title="No integrations yet"
            description="Connect a WhatsApp channel to start managing contacts and conversations."
            action={
              <Button
                onClick={() => {
                  setEditing(null)
                  setDialogOpen(true)
                }}
              >
                <Plus />
                New integration
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
                <TableHead>Type</TableHead>
                <TableHead>Adapter</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Credentials</TableHead>
                <TableHead>Active</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {integrations.map((integration) => (
                <TableRow key={integration.id}>
                  <TableCell>
                    <span className="flex items-center gap-2 font-medium">
                      <Smartphone className="size-4 text-muted-foreground" />
                      {integration.name}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={integration.integration_type === "official" ? "secondary" : "outline"}>
                      {integration.integration_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {integration.adapter}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {integration.phone_number ?? "—"}
                  </TableCell>
                  <TableCell>
                    {integration.credentials_configured ? (
                      <Badge variant="secondary">Configured</Badge>
                    ) : (
                      <Badge variant="outline">Missing</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <IntegrationActiveToggle
                      integration={integration}
                      token={token ?? ""}
                      onChange={(updated) =>
                        setIntegrations((previous) =>
                          previous.map((item) =>
                            item.id === updated.id ? updated : item,
                          ),
                        )
                      }
                    />
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
                            setEditing(integration)
                            setDialogOpen(true)
                          }}
                        >
                          <Pencil />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          variant="destructive"
                          onClick={() => setDeleting(integration)}
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

      <IntegrationDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode={editing ? "edit" : "create"}
        integration={editing}
        companyId={companyId}
        onSave={async (data) => {
          if (!token) {
            return
          }
          if (editing) {
            const updated = await api.updateIntegration(editing.id, data, token)
            setIntegrations((previous) =>
              previous.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            )
          } else {
            const created = await api.createIntegration(data, token)
            setIntegrations((previous) => [...previous, created])
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
        title="Delete integration"
        description={`Delete "${deleting?.name ?? "this integration"}"? Its contacts, conversations, and messages will be removed.`}
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />
    </div>
  )
}
