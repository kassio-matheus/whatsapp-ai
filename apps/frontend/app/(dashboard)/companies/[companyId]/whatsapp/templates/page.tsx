"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import {
  CheckCircle2,
  CircleAlert,
  ClipboardCopy,
  Clock3,
  FileText,
  KeyRound,
  LayoutTemplate,
  LoaderCircle,
  Megaphone,
  MoreHorizontal,
  Pencil,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Wrench,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Textarea } from "@workspace/ui/components/textarea"
import { cn } from "@workspace/ui/lib/utils"

import { useApp } from "@/components/app-provider"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { WhatsAppSectionTabs } from "@/components/whatsapp/whatsapp-section-tabs"
import {
  api,
  ApiClientError,
  subscribeToWhatsAppEvents,
  type WhatsAppCloudApiTemplate,
  type WhatsAppIntegration,
} from "@/lib/api"

const statusStyle: Record<string, string> = {
  APPROVED:
    "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  PENDING:
    "border-amber-500/25 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  REJECTED: "border-destructive/25 bg-destructive/10 text-destructive",
}

const CATEGORY_META: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }> }
> = {
  MARKETING: { label: "Marketing", icon: Megaphone },
  UTILITY: { label: "Utility", icon: Wrench },
  AUTHENTICATION: { label: "Authentication", icon: KeyRound },
}

const QUALITY_META: Record<number, { label: string; chip: string }> = {
  3: {
    label: "High quality",
    chip: "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  },
  2: {
    label: "Medium quality",
    chip: "border-amber-500/25 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  },
  1: {
    label: "Low quality",
    chip: "border-destructive/25 bg-destructive/10 text-destructive",
  },
}

function templateBody(template: WhatsAppCloudApiTemplate) {
  const body = template.components.find(
    (component) => String(component.type ?? "").toUpperCase() === "BODY"
  )
  return body && typeof body.text === "string"
    ? body.text
    : "No text body provided by Meta."
}

function templateComponentSummary(template: WhatsAppCloudApiTemplate) {
  let header: string | null = null
  let buttons: string[] = []
  for (const component of template.components) {
    const type = String(component.type ?? "").toUpperCase()
    if (type === "HEADER") {
      const format = String(component.format ?? "TEXT").toUpperCase()
      header =
        format === "TEXT"
          ? typeof component.text === "string"
            ? component.text
            : null
          : `${format.charAt(0) + format.slice(1).toLowerCase()} header`
    }
    if (type === "BUTTON" && Array.isArray(component.buttons)) {
      buttons = component.buttons
        .map((button) => {
          if (!button || typeof button !== "object") {
            return null
          }
          const record = button as Record<string, unknown>
          const kind = String(record.type ?? "").toUpperCase()
          const buttonLabel =
            typeof record.text === "string"
              ? record.text
              : `${kind.charAt(0) + kind.slice(1).toLowerCase()} button`
          return buttonLabel
        })
        .filter((label): label is string => Boolean(label))
    }
  }
  return { header, buttons }
}

function qualityScoreOf(template: WhatsAppCloudApiTemplate) {
  const score = Number(template.quality_score?.score)
  return QUALITY_META[score] ?? null
}

function StatCard({
  icon,
  label,
  value,
  accent,
  delay,
}: {
  icon: React.ReactNode
  label: string
  value: number
  accent: string
  delay: number
}) {
  return (
    <Card
      className="flex flex-row stagger-enter items-center gap-3 rounded-none p-3"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div
        className={cn(
          "flex size-9 shrink-0 items-center justify-center border",
          accent
        )}
      >
        {icon}
      </div>

      <div className="min-w-0">
        <p className="text-lg leading-none font-semibold">{value}</p>
        <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
          {label}
        </p>
      </div>
    </Card>
  )
}

export default function TemplatesPage() {
  const params = useParams<{ companyId: string }>()
  const { token } = useApp()
  const [instances, setInstances] = React.useState<WhatsAppIntegration[]>([])
  const [instanceId, setInstanceId] = React.useState("")
  const [templates, setTemplates] = React.useState<WhatsAppCloudApiTemplate[]>(
    []
  )
  const [loading, setLoading] = React.useState(true)
  const [syncing, setSyncing] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [query, setQuery] = React.useState("")
  const [status, setStatus] = React.useState("all")
  const [createOpen, setCreateOpen] = React.useState(false)
  const [editing, setEditing] = React.useState<WhatsAppCloudApiTemplate | null>(
    null
  )
  const [deleting, setDeleting] =
    React.useState<WhatsAppCloudApiTemplate | null>(null)

  const cloudInstances = instances.filter(
    (instance) => instance.adapter === "whatsapp_cloud"
  )
  const selectedInstance = cloudInstances.find(
    (instance) => instance.id === instanceId
  )

  const loadInstances = React.useCallback(async () => {
    if (!token) return
    try {
      const result = await api.listInstances(token, {
        company_id: params.companyId,
      })
      setInstances(result)
      setInstanceId((current) =>
        current &&
        result.some(
          (instance) =>
            instance.id === current && instance.adapter === "whatsapp_cloud"
        )
          ? current
          : (result.find((instance) => instance.adapter === "whatsapp_cloud")
              ?.id ?? "")
      )
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not load Cloud API instances."
      )
    }
  }, [params.companyId, token])

  const loadTemplates = React.useCallback(async () => {
    if (!token || !instanceId) {
      setTemplates([])
      return
    }
    setSyncing(true)
    try {
      const result = await api.listCloudApiTemplates(instanceId, token, {
        limit: 250,
      })
      setTemplates(result.data)
      setError(null)
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not sync templates from Meta."
      )
    } finally {
      setSyncing(false)
      setLoading(false)
    }
  }, [instanceId, token])

  React.useEffect(() => {
    const timer = window.setTimeout(() => void loadInstances(), 0)
    return () => window.clearTimeout(timer)
  }, [loadInstances])

  React.useEffect(() => {
    const timer = window.setTimeout(() => void loadTemplates(), 0)
    return () => window.clearTimeout(timer)
  }, [loadTemplates])

  React.useEffect(() => {
    if (!token) return
    return subscribeToWhatsAppEvents({
      companyId: params.companyId,
      token,
      onEvent: (event) => {
        if (
          event.instance_id === instanceId &&
          (event.type.startsWith("template.") ||
            event.type === "instance.updated")
        ) {
          void loadTemplates()
        }
      },
    })
  }, [instanceId, loadTemplates, params.companyId, token])

  const visibleTemplates = templates.filter((template) => {
    const matchesQuery =
      `${template.name} ${template.language} ${template.category ?? ""}`
        .toLowerCase()
        .includes(query.toLowerCase())
    return (
      matchesQuery &&
      (status === "all" || template.status.toUpperCase() === status)
    )
  })

  const approvedCount = templates.filter(
    (template) => template.status.toUpperCase() === "APPROVED"
  ).length
  const pendingCount = templates.filter(
    (template) => template.status.toUpperCase() === "PENDING"
  ).length
  const rejectedCount = templates.filter(
    (template) => template.status.toUpperCase() === "REJECTED"
  ).length

  async function handleDelete() {
    if (!token || !instanceId || !deleting) return
    try {
      await api.deleteCloudApiTemplate(
        instanceId,
        deleting.name,
        token,
        deleting.id ? { hsm_id: deleting.id } : {}
      )
      setDeleting(null)
      await loadTemplates()
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not delete the template on Meta."
      )
      setDeleting(null)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <LoaderCircle className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Message templates"
        description="A live view of your Meta-approved outbound messages."
      >
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            <Radio className="size-3 animate-pulse" /> Live catalog
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadTemplates()}
            disabled={!instanceId || syncing}
          >
            <RefreshCw className={cn(syncing && "animate-spin")} /> Sync
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setEditing(null)
              setCreateOpen(true)
            }}
            disabled={!instanceId}
          >
            <Plus /> New template
          </Button>
        </div>
      </PageHeader>

      <WhatsAppSectionTabs companyId={params.companyId} active="templates" />

      {cloudInstances.length === 0 ? (
        <EmptyState
          icon={<LayoutTemplate />}
          title="Connect Meta Cloud API first"
          description="Templates are tied to a WhatsApp Business Account. Connect a dedicated Cloud API number to manage them here."
        />
      ) : (
        <>
          <Card className="border-primary/15 bg-gradient-to-br from-primary/[0.07] via-background to-background p-0">
            <div className="grid gap-3 p-4 md:grid-cols-[1fr_auto] md:items-center">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center border border-primary/20 bg-primary text-primary-foreground shadow-sm">
                  <LayoutTemplate className="size-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium">Meta template library</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {selectedInstance?.name ?? "Choose a Cloud API number"} ·
                    only approved templates are available in chat.
                  </p>
                </div>
              </div>
              <Select
                items={cloudInstances.map((instance) => ({
                  value: instance.id,
                  label: instance.name,
                }))}
                value={instanceId}
                onValueChange={(value) => setInstanceId(String(value))}
              >
                <SelectTrigger className="w-full bg-background md:w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {cloudInstances.map((instance) => (
                    <SelectItem key={instance.id} value={instance.id}>
                      {instance.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </Card>

          {templates.length > 0 ? (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard
                icon={<LayoutTemplate className="size-4" />}
                label="Total templates"
                value={templates.length}
                accent="border-primary/20 bg-primary/10 text-primary"
                delay={0}
              />
              <StatCard
                icon={<ShieldCheck className="size-4" />}
                label="Approved"
                value={approvedCount}
                accent="border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                delay={50}
              />
              <StatCard
                icon={<Clock3 className="size-4" />}
                label="In review"
                value={pendingCount}
                accent="border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400"
                delay={100}
              />
              <StatCard
                icon={<ShieldAlert className="size-4" />}
                label="Rejected"
                value={rejectedCount}
                accent="border-destructive/20 bg-destructive/10 text-destructive"
                delay={150}
              />
            </div>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full sm:max-w-sm">
              <Search className="pointer-events-none absolute start-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="ps-8"
                placeholder="Search templates"
              />
            </div>
            <Select
              items={[
                { value: "all", label: "All statuses" },
                { value: "APPROVED", label: "Approved" },
                { value: "PENDING", label: "In review" },
                { value: "REJECTED", label: "Rejected" },
              ]}
              value={status}
              onValueChange={(value) => setStatus(String(value))}
            >
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="APPROVED">Approved</SelectItem>
                <SelectItem value="PENDING">In review</SelectItem>
                <SelectItem value="REJECTED">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {error ? (
            <div className="flex items-center gap-2 border border-destructive/20 bg-destructive/5 p-3 text-xs text-destructive">
              <CircleAlert className="size-4" />
              {error}
            </div>
          ) : null}

          {visibleTemplates.length === 0 && !syncing ? (
            <EmptyState
              icon={<LayoutTemplate />}
              title="No templates found"
              description="Create a template or change your filters. Meta must approve a template before it can be sent."
            />
          ) : (
            <div className="grid gap-3 xl:grid-cols-2">
              {visibleTemplates.map((template) => {
                const category = CATEGORY_META[template.category ?? ""]
                const quality = qualityScoreOf(template)
                const summary = templateComponentSummary(template)
                
                return (
                  <Card
                    key={template.id}
                    className="group relative overflow-hidden p-0 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
                  >
                    <div
                      className={cn(
                        "h-1 bg-gradient-to-r",
                        template.status.toUpperCase() === "APPROVED"
                          ? "from-emerald-500 via-emerald-500/50 to-transparent"
                          : template.status.toUpperCase() === "REJECTED"
                            ? "from-destructive via-destructive/50 to-transparent"
                            : "from-amber-500 via-amber-500/50 to-transparent"
                      )}
                    />
                    <div className="grid gap-3 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-2.5">
                          {category ? (
                            <div className="flex size-8 shrink-0 items-center justify-center border border-border bg-muted/40 text-muted-foreground">
                              <category.icon className="size-4" />
                            </div>
                          ) : null}
                          <div className="min-w-0">
                            <p className="truncate font-mono text-xs font-semibold">
                              {template.name}
                            </p>
                            <p className="mt-1 text-[10px] tracking-[0.12em] text-muted-foreground uppercase">
                              {category?.label ?? "Uncategorized"} ·{" "}
                              {template.language}
                            </p>
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-1.5">
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[9px]",
                              statusStyle[template.status.toUpperCase()] ?? ""
                            )}
                          >
                            {template.status}
                          </Badge>
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  className="opacity-0 transition-opacity group-hover:opacity-100 data-open:opacity-100"
                                >
                                  <MoreHorizontal />
                                </Button>
                              }
                            />
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => {
                                  void navigator.clipboard.writeText(
                                    template.name
                                  )
                                }}
                              >
                                <ClipboardCopy />
                                Copy name
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => {
                                  setEditing(template)
                                  setCreateOpen(true)
                                }}
                              >
                                <Pencil />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                variant="destructive"
                                onClick={() => setDeleting(template)}
                              >
                                <Trash2 />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>

                      {summary.header ? (
                        <p className="flex items-center gap-1.5 border-s border-muted-foreground/30 bg-muted/30 px-3 py-1.5 text-[10px] font-medium text-muted-foreground">
                          <FileText className="size-3 shrink-0" />
                          <span className="truncate">{summary.header}</span>
                        </p>
                      ) : null}

                      <div className="border-s border-primary/40 bg-muted/30 px-3 py-2.5">
                        <p className="text-xs leading-relaxed whitespace-pre-wrap text-foreground/85">
                          {templateBody(template)}
                        </p>
                      </div>

                      {template.rejected_reason && template.rejected_reason !== "NONE" ? (
                        <p className="flex items-center gap-1.5 text-[11px] text-destructive">
                          <CircleAlert className="size-3 shrink-0" />
                          {template.rejected_reason}
                        </p>
                      ) : null}

                      <div className="flex flex-wrap items-center gap-1.5">
                        {summary.buttons.map((label, buttonIndex) => (
                          <Badge
                            key={buttonIndex}
                            variant="outline"
                            className="border-primary/20 bg-primary/[0.04] text-[9px] font-normal text-muted-foreground"
                          >
                            {label}
                          </Badge>
                        ))}
                        {quality ? (
                          <Badge
                            variant="outline"
                            className={cn("ms-auto text-[9px]", quality.chip)}
                          >
                            <CheckCircle2 className="size-3" />
                            {quality.label}
                          </Badge>
                        ) : (
                          <span className="ms-auto text-[10px] text-muted-foreground">
                            {template.components.length} component
                            {template.components.length === 1 ? "" : "s"}
                          </span>
                        )}
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </>
      )}

      {selectedInstance ? (
        <TemplateDialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open)
            if (!open) {
              setEditing(null)
            }
          }}
          instance={selectedInstance}
          token={token}
          template={editing}
          onSaved={() => void loadTemplates()}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleting(null)
          }
        }}
        title="Delete template"
        description={
          deleting
            ? `Delete "${deleting.name}" from the connected WABA? This removes it from Meta's catalog and it stops being available in chat.`
            : undefined
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />
    </div>
  )
}

type ButtonDraft = {
  type: "QUICK_REPLY" | "URL"
  text: string
  url: string
}

function componentsToForm(template: WhatsAppCloudApiTemplate): {
  name: string
  language: string
  category: string
  header: string
  body: string
  footer: string
  buttons: ButtonDraft[]
  mediaHeader: Record<string, unknown> | null
} {
  let header = ""
  let body = ""
  let footer = ""
  const buttons: ButtonDraft[] = []
  let mediaHeader: Record<string, unknown> | null = null
  for (const component of template.components) {
    const type = String(component.type ?? "").toUpperCase()
    if (type === "HEADER") {
      const format = String(component.format ?? "TEXT").toUpperCase()
      if (["IMAGE", "VIDEO", "DOCUMENT"].includes(format)) {
        mediaHeader = component
      } else {
        header = typeof component.text === "string" ? component.text : ""
      }
    } else if (type === "BODY") {
      body = typeof component.text === "string" ? component.text : ""
    } else if (type === "FOOTER") {
      footer = typeof component.text === "string" ? component.text : ""
    } else if (type === "BUTTONS" && Array.isArray(component.buttons)) {
      for (const button of component.buttons) {
        if (!button || typeof button !== "object") {
          continue
        }
        const record = button as Record<string, unknown>
        const kind = String(record.type ?? "").toUpperCase()
        buttons.push(
          kind === "URL"
            ? {
                type: "URL",
                text: typeof record.text === "string" ? record.text : "",
                url: typeof record.url === "string" ? record.url : "",
              }
            : {
                type: "QUICK_REPLY",
                text: typeof record.text === "string" ? record.text : "",
                url: "",
              }
        )
      }
    }
  }
  return {
    name: template.name,
    language: template.language,
    category: template.category ?? "UTILITY",
    header,
    body,
    footer,
    buttons,
    mediaHeader,
  }
}

function TemplateDialog({
  open,
  onOpenChange,
  instance,
  token,
  template,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  instance: WhatsAppIntegration
  token: string | null
  template: WhatsAppCloudApiTemplate | null
  onSaved: () => void
}) {
  const [name, setName] = React.useState("")
  const [language, setLanguage] = React.useState("pt_BR")
  const [category, setCategory] = React.useState("UTILITY")
  const [header, setHeader] = React.useState("")
  const [body, setBody] = React.useState("")
  const [footer, setFooter] = React.useState("")
  const [buttons, setButtons] = React.useState<ButtonDraft[]>([])
  const [preservedHeader, setPreservedHeader] = React.useState<Record<
    string,
    unknown
  > | null>(null)
  const [pending, setPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const editing = template !== null

  React.useEffect(() => {
    if (!open) {
      return
    }
    setError(null)
    if (template) {
      const form = componentsToForm(template)
      setName(form.name)
      setLanguage(form.language)
      setCategory(form.category)
      setHeader(form.header)
      setBody(form.body)
      setFooter(form.footer)
      setButtons(form.buttons)
      setPreservedHeader(form.mediaHeader)
    } else {
      setName("")
      setLanguage("pt_BR")
      setCategory("UTILITY")
      setHeader("")
      setBody("")
      setFooter("")
      setButtons([])
      setPreservedHeader(null)
    }
  }, [open, template])

  const bodyVariableCount = [...body.matchAll(/{{\s*(\d+)\s*}}/g)].length

  function addButton(type: ButtonDraft["type"]) {
    setButtons((previous) => [...previous, { type, text: "", url: "" }])
  }

  function updateButton(index: number, patch: Partial<ButtonDraft>) {
    setButtons((previous) =>
      previous.map((button, itemIndex) =>
        itemIndex === index ? { ...button, ...patch } : button
      )
    )
  }

  function removeButton(index: number) {
    setButtons((previous) =>
      previous.filter((_, itemIndex) => itemIndex !== index)
    )
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!token || !name.trim() || !body.trim()) return
    const normalizedName = name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, "_")

    const components: Record<string, unknown>[] = []
    if (preservedHeader) {
      components.push(preservedHeader)
    } else if (header.trim()) {
      components.push({ type: "HEADER", format: "TEXT", text: header.trim() })
    }
    components.push({
      type: "BODY",
      text: body.trim(),
      ...(bodyVariableCount
        ? {
            example: {
              body_text: [
                Array.from(
                  { length: bodyVariableCount },
                  (_, index) => `example ${index + 1}`
                ),
              ],
            },
          }
        : {}),
    })
    if (footer.trim()) {
      components.push({ type: "FOOTER", text: footer.trim() })
    }
    const validButtons = buttons.filter((button) => button.text.trim())
    if (validButtons.length > 0) {
      components.push({
        type: "BUTTONS",
        buttons: validButtons.map((button) =>
          button.type === "URL"
            ? {
                type: "URL",
                text: button.text.trim(),
                url: button.url.trim(),
              }
            : { type: "QUICK_REPLY", text: button.text.trim() }
        ),
      })
    }

    const payload = {
      name: normalizedName,
      language,
      category,
      components,
    }

    setPending(true)
    setError(null)
    try {
      if (editing && template) {
        await api.updateCloudApiTemplate(
          instance.id,
          template.name,
          payload,
          token,
          template.id ? { previous_hsm_id: template.id } : {}
        )
      } else {
        await api.createCloudApiTemplate(instance.id, payload, token)
      }
      onOpenChange(false)
      setName("")
      setHeader("")
      setBody("")
      setFooter("")
      setButtons([])
      setPreservedHeader(null)
      onSaved()
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : editing
            ? "Could not save the template changes to Meta."
            : "Could not submit the template to Meta."
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editing ? "Edit a message template" : "Create a message template"}
          </DialogTitle>
          <DialogDescription>
            {editing ? (
              <>
                Meta templates are immutable, so saving sends the changes as a
                new template for review and removes the previous one from the
                catalog. Use numbered variables like <code>{"{{1}}"}</code> for
                personalized values.
              </>
            ) : (
              <>
                Build a Meta-compliant template for review. Use numbered
                variables like <code>{"{{1}}"}</code> for personalized values.
                Meta enforces its own content policy before approval.
              </>
            )}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={(event) => void submit(event)} className="grid gap-3">
          <div className="grid gap-1">
            <Label htmlFor="template-name">Template name</Label>
            <Input
              id="template-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="appointment_reminder"
              className="font-mono"
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1">
              <Label>Language</Label>
              <Select
                items={[
                  { value: "pt_BR", label: "Português (Brasil)" },
                  { value: "en_US", label: "English (US)" },
                  { value: "es", label: "Español" },
                ]}
                value={language}
                onValueChange={(value) => setLanguage(String(value))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pt_BR">Português (Brasil)</SelectItem>
                  <SelectItem value="en_US">English (US)</SelectItem>
                  <SelectItem value="es">Español</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1">
              <Label>Category</Label>
              <Select
                items={[
                  { value: "UTILITY", label: "Utility" },
                  { value: "MARKETING", label: "Marketing" },
                  { value: "AUTHENTICATION", label: "Authentication" },
                ]}
                value={category}
                onValueChange={(value) => setCategory(String(value))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="UTILITY">Utility</SelectItem>
                  <SelectItem value="MARKETING">Marketing</SelectItem>
                  <SelectItem value="AUTHENTICATION">Authentication</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-1">
            <Label htmlFor="template-header">Header (optional)</Label>
            {preservedHeader ? (
              <div className="flex items-center gap-2 border border-primary/20 bg-primary/[0.04] px-2.5 py-1.5 text-[10px] text-muted-foreground">
                <FileText className="size-3 shrink-0" />
                Media header preserved as-is — this builder edits text content
                only.
              </div>
            ) : (
              <>
                <Input
                  id="template-header"
                  value={header}
                  onChange={(event) => setHeader(event.target.value)}
                  placeholder="Obrigado por escolher nossa empresa"
                  maxLength={60}
                />
                <p className="text-[10px] text-muted-foreground">
                  Up to 60 characters of text. Media headers are not supported
                  in this builder.
                </p>
              </>
            )}
          </div>
          <div className="grid gap-1">
            <Label htmlFor="template-body">Body</Label>
            <Textarea
              id="template-body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="Olá {{1}}, seu atendimento está confirmado para {{2}}."
              rows={4}
            />
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <span>
                Use <code>{"{{1}}"}</code>, <code>{"{{2}}"}</code>… for
                variables to be filled in chat.
              </span>
              <span className="tabular-nums">{body.length}/1024</span>
            </div>
          </div>
          <div className="grid gap-1">
            <Label htmlFor="template-footer">Footer (optional)</Label>
            <Input
              id="template-footer"
              value={footer}
              onChange={(event) => setFooter(event.target.value)}
              placeholder="Horário de atendimento: 9h às 18h"
              maxLength={60}
            />
          </div>

          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <Label>Buttons (optional)</Label>
              <div className="flex gap-1.5">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-[11px]"
                  onClick={() => addButton("QUICK_REPLY")}
                  disabled={buttons.length >= 3}
                >
                  <Plus /> Quick reply
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-[11px]"
                  onClick={() => addButton("URL")}
                  disabled={buttons.length >= 2}
                >
                  <Plus /> URL button
                </Button>
              </div>
            </div>
            {buttons.length > 0 ? (
              <div className="grid gap-2 border border-border bg-muted/20 p-2.5">
                {buttons.map((button, index) => (
                  <div key={index} className="grid gap-1.5">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[9px]">
                        {button.type === "URL" ? "URL" : "Quick reply"}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        Button {index + 1}
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        className="ms-auto h-6 w-6 text-destructive"
                        onClick={() => removeButton(index)}
                        aria-label="Remove button"
                      >
                        <Trash2 />
                      </Button>
                    </div>
                    <Input
                      value={button.text}
                      onChange={(event) =>
                        updateButton(index, { text: event.target.value })
                      }
                      placeholder="Button label"
                      maxLength={25}
                    />
                    {button.type === "URL" ? (
                      <Input
                        value={button.url}
                        onChange={(event) =>
                          updateButton(index, { url: event.target.value })
                        }
                        placeholder="https://example.com/{{1}}"
                      />
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
            <p className="text-[10px] text-muted-foreground">
              Meta requires a button or media for MARKETING templates. URL
              buttons may use numbered variables in the link.
            </p>
          </div>

          {error ? <p className="text-xs text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button
              type="submit"
              disabled={pending || !name.trim() || !body.trim()}
            >
              {pending ? <LoaderCircle className="animate-spin" /> : <Send />}
              {editing ? "Save changes" : "Submit to Meta"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
