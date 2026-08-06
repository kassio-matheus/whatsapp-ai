"use client"

import * as React from "react"
import {
  Bot,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Send,
  Sparkles,
  Trash2,
  User,
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"
import { cn } from "@workspace/ui/lib/utils"

import { useApp } from "@/components/app-provider"
import { SessionDialog } from "@/components/ai/session-dialog"
import { SystemPromptDialog } from "@/components/ai/system-prompt-dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Markdown } from "@/components/ui/markdown"
import { PageHeader } from "@/components/ui/page-header"
import { SearchInput } from "@/components/ui/search-input"
import { compactPrompt } from "@/lib/token-saver"
import {
  api,
  ApiClientError,
  type ChatMessage,
  type ChatSession,
  type ContextSummary,
} from "@/lib/api"
import { formatDateTime, formatRelative } from "@/lib/format"

export default function AIPage() {
  const { token, companies, currentCompanyId } = useApp()
  const timezone =
    companies.find((company) => company.id === currentCompanyId)?.timezone ??
    "UTC"

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [sessions, setSessions] = React.useState<ChatSession[]>([])
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [messagesLoading, setMessagesLoading] = React.useState(false)
  const [prompt, setPrompt] = React.useState("")
  const [sending, setSending] = React.useState(false)
  const [sessionDialog, setSessionDialog] = React.useState(false)
  const [systemPromptTarget, setSystemPromptTarget] =
    React.useState<ChatSession | null>(null)
  const [contextTarget, setContextTarget] = React.useState<ContextSummary | null>(null)
  const [contextLoading, setContextLoading] = React.useState(false)
  const [deleting, setDeleting] = React.useState<ChatSession | null>(null)
  const [sessionSearch, setSessionSearch] = React.useState("")
  const messagesEndRef = React.useRef<HTMLDivElement>(null)

  const selected = sessions.find((session) => session.id === selectedId) ?? null
  const sessionQuery = sessionSearch.trim().toLowerCase()
  const filteredSessions = React.useMemo(
    () =>
      sessionQuery
        ? sessions.filter((session) =>
            (session.title || "Untitled session")
              .toLowerCase()
              .includes(sessionQuery)
          )
        : sessions,
    [sessions, sessionQuery]
  )

  const loadSessions = React.useCallback(
    async (showLoader = false) => {
      if (!token) {
        return
      }
      if (showLoader) {
        setIsLoading(true)
      }
      try {
        const result = await api.listChatSessions(token)
        setSessions(result)
        setError(null)
        setSelectedId((previous) => {
          if (previous && result.some((session) => session.id === previous)) {
            return previous
          }
          return result[0]?.id ?? null
        })
      } catch (err) {
        if (err instanceof ApiClientError) {
          setError(err.message)
        } else {
          setError("Failed to load sessions.")
        }
      } finally {
        setIsLoading(false)
      }
    },
    [token],
  )

  const loadMessages = React.useCallback(
    async (sessionId: string | null) => {
      if (!token || !sessionId) {
        setMessages([])
        return
      }
      setMessagesLoading(true)
      try {
        const context = await api.getChatContext(sessionId, token)
        setMessages(context.messages)
      } finally {
        setMessagesLoading(false)
      }
    },
    [token],
  )

  React.useEffect(() => {
    void loadSessions(true)
  }, [loadSessions])

  React.useEffect(() => {
    void loadMessages(selectedId)
  }, [selectedId, loadMessages])

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" })
  }, [messages, messagesLoading, sending])

  async function handleSend(event: React.FormEvent) {
    event.preventDefault()
    const content = compactPrompt(prompt)
    if (!token || !selectedId || !content || sending) {
      return
    }
    setSending(true)
    const userMessage: ChatMessage = {
      id: `optimistic-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    }
    setMessages((previous) => [...previous, userMessage])
    setPrompt("")
    try {
      const result = await api.chat(selectedId, content, token)
      const assistantMessage: ChatMessage = {
        id: `optimistic-${Date.now()}-a`,
        role: "assistant",
        content: result.response,
        created_at: new Date().toISOString(),
      }
      setMessages((previous) => [...previous, assistantMessage])
    } catch (err) {
      const failedMessage: ChatMessage = {
        id: `optimistic-${Date.now()}-e`,
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Something went wrong."}`,
        created_at: new Date().toISOString(),
      }
      setMessages((previous) => [...previous, failedMessage])
    } finally {
      setSending(false)
    }
  }

  async function handleDelete() {
    if (!token || !deleting) {
      return
    }
    await api.deleteChatSession(deleting.id, token)
    setSessions((previous) =>
      previous.filter((session) => session.id !== deleting.id),
    )
    if (selectedId === deleting.id) {
      setSelectedId(null)
    }
    setDeleting(null)
  }

  async function openContext(sessionId: string) {
    if (!token) {
      return
    }
    setContextLoading(true)
    setContextTarget(null)
    try {
      const context = await api.getChatContext(sessionId, token)
      setContextTarget(context)
    } finally {
      setContextLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-full flex-col gap-4 p-4 md:p-6">
        <Skeleton className="h-6 w-40 rounded-none" />
        <div className="grid flex-1 gap-3 lg:grid-cols-[300px_1fr]">
          <Skeleton className="h-[520px] rounded-none" />
          <Skeleton className="h-[520px] rounded-none" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4 md:p-6">
      <PageHeader
        title="AI Chat"
        description="Chat with an AI assistant that remembers the conversation context."
      >
        <Button
          onClick={() => {
            setSessionDialog(true)
          }}
        >
          <Plus />
          New session
        </Button>
      </PageHeader>

      {error ? (
        <Card className="p-0">
          <EmptyState
            title="Something went wrong"
            description={error}
            action={
              <Button variant="outline" onClick={() => void loadSessions(true)}>
                Retry
              </Button>
            }
          />
        </Card>
      ) : sessions.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={<Bot />}
            title="No sessions yet"
            description="Create a chat session to start a conversation with the AI assistant."
            action={
              <Button
                onClick={() => {
                  setSessionDialog(true)
                }}
              >
                <Plus />
                New session
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid min-h-0 max-h-[80vh] flex-1 gap-3 lg:grid-cols-[300px_1fr]">
          <Card className="flex min-h-0 flex-col p-0">
            <div className="border-b p-2">
              <SearchInput
                value={sessionSearch}
                onValueChange={setSessionSearch}
                placeholder="Search sessions…"
                shortcut="/"
              />
              <p className="mt-1.5 text-[10px] text-muted-foreground tabular-nums">
                {filteredSessions.length} of {sessions.length} sessions
              </p>
            </div>
            <ScrollArea className="flex-1">
              <ul className="flex flex-col">
                {filteredSessions.map((session, index) => {
                  const isActive = session.id === selectedId
                  return (
                    <li
                      key={session.id}
                      className="stagger-enter"
                      style={{ animationDelay: `${index * 30}ms` }}
                    >
                      <div
                        className={cn(
                          "flex items-center gap-1 border-b px-2 py-2 transition-colors hover:bg-accent",
                          isActive && "bg-accent",
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedId(session.id)}
                          className="flex min-w-0 flex-1 flex-col gap-0.5 px-1 py-1 text-start outline-none"
                        >
                          <span className="truncate text-xs font-medium">
                            {session.title || "Untitled session"}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {session.message_count} messages ·{" "}
                            {formatRelative(session.created_at)}
                          </span>
                        </button>
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
                              onClick={() => setSystemPromptTarget(session)}
                            >
                              <Pencil />
                              System prompt
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => void openContext(session.id)}
                            >
                              <Sparkles />
                              View context
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => setDeleting(session)}
                            >
                              <Trash2 />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </ScrollArea>
          </Card>

          <Card className="flex min-h-0 flex-col p-0">
            {!selected ? (
              <EmptyState
                title="Select a session"
                description="Choose a session from the list to start chatting."
              />
            ) : (
              <>
                <div className="flex items-center justify-between gap-2 border-b px-3 py-2.5">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate text-xs font-medium">
                      {selected.title || "Untitled session"}
                    </span>
                    {selected.system_prompt ? (
                      <Badge variant="outline" className="text-[10px]">
                        Custom prompt
                      </Badge>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setSystemPromptTarget(selected)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => void openContext(selected.id)}
                    >
                      <Sparkles />
                    </Button>
                  </div>
                </div>

                <ScrollArea className="min-h-0 flex-1">
                  <div className="flex flex-col gap-3 p-4">
                    {messagesLoading ? (
                      <div className="flex justify-center py-10 text-muted-foreground">
                        <LoaderCircle className="size-4 animate-spin" />
                      </div>
                    ) : messages.length === 0 ? (
                      <p className="py-10 text-center text-xs text-muted-foreground">
                        Start the conversation. The assistant has access to the
                        session context.
                      </p>
                    ) : (
                      messages.map((message) => (
<ChatBubble
                          key={message.id}
                          message={message}
                          timezone={timezone}
                        />
                      ))
                    )}
                    {sending ? <TypingIndicator /> : null}
                    <div ref={messagesEndRef} />
                  </div>
                </ScrollArea>

                <form
                  onSubmit={(event) => void handleSend(event)}
                  className="flex items-end gap-2 border-t p-3"
                >
                  <textarea
                    value={prompt}
                    onChange={(event) => setPrompt(event.target.value)}
                    placeholder="Ask anything…"
                    rows={1}
                    className="min-h-9 flex-1 resize-none rounded-none border border-input bg-transparent px-2.5 py-2 text-xs focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault()
                        event.currentTarget.form?.requestSubmit()
                      }
                    }}
                  />
                  <Button
                    type="submit"
                    size="icon"
                    disabled={sending || !prompt.trim()}
                  >
                    {sending ? (
                      <LoaderCircle className="animate-spin" />
                    ) : (
                      <Send />
                    )}
                  </Button>
                </form>
              </>
            )}
          </Card>
        </div>
      )}

      <SessionDialog
        open={sessionDialog}
        onOpenChange={setSessionDialog}
        onSave={async (data) => {
          if (!token) {
            return
          }
          const created = await api.createChatSession(data, token)
          setSessions((previous) => [...previous, created])
          setSelectedId(created.id)
        }}
      />

      <SystemPromptDialog
        session={systemPromptTarget}
        onOpenChange={(open) => {
          if (!open) {
            setSystemPromptTarget(null)
          }
        }}
        onSave={async (sessionId, systemPrompt) => {
          if (!token) {
            return
          }
          const result = await api.updateSystemPrompt(
            sessionId,
            systemPrompt,
            token,
          )
          setSessions((previous) =>
            previous.map((session) =>
              session.id === sessionId
                ? { ...session, system_prompt: result.system_prompt }
                : session,
            ),
          )
        }}
        onClear={async (sessionId) => {
          if (!token) {
            return
          }
          const result = await api.deleteSystemPrompt(sessionId, token)
          setSessions((previous) =>
            previous.map((session) =>
              session.id === sessionId
                ? { ...session, system_prompt: result.system_prompt }
                : session,
            ),
          )
        }}
      />

      <Sheet
        open={contextTarget !== null || contextLoading}
        onOpenChange={(open) => {
          if (!open) {
            setContextTarget(null)
          }
        }}
      >
        <SheetContent side="right">
          <SheetHeader>
            <SheetTitle>Session context</SheetTitle>
            <SheetDescription>
              The summarized context used by the assistant for this session.
            </SheetDescription>
          </SheetHeader>
          <div className="flex flex-col gap-4 p-4">
            {contextLoading ? (
              <div className="flex justify-center py-10 text-muted-foreground">
                <LoaderCircle className="size-4 animate-spin" />
              </div>
            ) : contextTarget ? (
              <>
                <div className="flex flex-col gap-2">
                  <h3 className="text-xs font-medium">Summary</h3>
                  <p className="whitespace-pre-wrap rounded-none border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                    {contextTarget.context_summary ??
                      "No summary available yet."}
                  </p>
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="text-xs font-medium">
                    Recent messages ({contextTarget.messages.length})
                  </h3>
                  <div className="flex flex-col gap-2">
                    {contextTarget.messages.map((message) => (
                      <ChatBubble
                        key={message.id}
                        message={message}
                        timezone={timezone}
                      />
                    ))}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleting(null)
          }
        }}
        title="Delete session"
        description={`Delete "${deleting?.title ?? "this session"}" and all of its messages?`}
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex w-full justify-start gap-2">
      <span className="mt-1 flex size-6 shrink-0 items-center justify-center rounded-full border bg-muted/40 [&_svg]:size-3">
        <Bot />
      </span>
      <div className="flex items-center gap-1 rounded-none border border-border bg-background px-3 py-3">
        <span className="animate-typing size-1.5 rounded-full bg-muted-foreground" />
        <span className="animate-typing size-1.5 rounded-full bg-muted-foreground [animation-delay:0.15s]" />
        <span className="animate-typing size-1.5 rounded-full bg-muted-foreground [animation-delay:0.3s]" />
      </div>
    </div>
  )
}

function ChatBubble({
  message,
  timezone = "UTC",
}: {
  message: ChatMessage
  timezone?: string
}) {
  const isUser = message.role === "user"
  const isSystem = message.role === "system"
  return (
    <div
      className={cn(
        "flex w-full gap-2",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      {!isUser ? (
        <span className="animate-pop mt-1 flex size-6 shrink-0 items-center justify-center rounded-full border bg-muted/40 [&_svg]:size-3">
          {isSystem ? <Sparkles /> : <Bot />}
        </span>
      ) : null}
      <div
        className={cn(
          "animate-pop max-w-[75%] rounded-none border px-3 py-2 text-xs",
          isUser
            ? "border-primary/20 bg-primary/10"
            : isSystem
              ? "border-border bg-muted/30"
              : "border-border bg-background",
        )}
      >
        <Markdown content={message.content} />
        <span className="mt-1 block text-[10px] text-muted-foreground">
          {formatDateTime(message.created_at, timezone)}
        </span>
      </div>
      {isUser ? (
        <span className="mt-1 flex size-6 shrink-0 items-center justify-center rounded-full border bg-primary/10 text-primary [&_svg]:size-3">
          <User />
        </span>
      ) : null}
    </div>
  )
}
