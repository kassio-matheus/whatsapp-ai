"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import {
  CheckCircle2,
  CircleAlert,
  Clipboard,
  ExternalLink,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"

import { useApp } from "@/components/app-provider"
import { CloudApiConnectionDialog } from "@/components/whatsapp/cloud-api-connection-dialog"
import { WhatsAppSectionTabs } from "@/components/whatsapp/whatsapp-section-tabs"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { PageContainer, PageHeader } from "@/components/ui/page-header"
import {
  api,
  ApiClientError,
  type WhatsAppIntegration,
} from "@/lib/api"
import { formatDateTime } from "@/lib/format"

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"

function configBoolean(integration: WhatsAppIntegration, key: string) {
  return integration.config[key] === true
}

export default function WhatsAppConfigurationPage() {
  const params = useParams<{ companyId: string }>()
  const { token } = useApp()
  const companyId = params.companyId

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [connections, setConnections] = React.useState<WhatsAppIntegration[]>([])
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editing, setEditing] = React.useState<WhatsAppIntegration | null>(null)
  const [deleting, setDeleting] = React.useState<WhatsAppIntegration | null>(null)
  const [verifyingId, setVerifyingId] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    if (!token) {
      return
    }
    try {
      const result = await api.listIntegrations(token, companyId)
      setConnections(result.filter((item) => item.adapter === "whatsapp_cloud"))
      setError(null)
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not load Meta connections.",
      )
    } finally {
      setIsLoading(false)
    }
  }, [token, companyId])

  React.useEffect(() => {
    void load()
  }, [load])

  async function handleSave({
    name,
    credentials,
    subscribe_to_webhooks,
  }: Parameters<
    React.ComponentProps<typeof CloudApiConnectionDialog>["onSave"]
  >[0]) {
    if (!token) {
      return
    }
    if (editing) {
      const result = await api.updateCloudApiIntegration(
        editing.id,
        { name, credentials, subscribe_to_webhooks },
        token,
      )
      setConnections((previous) =>
        previous.map((item) =>
          item.id === result.integration.id ? result.integration : item,
        ),
      )
      return
    }
    const result = await api.createCloudApiIntegration(
      {
        company_id: companyId,
        name,
        credentials,
        subscribe_to_webhooks,
      },
      token,
    )
    setConnections((previous) => [...previous, result.integration])
  }

  async function handleVerify(integration: WhatsAppIntegration) {
    if (!token) {
      return
    }
    setVerifyingId(integration.id)
    try {
      const result = await api.verifyCloudApiIntegration(integration.id, token)
      setConnections((previous) =>
        previous.map((item) =>
          item.id === result.integration.id ? result.integration : item,
        ),
      )
      setError(null)
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not verify this Meta connection.",
      )
    } finally {
      setVerifyingId(null)
    }
  }

  async function handleDelete() {
    if (!token || !deleting) {
      return
    }
    await api.deleteIntegration(deleting.id, token)
    setConnections((previous) =>
      previous.filter((item) => item.id !== deleting.id),
    )
    setDeleting(null)
  }

  const webhookUrl = `${API_BASE}/whatsapp/webhooks/meta`

  return (
    <PageContainer>
      <WhatsAppSectionTabs companyId={companyId} active="configuration" />

      <PageHeader
        title="WhatsApp configuration"
        description="Connect multiple official Meta Cloud API phone numbers to this company. Each connection keeps its own WABA, token, phone number and webhook settings."
      >
        <Button
          onClick={() => {
            setEditing(null)
            setDialogOpen(true)
          }}
        >
          <Plus />
          Add connection
        </Button>
      </PageHeader>

      <div className="grid gap-3 md:grid-cols-3">
        <MetricCard
          label="Active connections"
          value={connections.filter((item) => item.is_active).length}
          icon={<ShieldCheck />}
        />
        <MetricCard
          label="Webhook ready"
          value={connections.filter((item) => configBoolean(item, "webhook_subscribed")).length}
          icon={<CheckCircle2 />}
        />
        <MetricCard
          label="Phone numbers"
          value={connections.filter((item) => item.phone_number).length}
          icon={<RefreshCw />}
        />
      </div>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xs">
            <ExternalLink className="size-4" />
            Meta webhook callback
          </CardTitle>
          <CardDescription>
            Configure this URL in the Meta App Dashboard and use the same verify
            token entered for each connection.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 overflow-x-auto bg-muted px-2 py-1.5 text-[11px]">
              {webhookUrl}
            </code>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void navigator.clipboard?.writeText(webhookUrl)}
            >
              <Clipboard />
              Copy URL
            </Button>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <LoaderCircle className="size-5 animate-spin" />
        </div>
      ) : error ? (
        <Card className="p-0">
          <EmptyState
            icon={<CircleAlert />}
            title="Something went wrong"
            description={error}
            action={
              <Button variant="outline" onClick={() => void load()}>
                Retry
              </Button>
            }
          />
        </Card>
      ) : connections.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={<ShieldCheck />}
            title="No Meta connections yet"
            description="Add your first official WhatsApp Cloud API connection. You can add one connection for every WABA or phone number you operate."
            action={
              <Button
                onClick={() => {
                  setEditing(null)
                  setDialogOpen(true)
                }}
              >
                <Plus />
                Add connection
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {connections.map((connection) => (
            <ConnectionCard
              key={connection.id}
              connection={connection}
              isVerifying={verifyingId === connection.id}
              onVerify={() => void handleVerify(connection)}
              onEdit={() => {
                setEditing(connection)
                setDialogOpen(true)
              }}
              onDelete={() => setDeleting(connection)}
            />
          ))}
        </div>
      )}

      <CloudApiConnectionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode={editing ? "edit" : "create"}
        integration={editing}
        onSave={handleSave}
      />

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleting(null)
          }
        }}
        title="Remove Meta connection"
        description={`Remove "${deleting?.name ?? "this connection"}"? Its stored conversations remain available, but new messages will stop using this connection.`}
        confirmLabel="Remove"
        destructive
        onConfirm={handleDelete}
      />
    </PageContainer>
  )
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string
  value: number
  icon: React.ReactNode
}) {
  return (
    <Card size="sm">
      <CardContent className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-muted-foreground">{label}</span>
          <span className="text-lg font-medium">{value}</span>
        </div>
        <span className="text-muted-foreground">{icon}</span>
      </CardContent>
    </Card>
  )
}

function ConnectionCard({
  connection,
  isVerifying,
  onVerify,
  onEdit,
  onDelete,
}: {
  connection: WhatsAppIntegration
  isVerifying: boolean
  onVerify: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const webhookSubscribed = configBoolean(connection, "webhook_subscribed")
  const verifiedName =
    typeof connection.config.verified_name === "string"
      ? connection.config.verified_name
      : null
  const qualityRating = connection.config.quality_rating

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs">
          <span className="flex size-7 items-center justify-center bg-primary/10 text-primary">
            <ShieldCheck className="size-4" />
          </span>
          <span className="truncate">{connection.name}</span>
          <Badge variant={connection.is_active ? "secondary" : "outline"}>
            {connection.is_active ? "Active" : "Inactive"}
          </Badge>
        </CardTitle>
        <CardAction>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="icon-sm" aria-label="Connection actions">
                  <MoreHorizontal />
                </Button>
              }
            />
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onEdit}>
                <Pencil />
                Replace credentials
              </DropdownMenuItem>
              <DropdownMenuItem variant="destructive" onClick={onDelete}>
                <Trash2 />
                Remove connection
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardAction>
        <CardDescription>
          {verifiedName || connection.phone_number || "Phone number pending"}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="grid gap-2 text-[11px] sm:grid-cols-2">
          <InfoRow label="Phone" value={connection.phone_number ?? "—"} />
          <InfoRow
            label="WABA"
            value={connection.external_account_id ?? "—"}
          />
          <InfoRow
            label="Quality"
            value={typeof qualityRating === "string" ? qualityRating : "—"}
          />
          <InfoRow label="Created" value={formatDateTime(connection.created_at)} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
          <Badge variant={webhookSubscribed ? "secondary" : "outline"}>
            {webhookSubscribed ? "Webhooks subscribed" : "Webhooks not subscribed"}
          </Badge>
          <Button variant="outline" size="sm" disabled={isVerifying} onClick={onVerify}>
            {isVerifying ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}
            Verify connection
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-medium">{value}</span>
    </div>
  )
}
