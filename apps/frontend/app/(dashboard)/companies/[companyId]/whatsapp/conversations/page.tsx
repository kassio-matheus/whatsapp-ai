"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import {
  Bot,
  Check,
  CheckCheck,
  FileText,
  LayoutTemplate,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Radio,
  RotateCcw,
  StickyNote,
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
import { ScrollArea } from "@workspace/ui/components/scroll-area"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Switch } from "@workspace/ui/components/switch"
import { cn } from "@workspace/ui/lib/utils"

import { useApp } from "@/components/app-provider"
import { WhatsAppSectionTabs } from "@/components/whatsapp/whatsapp-section-tabs"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { ConversationDialog } from "@/components/whatsapp/conversation-dialog"
import {
  MessageComposer,
  type ComposerMessageData,
} from "@/components/whatsapp/message-composer"
import { MessageDialog } from "@/components/whatsapp/message-dialog"
import {
  api,
  ApiClientError,
  subscribeToWhatsAppEvents,
  type ConversationAISettings,
  type ConversationStatus,
  type WhatsAppContact,
  type WhatsAppCloudApiTemplate,
  type WhatsAppConversation,
  type WhatsAppIntegration,
  type WhatsAppMessage,
} from "@/lib/api"
import { formatDateTime } from "@/lib/format"

const STATUS_BADGE: Record<
  ConversationStatus,
  { label: string; variant: "secondary" | "outline" | "default" }
> = {
  open: { label: "Open", variant: "secondary" },
  pending: { label: "Pending", variant: "outline" },
  closed: { label: "Closed", variant: "default" },
}

function StatusBadge({ status }: { status: ConversationStatus }) {
  const config = STATUS_BADGE[status]
  return <Badge variant={config.variant}>{config.label}</Badge>
}

function MessageStatusIcon({ message }: { message: WhatsAppMessage }) {
  if (message.direction === "inbound") {
    return null
  }
  switch (message.status) {
    case "read":
      return <CheckCheck className="size-3 text-primary" />
    case "delivered":
      return <CheckCheck className="size-3 text-muted-foreground" />
    case "sent":
      return <Check className="size-3 text-muted-foreground" />
    case "failed":
      return <Check className="size-3 text-destructive" />
    default:
      return <Check className="size-3 text-muted-foreground opacity-50" />
  }
}

export default function ConversationsPage() {
  const params = useParams<{ companyId: string }>()
  const { token } = useApp()
  const companyId = params.companyId

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [conversations, setConversations] = React.useState<
    WhatsAppConversation[]
  >([])
  const [integrations, setIntegrations] = React.useState<WhatsAppIntegration[]>(
    []
  )
  const [contacts, setContacts] = React.useState<WhatsAppContact[]>([])
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [messages, setMessages] = React.useState<WhatsAppMessage[]>([])
  const [messagesLoading, setMessagesLoading] = React.useState(false)
  const [templates, setTemplates] = React.useState<WhatsAppCloudApiTemplate[]>(
    []
  )
  const [templatesLoading, setTemplatesLoading] = React.useState(false)
  const [templatesError, setTemplatesError] = React.useState<string | null>(
    null
  )
  const [aiPending, setAiPending] = React.useState(false)
  const [companyAiEnabled, setCompanyAiEnabled] = React.useState<boolean | null>(
    null
  )
  const [conversationAi, setConversationAi] =
    React.useState<ConversationAISettings | null>(null)
  const [aiSettingsLoading, setAiSettingsLoading] = React.useState(false)
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editingConversation, setEditingConversation] =
    React.useState<WhatsAppConversation | null>(null)
  const [editingMessage, setEditingMessage] =
    React.useState<WhatsAppMessage | null>(null)
  const [deletingConversation, setDeletingConversation] =
    React.useState<WhatsAppConversation | null>(null)
  const [deletingMessage, setDeletingMessage] =
    React.useState<WhatsAppMessage | null>(null)

  const selected =
    conversations.find((conversation) => conversation.id === selectedId) ?? null

  const loadConversations = React.useCallback(
    async (showLoader = false) => {
      if (!token) {
        return
      }
      if (showLoader) {
        setIsLoading(true)
      }
      try {
        const [conversationsResult, integrationsResult, contactsResult] =
          await Promise.all([
            api.listConversations(token, { company_id: companyId, limit: 100 }),
            api.listInstances(token, companyId),
            api.listContacts(token, { company_id: companyId, limit: 200 }),
          ])
        setConversations(conversationsResult)
        setIntegrations(integrationsResult)
        setContacts(contactsResult)
        setError(null)
        setSelectedId((previous) => {
          if (previous && conversationsResult.some((c) => c.id === previous)) {
            return previous
          }
          return conversationsResult[0]?.id ?? null
        })
      } catch (err) {
        if (err instanceof ApiClientError) {
          setError(err.message)
        } else {
          setError("Failed to load conversations.")
        }
      } finally {
        setIsLoading(false)
      }
    },
    [token, companyId]
  )

  const loadMessages = React.useCallback(
    async (conversationId: string | null, showLoader = false) => {
      if (!token || !conversationId) {
        setMessages([])
        return
      }
      if (showLoader) {
        setMessagesLoading(true)
      }
      try {
        const result = await api.listConversationMessages(conversationId, token)
        setMessages(result)
      } finally {
        if (showLoader) {
          setMessagesLoading(false)
        }
      }
    },
    [token]
  )

  React.useEffect(() => {
    void loadConversations(true)
  }, [loadConversations])

  React.useEffect(() => {
    if (!token) {
      setCompanyAiEnabled(null)
      return
    }
    let cancelled = false
    void api
      .getCompanyAISettings(companyId, token)
      .then((result) => {
        if (!cancelled) {
          setCompanyAiEnabled(result.enabled)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [companyId, token])

  React.useEffect(() => {
    if (!token || !selectedId) {
      setConversationAi(null)
      return
    }
    let cancelled = false
    setAiSettingsLoading(true)
    void api
      .getConversationAISettings(selectedId, token)
      .then((result) => {
        if (!cancelled) {
          setConversationAi(result)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) {
          setAiSettingsLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [selectedId, token])

  React.useEffect(() => {
    void loadMessages(selectedId, true)
  }, [selectedId, loadMessages])

  React.useEffect(() => {
    const integration = integrations.find(
      (item) => item.id === selected?.instance_id
    )
    if (!token || !integration || integration.adapter !== "whatsapp_cloud") {
      const resetTimer = window.setTimeout(() => {
        setTemplates([])
        setTemplatesError(
          integration
            ? "Templates are available only for Meta Cloud API conversations."
            : null
        )
      }, 0)
      return () => window.clearTimeout(resetTimer)
    }
    let cancelled = false
    const requestTimer = window.setTimeout(() => {
      setTemplatesLoading(true)
      setTemplatesError(null)
      void api
        .listCloudApiTemplates(integration.id, token, { limit: 250 })
        .then((result) => {
          if (!cancelled) {
            setTemplates(result.data)
          }
        })
        .catch((err) => {
          if (!cancelled) {
            setTemplates([])
            setTemplatesError(
              err instanceof ApiClientError
                ? err.message
                : "Could not load Meta templates."
            )
          }
        })
        .finally(() => {
          if (!cancelled) {
            setTemplatesLoading(false)
          }
        })
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(requestTimer)
    }
  }, [integrations, selected?.instance_id, token])

  React.useEffect(() => {
    if (!token) {
      return
    }
    return subscribeToWhatsAppEvents({
      companyId,
      token,
      onEvent: (event) => {
        void loadConversations()
        if (
          selectedId &&
          (!event.conversation_id || event.conversation_id === selectedId)
        ) {
          void loadMessages(selectedId)
        }
      },
    })
  }, [companyId, loadConversations, loadMessages, selectedId, token])

  async function handleSendMessage(data: ComposerMessageData) {
    if (!token || !selectedId) {
      return
    }
    const created = await api.createMessage(
      {
        conversation_id: selectedId,
        direction: "outbound",
        message_type: data.message_type,
        content: data.content,
        media_url: data.media_url,
        metadata: data.metadata,
        status: "pending",
      },
      token
    )
    setMessages((previous) => [...previous, created])
    void loadConversations()
  }

  async function handleCreateNote(content: string) {
    if (!token || !selectedId) {
      return
    }
    const created = await api.createNote(selectedId, content, token)
    setMessages((previous) => [...previous, created])
    void loadConversations()
  }

  async function handleAskAi(prompt: string) {
    if (!token || !selectedId) {
      return
    }
    setAiPending(true)
    try {
      const result = await api.askAi(selectedId, prompt, token)
      setMessages((previous) => [
        ...previous,
        result.prompt_message,
        result.message,
      ])
      void loadConversations()
    } finally {
      setAiPending(false)
    }
  }

  async function handleToggleConversationAi(enabled: boolean) {
    if (!token || !selectedId) {
      return
    }
    setAiSettingsLoading(true)
    try {
      const updated = await api.updateConversationAISettings(
        selectedId,
        { enabled },
        token
      )
      setConversationAi(updated)
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not update the conversation AI setting."
      )
    } finally {
      setAiSettingsLoading(false)
    }
  }

  async function handleResetConversationAi() {
    if (!token || !selectedId) {
      return
    }
    setAiSettingsLoading(true)
    try {
      const updated = await api.updateConversationAISettings(
        selectedId,
        { enabled: null },
        token
      )
      setConversationAi(updated)
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not reset the conversation AI setting."
      )
    } finally {
      setAiSettingsLoading(false)
    }
  }

  async function handleUploadMedia(file: File): Promise<string> {
    if (!token) {
      throw new Error("You must be signed in to upload media.")
    }
    const upload = await api.uploadWhatsAppMedia(file, token)
    return upload.url
  }

  async function handleDeleteConversation() {
    if (!token || !deletingConversation) {
      return
    }
    await api.deleteConversation(deletingConversation.id, token)
    setConversations((previous) =>
      previous.filter(
        (conversation) => conversation.id !== deletingConversation.id
      )
    )
    if (selectedId === deletingConversation.id) {
      setSelectedId(null)
    }
    setDeletingConversation(null)
  }

  async function handleDeleteMessage() {
    if (!token || !deletingMessage) {
      return
    }
    await api.deleteMessage(deletingMessage.id, token)
    setMessages((previous) =>
      previous.filter((message) => message.id !== deletingMessage.id)
    )
    setDeletingMessage(null)
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-40 rounded-none" />
        <div className="grid gap-3 lg:grid-cols-[320px_1fr]">
          <Skeleton className="h-[520px] rounded-none" />
          <Skeleton className="h-[520px] rounded-none" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col gap-4">
        <EmptyState
          title="Something went wrong"
          description={error}
          action={
            <Button
              variant="outline"
              onClick={() => void loadConversations(true)}
            >
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <WhatsAppSectionTabs companyId={companyId} active="conversations" />
      <PageHeader
        title="Conversations"
        description="Live inbox for inbound and outbound WhatsApp messages."
      >
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            <Radio className="size-3 animate-pulse" />
            Live sync
          </Badge>
          <Button
            onClick={() => {
              setEditingConversation(null)
              setDialogOpen(true)
            }}
          >
            <Plus />
            New conversation
          </Button>
        </div>
      </PageHeader>

      {conversations.length === 0 ? (
        <EmptyState
          icon={<Plus />}
          title="No conversations yet"
          description="Create a conversation to start messaging a contact."
          action={
            <Button
              onClick={() => {
                setEditingConversation(null)
                setDialogOpen(true)
              }}
            >
              <Plus />
              New conversation
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-[320px_1fr]">
          <Card className="p-0">
            <ScrollArea className="h-[520px]">
              <ul className="flex flex-col">
                {conversations.map((conversation, index) => {
                  const contact = contacts.find(
                    (c) => c.id === conversation.contact_id
                  )
                  const integration = integrations.find(
                    (i) => i.id === conversation.instance_id
                  )
                  const isActive = conversation.id === selectedId
                  return (
                    <li
                      key={conversation.id}
                      className="stagger-enter"
                      style={{ animationDelay: `${index * 30}ms` }}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedId(conversation.id)}
                        className={cn(
                          "flex w-full flex-col gap-1 border-b px-3 py-3 text-start transition-colors duration-150 outline-none hover:bg-accent",
                          isActive && "bg-accent"
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-xs font-medium">
                            {conversation.title ??
                              contact?.name ??
                              contact?.phone_number ??
                              "Untitled conversation"}
                          </span>
                          <StatusBadge status={conversation.status} />
                        </div>
                        <span className="truncate text-[10px] text-muted-foreground">
                          {integration?.name ?? "Unknown instance"}
                          {contact?.phone_number
                            ? ` · ${contact.phone_number}`
                            : ""}
                        </span>
                        {conversation.last_message_at ? (
                          <span className="text-[10px] text-muted-foreground">
                            {formatDateTime(conversation.last_message_at)}
                          </span>
                        ) : null}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </ScrollArea>
          </Card>

          <Card className="flex h-[520px] p-0">
            {!selected ? (
              <EmptyState
                title="Select a conversation"
                description="Choose a conversation from the list to view its messages."
              />
            ) : (
              <>
                <div className="flex items-center justify-between gap-2 border-b px-3 py-2.5">
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-xs font-medium">
                      {selected.title ??
                        contacts.find((c) => c.id === selected.contact_id)
                          ?.name ??
                        "Untitled conversation"}
                    </span>
                    <StatusBadge status={selected.status} />
                  </div>
                  <div className="flex items-center gap-2">
                    <label
                      title={
                        conversationAi?.enabled === null
                          ? "Following the company default"
                          : "Customized for this conversation"
                      }
                      className="flex items-center gap-1.5 text-[10px] text-muted-foreground"
                    >
                      <Bot className="size-3" />
                      <Switch
                        checked={
                          conversationAi?.enabled ?? companyAiEnabled ?? false
                        }
                        disabled={
                          aiSettingsLoading || companyAiEnabled === null
                        }
                        onCheckedChange={(checked) =>
                          void handleToggleConversationAi(checked)
                        }
                      />
                    </label>
                    {conversationAi?.enabled !== null ? (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="Reset to company default"
                        onClick={() => void handleResetConversationAi()}
                      >
                        <RotateCcw />
                      </Button>
                    ) : null}
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
                          setEditingConversation(selected)
                          setDialogOpen(true)
                        }}
                      >
                        <Pencil />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => setDeletingConversation(selected)}
                      >
                        <Trash2 />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>

                <ScrollArea className="flex-1">
                  <div className="flex flex-col gap-2 p-3">
                    {messagesLoading ? (
                      <div className="flex justify-center py-8 text-muted-foreground">
                        <LoaderCircle className="size-4 animate-spin" />
                      </div>
                    ) : messages.length === 0 ? (
                      <p className="py-8 text-center text-xs text-muted-foreground">
                        No messages yet. Send the first one below.
                      </p>
                    ) : (
                      messages.map((message) => (
                        <MessageBubble
                          key={message.id}
                          message={message}
                          templates={templates}
                          onEdit={() => setEditingMessage(message)}
                          onDelete={() => setDeletingMessage(message)}
                        />
                      ))
                    )}
                  </div>
                </ScrollArea>

                <MessageComposer
                  messages={messages}
                  disabled={!selected}
                  templates={templates}
                  templatesLoading={templatesLoading}
                  templatesError={templatesError}
                  onSend={handleSendMessage}
                  onNote={handleCreateNote}
                  onAi={handleAskAi}
                  onUpload={handleUploadMedia}
                  aiPending={aiPending}
                />
              </>
            )}
          </Card>
        </div>
      )}

      <ConversationDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode={editingConversation ? "edit" : "create"}
        conversation={editingConversation}
        integrations={integrations}
        contacts={contacts}
        onSave={async (data) => {
          if (!token) {
            return
          }
          if (editingConversation) {
            const updated = await api.updateConversation(
              editingConversation.id,
              data,
              token
            )
            setConversations((previous) =>
              previous.map((item) => (item.id === updated.id ? updated : item))
            )
          } else {
            const created = await api.createConversation(data, token)
            setConversations((previous) => [...previous, created])
            setSelectedId(created.id)
          }
        }}
      />

      <MessageDialog
        open={editingMessage !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditingMessage(null)
          }
        }}
        message={editingMessage}
        onSave={async (data) => {
          if (!token || !editingMessage) {
            return
          }
          const updated = await api.updateMessage(
            editingMessage.id,
            data,
            token
          )
          setMessages((previous) =>
            previous.map((item) => (item.id === updated.id ? updated : item))
          )
        }}
      />

      <ConfirmDialog
        open={deletingConversation !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeletingConversation(null)
          }
        }}
        title="Delete conversation"
        description="Delete this conversation and all of its messages? This cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConversation}
      />

      <ConfirmDialog
        open={deletingMessage !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeletingMessage(null)
          }
        }}
        title="Delete message"
        description="Delete this message? This cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteMessage}
      />
    </div>
  )
}

function MessageBubble({
  message,
  templates = [],
  onEdit,
  onDelete,
}: {
  message: WhatsAppMessage
  templates?: WhatsAppCloudApiTemplate[]
  onEdit: () => void
  onDelete: () => void
}) {
  const isOutbound = message.direction === "outbound"
  const isNote = message.message_type === "note"
  const isAi = message.message_type === "ai"
  const aiRole = isAi ? String(message.metadata?.role ?? "assistant") : null

  if (isNote || isAi) {
    return (
      <div className="group flex w-full justify-start">
        <div
          className={cn(
            "relative max-w-[80%] animate-pop rounded-none border px-3 py-2 text-xs",
            isNote
              ? "border-amber-500/25 bg-amber-400/[0.07] dark:border-amber-400/20 dark:bg-amber-400/[0.05]"
              : aiRole === "user"
                ? "border-border bg-muted/40"
                : "border-primary/20 bg-primary/[0.06]"
          )}
        >
          <div className="mb-1 flex items-center gap-1.5">
            <span
              className={cn(
                "flex size-4 items-center justify-center [&_svg]:size-3",
                isNote
                  ? "text-amber-500"
                  : aiRole === "user"
                    ? "text-muted-foreground"
                    : "text-primary"
              )}
            >
              {isNote ? <StickyNote /> : <Bot />}
            </span>
            <span className="text-[10px] font-medium text-muted-foreground">
              {isNote
                ? "Note"
                : aiRole === "user"
                  ? "You asked the AI"
                  : "AI assistant"}
            </span>
            <Badge
              variant="outline"
              className="text-[9px] font-normal text-muted-foreground"
            >
              Internal
            </Badge>
          </div>
          <p className="break-words whitespace-pre-wrap">
            {message.content ?? ""}
          </p>
          <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
            <span>{formatDateTime(message.sent_at ?? message.created_at)}</span>
          </div>
          <div className="absolute end-2 -top-2 hidden gap-0.5 group-hover:flex">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="h-6 w-6 shadow-sm"
              onClick={onEdit}
            >
              <Pencil />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="h-6 w-6 text-destructive shadow-sm"
              onClick={onDelete}
            >
              <Trash2 />
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (message.message_type === "template") {
    return (
      <TemplateBubble
        message={message}
        templates={templates}
        onEdit={onEdit}
        onDelete={onDelete}
      />
    )
  }

  return (
    <div
      className={cn(
        "group flex w-full",
        isOutbound ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "relative max-w-[80%] animate-pop rounded-none border px-3 py-2 text-xs",
          isOutbound
            ? "border-primary/20 bg-primary/10"
            : "border-border bg-muted/40"
        )}
      >
        {message.media_url ? (
          <MediaPreview message={message} />
        ) : null}
        {message.content ? (
          <p className="break-words whitespace-pre-wrap">
            {message.content}
          </p>
        ) : null}
        <div
          className={cn(
            "mt-1 flex items-center gap-1 text-[10px] text-muted-foreground",
            isOutbound ? "justify-end" : "justify-start"
          )}
        >
          <span>{formatDateTime(message.sent_at ?? message.created_at)}</span>
          <MessageStatusIcon message={message} />
        </div>
        <div className="absolute end-2 -top-2 hidden gap-0.5 group-hover:flex">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="h-6 w-6 shadow-sm"
            onClick={onEdit}
          >
            <Pencil />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="h-6 w-6 text-destructive shadow-sm"
            onClick={onDelete}
          >
            <Trash2 />
          </Button>
        </div>
      </div>
    </div>
  )
}

type TemplateParameter = {
  type?: string
  text?: string
  [key: string]: unknown
}

type TemplatePayload = {
  name?: string
  language?: { code?: string } | string
  components?: Array<{
    type?: string
    parameters?: TemplateParameter[]
    [key: string]: unknown
  }>
}

function extractTemplatePayload(message: WhatsAppMessage): TemplatePayload | null {
  const metadata = message.metadata ?? {}
  if (metadata.template && typeof metadata.template === "object") {
    return metadata.template as TemplatePayload
  }
  const raw = metadata.raw as Record<string, unknown> | undefined
  if (raw && raw.template && typeof raw.template === "object") {
    return raw.template as TemplatePayload
  }
  return null
}

function templateLanguage(payload: TemplatePayload): string {
  if (typeof payload.language === "string") {
    return payload.language
  }
  return payload.language?.code ?? ""
}

function templateBodyValues(payload: TemplatePayload): Record<string, string> {
  const values: Record<string, string> = {}
  for (const component of payload.components ?? []) {
    if (
      String(component.type ?? "").toUpperCase() === "BODY" &&
      Array.isArray(component.parameters)
    ) {
      component.parameters.forEach((parameter, index) => {
        if (parameter && typeof parameter.text === "string") {
          values[`body:${index + 1}`] = parameter.text
        }
      })
    }
  }
  return values
}

function renderTemplateBody(
  templates: WhatsAppCloudApiTemplate[],
  payload: TemplatePayload
): string {
  const name = payload.name ?? "Template message"
  const language = templateLanguage(payload)
  const template =
    templates.find(
      (item) =>
        item.name === name && (!language || item.language === language)
    ) ?? templates.find((item) => item.name === name)
  const body = template?.components.find(
    (component) => String(component.type ?? "").toUpperCase() === "BODY"
  )
  if (!body || typeof body.text !== "string") {
    return name
  }
  const values = templateBodyValues(payload)
  return body.text.replace(/{{\s*(\d+)\s*}}/g, (_, position: string) => {
    return values[`body:${position}`]?.trim() || `{{${position}}}`
  })
}

function TemplateBubble({
  message,
  templates,
  onEdit,
  onDelete,
}: {
  message: WhatsAppMessage
  templates: WhatsAppCloudApiTemplate[]
  onEdit: () => void
  onDelete: () => void
}) {
  const isOutbound = message.direction === "outbound"
  const payload = extractTemplatePayload(message)
  const name = payload?.name ?? "Template message"
  const language = payload ? templateLanguage(payload) : ""
  const bodyPreview = payload
    ? renderTemplateBody(templates, payload)
    : "Meta template message"

  return (
    <div
      className={cn(
        "group flex w-full",
        isOutbound ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "relative max-w-[80%] animate-pop overflow-hidden rounded-none border text-xs",
          isOutbound
            ? "border-primary/25 bg-primary/10"
            : "border-border bg-muted/40"
        )}
      >
        <div
          className={cn(
            "flex items-center gap-1.5 border-b px-2.5 py-1.5",
            isOutbound
              ? "border-primary/15 bg-primary/[0.06]"
              : "border-border bg-muted/20"
          )}
        >
          <LayoutTemplate className="size-3 shrink-0 text-muted-foreground" />
          <span className="truncate font-mono text-[10px] font-semibold">
            {name}
          </span>
          {language ? (
            <Badge
              variant="outline"
              className="ms-auto shrink-0 text-[8px] font-normal text-muted-foreground"
            >
              {language}
            </Badge>
          ) : null}
        </div>
        <div className="px-2.5 py-2">
          <p className="break-words text-xs leading-relaxed whitespace-pre-wrap text-foreground/85">
            {bodyPreview}
          </p>
          <div className="mt-1.5 flex items-center gap-1 text-[9px] font-medium tracking-wide text-muted-foreground uppercase">
            <FileText className="size-2.5" />
            WhatsApp template
          </div>
        </div>
        <div
          className={cn(
            "flex items-center gap-1 px-2.5 pb-1.5 text-[10px] text-muted-foreground",
            isOutbound ? "justify-end" : "justify-start"
          )}
        >
          <span>{formatDateTime(message.sent_at ?? message.created_at)}</span>
          <MessageStatusIcon message={message} />
        </div>
        <div className="absolute end-2 -top-2 hidden gap-0.5 group-hover:flex">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="h-6 w-6 shadow-sm"
            onClick={onEdit}
          >
            <Pencil />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="h-6 w-6 text-destructive shadow-sm"
            onClick={onDelete}
          >
            <Trash2 />
          </Button>
        </div>
      </div>
    </div>
  )
}

function MediaPreview({ message }: { message: WhatsAppMessage }) {
  const url = message.media_url ?? ""
  const type = (message.metadata?.mime_type as string | undefined) ?? ""
  const filename =
    (message.metadata?.filename as string | undefined) ?? url.split("/").pop()

  const mediaType = type.split("/")[0] ?? ""

  return (
    <div className="mb-2 overflow-hidden border border-black/10 dark:border-white/10">
      {mediaType === "image" ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt={filename ?? "Image"}
          className="max-h-64 w-full object-cover"
          loading="lazy"
        />
      ) : mediaType === "video" ? (
        <video
          src={url}
          controls
          className="max-h-64 w-full object-contain"
          preload="metadata"
        />
      ) : mediaType === "audio" ? (
        <audio src={url} controls className="w-full" preload="metadata" />
      ) : (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 bg-muted/40 px-3 py-2 text-[11px] font-medium hover:underline"
        >
          <FileText className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="truncate">{filename ?? "Download file"}</span>
        </a>
      )}
    </div>
  )
}
