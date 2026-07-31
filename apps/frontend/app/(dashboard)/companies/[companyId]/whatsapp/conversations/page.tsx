"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import {
  Check,
  CheckCheck,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Radio,
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
import { cn } from "@workspace/ui/lib/utils"

import { useApp } from "@/components/app-provider"
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
  type ConversationStatus,
  type WhatsAppContact,
  type WhatsAppConversation,
  type WhatsAppIntegration,
  type WhatsAppMessage,
} from "@/lib/api"
import { formatDateTime } from "@/lib/format"

const STATUS_BADGE: Record<ConversationStatus, { label: string; variant: "secondary" | "outline" | "default" }> = {
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
  const [conversations, setConversations] = React.useState<WhatsAppConversation[]>([])
  const [integrations, setIntegrations] = React.useState<WhatsAppIntegration[]>([])
  const [contacts, setContacts] = React.useState<WhatsAppContact[]>([])
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [messages, setMessages] = React.useState<WhatsAppMessage[]>([])
  const [messagesLoading, setMessagesLoading] = React.useState(false)
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editingConversation, setEditingConversation] =
    React.useState<WhatsAppConversation | null>(null)
  const [editingMessage, setEditingMessage] = React.useState<WhatsAppMessage | null>(null)
  const [deletingConversation, setDeletingConversation] =
    React.useState<WhatsAppConversation | null>(null)
  const [deletingMessage, setDeletingMessage] = React.useState<WhatsAppMessage | null>(null)

  const selected = conversations.find((conversation) => conversation.id === selectedId) ?? null

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
            api.listIntegrations(token, companyId),
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
    [token, companyId],
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
    [token],
  )

  React.useEffect(() => {
    void loadConversations(true)
  }, [loadConversations])

  React.useEffect(() => {
    void loadMessages(selectedId, true)
  }, [selectedId, loadMessages])

  React.useEffect(() => {
    if (!token) {
      return
    }
    const interval = window.setInterval(() => {
      void loadConversations()
      if (selectedId) {
        void loadMessages(selectedId)
      }
    }, 4000)
    return () => window.clearInterval(interval)
  }, [loadConversations, loadMessages, selectedId, token])

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
      token,
    )
    setMessages((previous) => [...previous, created])
    void loadConversations()
  }

  async function handleDeleteConversation() {
    if (!token || !deletingConversation) {
      return
    }
    await api.deleteConversation(deletingConversation.id, token)
    setConversations((previous) =>
      previous.filter((conversation) => conversation.id !== deletingConversation.id),
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
      previous.filter((message) => message.id !== deletingMessage.id),
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
            <Button variant="outline" onClick={() => void loadConversations(true)}>
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
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
                {conversations.map((conversation) => {
                  const contact = contacts.find(
                    (c) => c.id === conversation.contact_id,
                  )
                  const integration = integrations.find(
                    (i) => i.id === conversation.integration_id,
                  )
                  const isActive = conversation.id === selectedId
                  return (
                    <li key={conversation.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(conversation.id)}
                        className={cn(
                          "flex w-full flex-col gap-1 border-b px-3 py-3 text-start outline-none transition-colors hover:bg-accent",
                          isActive && "bg-accent",
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
                          {integration?.name ?? "Unknown integration"}
                          {contact?.phone_number ? ` · ${contact.phone_number}` : ""}
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
                        contacts.find((c) => c.id === selected.contact_id)?.name ??
                        "Untitled conversation"}
                    </span>
                    <StatusBadge status={selected.status} />
                  </div>
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
                  onSend={handleSendMessage}
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
              token,
            )
            setConversations((previous) =>
              previous.map((item) => (item.id === updated.id ? updated : item)),
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
          const updated = await api.updateMessage(editingMessage.id, data, token)
          setMessages((previous) =>
            previous.map((item) => (item.id === updated.id ? updated : item)),
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
  onEdit,
  onDelete,
}: {
  message: WhatsAppMessage
  onEdit: () => void
  onDelete: () => void
}) {
  const isOutbound = message.direction === "outbound"
  return (
    <div
      className={cn(
        "group flex w-full",
        isOutbound ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "relative max-w-[80%] rounded-none border px-3 py-2 text-xs",
          isOutbound
            ? "border-primary/20 bg-primary/10"
            : "border-border bg-muted/40",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content ?? message.media_url ?? ""}</p>
        <div
          className={cn(
            "mt-1 flex items-center gap-1 text-[10px] text-muted-foreground",
            isOutbound ? "justify-end" : "justify-start",
          )}
        >
          <span>{formatDateTime(message.sent_at ?? message.created_at)}</span>
          <MessageStatusIcon message={message} />
        </div>
        <div className="absolute -top-2 end-2 hidden gap-0.5 group-hover:flex">
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
