"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import {
  Bot,
  CircleAlert,
  FileText,
  LoaderCircle,
  Save,
  ShieldCheck,
  Trash2,
  Upload,
  UserRound,
  Wrench,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Switch } from "@workspace/ui/components/switch"
import { Textarea } from "@workspace/ui/components/textarea"

import { useApp } from "@/components/app-provider"
import { EmptyState } from "@/components/ui/empty-state"
import { PageContainer, PageHeader } from "@/components/ui/page-header"
import { WhatsAppSectionTabs } from "@/components/whatsapp/whatsapp-section-tabs"
import {
  api,
  ApiClientError,
  type AIDocumentStatus,
  type CompanyKnowledge,
  type McpToolInfo,
  type WhatsAppAISettings,
} from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

export default function WhatsAppAIPage() {
  const params = useParams<{ companyId: string }>()
  const { token } = useApp()
  const companyId = params.companyId

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [settings, setSettings] = React.useState<WhatsAppAISettings | null>(null)
  const [tools, setTools] = React.useState<McpToolInfo[]>([])
  const [saving, setSaving] = React.useState(false)

  // Editable form state
  const [enabled, setEnabled] = React.useState(false)
  const [systemPrompt, setSystemPrompt] = React.useState("")
  const [trustedPhones, setTrustedPhones] = React.useState("")
  const [cooldown, setCooldown] = React.useState("20")
  const [allowedTools, setAllowedTools] = React.useState<string[]>([])

  // Company knowledge (injected into the system prompt)
  const [knowledge, setKnowledge] = React.useState<CompanyKnowledge | null>(null)
  const [companyInfo, setCompanyInfo] = React.useState("")
  const [knowledgeSaving, setKnowledgeSaving] = React.useState(false)
  const [uploadingDocument, setUploadingDocument] = React.useState(false)
  const [deletingDocument, setDeletingDocument] = React.useState<string | null>(null)
  const documentInputRef = React.useRef<HTMLInputElement>(null)

  const load = React.useCallback(
    async (showLoader = false) => {
      if (!token) {
        return
      }
      if (showLoader) {
        setIsLoading(true)
      }
      try {
        const [settingsResult, toolsResult, knowledgeResult] = await Promise.all([
          api.getCompanyAISettings(companyId, token),
          api.listCompanyAIMcpTools(companyId, token),
          api.getCompanyKnowledge(companyId, token),
        ])
        setSettings(settingsResult)
        setEnabled(settingsResult.enabled)
        setSystemPrompt(settingsResult.system_prompt ?? "")
        setTrustedPhones(settingsResult.trusted_phone_numbers.join("\n"))
        setCooldown(String(settingsResult.reply_cooldown_seconds))
        setAllowedTools(settingsResult.allowed_contact_tools)
        setTools(toolsResult.tools)
        setKnowledge(knowledgeResult)
        setCompanyInfo(knowledgeResult.company_info ?? "")
        setError(null)
      } catch (err) {
        setError(
          err instanceof ApiClientError
            ? err.message
            : "Could not load the AI assistant settings.",
        )
      } finally {
        setIsLoading(false)
      }
    },
    [companyId, token],
  )

  React.useEffect(() => {
    void load(true)
  }, [load])

  function toggleTool(name: string, checked: boolean) {
    setAllowedTools((previous) =>
      checked ? [...previous, name] : previous.filter((item) => item !== name),
    )
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    if (!token) {
      return
    }
    setSaving(true)
    setError(null)
    try {
      const trusted = trustedPhones
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean)
      const cooldownValue = Number.parseInt(cooldown, 10)
      const result = await api.updateCompanyAISettings(
        companyId,
        {
          enabled,
          system_prompt: systemPrompt.trim() || null,
          trusted_phone_numbers: trusted,
          allowed_contact_tools: allowedTools,
          reply_cooldown_seconds:
            Number.isNaN(cooldownValue) ? 20 : Math.max(0, cooldownValue),
        },
        token,
      )
      setSettings(result)
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not save the AI assistant settings.",
      )
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveKnowledge() {
    if (!token) {
      return
    }
    setKnowledgeSaving(true)
    setError(null)
    try {
      const result = await api.updateCompanyKnowledge(
        companyId,
        { company_info: companyInfo.trim() || null },
        token,
      )
      setKnowledge(result)
      setCompanyInfo(result.company_info ?? "")
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not save the company information.",
      )
    } finally {
      setKnowledgeSaving(false)
    }
  }

  async function handleUploadDocument(file: File) {
    if (!token) {
      return
    }
    setUploadingDocument(true)
    setError(null)
    try {
      const document = await api.uploadCompanyDocument(companyId, file, token)
      setKnowledge((previous) => ({
        company_id: companyId,
        company_info: companyInfo.trim() || null,
        documents: [...(previous?.documents ?? []), document],
      }))
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not upload the document.",
      )
    } finally {
      setUploadingDocument(false)
      if (documentInputRef.current) {
        documentInputRef.current.value = ""
      }
    }
  }

  async function handleDeleteDocument(documentId: string) {
    if (!token) {
      return
    }
    setDeletingDocument(documentId)
    setError(null)
    try {
      await api.deleteCompanyDocument(companyId, documentId, token)
      setKnowledge((previous) =>
        previous
          ? {
              ...previous,
              documents: previous.documents.filter(
                (document) => document.id !== documentId,
              ),
            }
          : previous,
      )
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not delete the document.",
      )
    } finally {
      setDeletingDocument(null)
    }
  }

  if (isLoading) {
    return (
      <PageContainer>
        <WhatsAppSectionTabs companyId={companyId} active="ai" />
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <LoaderCircle className="size-5 animate-spin" />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <WhatsAppSectionTabs companyId={companyId} active="ai" />

      <PageHeader
        title="AI Assistant"
        description="Let the AI answer inbound WhatsApp messages automatically. The model, provider and thinking power are configured globally in AI Settings."
      >
        <Badge variant={enabled ? "secondary" : "outline"}>
          <Bot className="size-3" />
          {enabled ? "Auto-replies on" : "Auto-replies off"}
        </Badge>
      </PageHeader>

      {error && !settings ? (
        <Card className="p-0">
          <EmptyState
            icon={<CircleAlert />}
            title="Something went wrong"
            description={error}
            action={
              <Button variant="outline" onClick={() => void load(true)}>
                Retry
              </Button>
            }
          />
        </Card>
      ) : (
        <form onSubmit={(event) => void handleSave(event)} className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs">
                <Bot className="size-4" />
                Automatic replies
              </CardTitle>
              <CardDescription>
                When enabled, the AI replies to inbound messages using the
                conversation history. Inbound messages trigger replies only when
                the company settings and the conversation both allow it.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium">Auto-reply to contacts</span>
                  <span className="text-[11px] text-muted-foreground">
                    Turn the assistant on for new inbound messages.
                  </span>
                </div>
                <Switch
                  checked={enabled}
                  onCheckedChange={setEnabled}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ai-system-prompt">System prompt</Label>
                <Textarea
                  id="ai-system-prompt"
                  value={systemPrompt}
                  onChange={(event) => setSystemPrompt(event.target.value)}
                  placeholder="Optional instructions steering automatic replies. Defaults to a safe support-agent prompt."
                  className="min-h-28"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ai-cooldown">Reply cooldown (seconds)</Label>
                <Input
                  id="ai-cooldown"
                  type="number"
                  min={0}
                  max={3600}
                  value={cooldown}
                  onChange={(event) => setCooldown(event.target.value)}
                />
                <p className="text-[11px] text-muted-foreground">
                  Minimum time between two automatic replies in the same
                  conversation.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs">
                <FileText className="size-4" />
                Company knowledge base
              </CardTitle>
              <CardDescription>
                Company information and documents that are injected into the AI
                assistant's system prompt, so it answers from your business
                data. Uploaded documents are read by the document-reading AI.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="ai-company-info">Company information</Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void handleSaveKnowledge()}
                    disabled={knowledgeSaving}
                  >
                    {knowledgeSaving ? (
                      <LoaderCircle className="size-3 animate-spin" />
                    ) : (
                      <Save className="size-3" />
                    )}
                    Save info
                  </Button>
                </div>
                <Textarea
                  id="ai-company-info"
                  value={companyInfo}
                  onChange={(event) => setCompanyInfo(event.target.value)}
                  placeholder="Describe the company: products, services, prices, policies, tone of voice... Everything here is given to the AI in the system prompt."
                  className="min-h-24"
                />
                <p className="text-[11px] text-muted-foreground">
                  Free-form description of the business. Shared with the AI Chat
                  of the company's members as well.
                </p>
              </div>

              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-3">
                  <Label>Documents</Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => documentInputRef.current?.click()}
                    disabled={uploadingDocument}
                  >
                    {uploadingDocument ? (
                      <LoaderCircle className="size-3 animate-spin" />
                    ) : (
                      <Upload className="size-3" />
                    )}
                    Upload
                  </Button>
                  <input
                    ref={documentInputRef}
                    type="file"
                    accept=".txt,.pdf,.jpg,.jpeg,.png"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0]
                      if (file) {
                        void handleUploadDocument(file)
                      }
                    }}
                  />
                </div>

                {knowledge?.documents.length ? (
                  <ul className="flex flex-col divide-y">
                    {knowledge.documents.map((document) => (
                      <li
                        key={document.id}
                        className="flex items-center gap-3 py-2"
                      >
                        <FileText className="size-4 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 flex-1 truncate text-xs">
                          {document.filename}
                        </span>
                        <ExtractionBadge
                          status={document.extraction_status}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Delete ${document.filename}`}
                          onClick={() => void handleDeleteDocument(document.id)}
                          disabled={deletingDocument === document.id}
                        >
                          {deletingDocument === document.id ? (
                            <LoaderCircle className="size-3 animate-spin" />
                          ) : (
                            <Trash2 className="size-3" />
                          )}
                        </Button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] text-muted-foreground">
                    No documents yet. Upload a PDF, image or text file to give
                    the assistant more context.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs">
                <ShieldCheck className="size-4" />
                Trusted numbers (system owners)
              </CardTitle>
              <CardDescription>
                Conversations started by these numbers give the AI full access to
                every backend tool. One number per line; the integration number is
                always treated as an owner.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                value={trustedPhones}
                onChange={(event) => setTrustedPhones(event.target.value)}
                placeholder={"+12025550123\n+5521987654321"}
                className="min-h-20 font-mono"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs">
                <Wrench className="size-4" />
                Contact tool access
              </CardTitle>
              <CardDescription>
                Tools the AI may call when the sender is a regular contact. Leave
                empty to make the AI answer only with text.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {tools.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No backend tools are exposed. Every backend route becomes an MCP
                  tool once the server initializes.
                </p>
              ) : (
                <ul className="flex flex-col divide-y">
                  {tools.map((tool) => {
                    const checked = allowedTools.includes(tool.name)
                    return (
                      <li key={tool.name}>
                        <label className="flex cursor-pointer items-center gap-3 py-2">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) =>
                              toggleTool(tool.name, event.target.checked)
                            }
                            className="size-3.5 shrink-0 accent-primary"
                          />
                          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                            <span className="truncate font-mono text-xs font-medium">
                              {tool.name}
                            </span>
                            <span className="truncate text-[10px] text-muted-foreground">
                              {tool.method} {tool.path}
                            </span>
                          </span>
                          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                            <UserRound className="size-3" />
                            {tool.requires_auth ? "needs auth" : "public"}
                          </span>
                        </label>
                      </li>
                    )
                  })}
                </ul>
              )}
            </CardContent>
          </Card>

          {error ? (
            <p className="text-xs text-destructive">{error}</p>
          ) : null}

          <div className="flex items-center justify-end gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? <LoaderCircle className="animate-spin" /> : <Save />}
              Save settings
            </Button>
          </div>
        </form>
      )}
    </PageContainer>
  )
}

const EXTRACTION_LABELS: Record<AIDocumentStatus, string> = {
  pending: "Waiting to be read",
  processing: "Reading…",
  extracted: "Read",
  failed: "Failed",
}

function ExtractionBadge({ status }: { status: AIDocumentStatus }) {
  const colored =
    status === "extracted"
      ? "bg-green-50 text-green-700"
      : status === "failed"
        ? "bg-red-50 text-red-700"
        : "bg-muted text-muted-foreground"
  return (
    <Badge variant="outline" className={cn("text-[10px]", colored)}>
      {EXTRACTION_LABELS[status]}
    </Badge>
  )
}
