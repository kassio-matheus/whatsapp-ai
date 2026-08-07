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
  Search,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Switch } from "@workspace/ui/components/switch"
import { cn } from "@workspace/ui/lib/utils"

import { useApp } from "@/components/app-provider"
import { WhatsAppSectionTabs } from "@/components/whatsapp/whatsapp-section-tabs"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Markdown } from "@/components/ui/markdown"
import { PageHeader } from "@/components/ui/page-header"
import { SearchInput } from "@/components/ui/search-input"
import { ConversationDialog } from "@/components/whatsapp/conversation-dialog"
import { compactPrompt } from "@/lib/token-saver"
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
import { useDebouncedValue } from "@/lib/use-debounced-value"
import { useInfiniteScroll } from "@/lib/use-infinite-scroll"

const CONVERSATIONS_PAGE_SIZE = 100
const MESSAGES_PAGE_SIZE = 100

import { useQueryState } from "nuqs"

const STATUS_BADGE: Record<
  ConversationStatus,
  { label: string; variant: "secondary" | "outline" | "default" }
> = {
  open: { label: "Open", variant: "secondary" },
  pending: { label: "Pending", variant: "outline" },
  closed: { label: "Closed", variant: "default" },
}

// Shared between the filter <Select>'s `items` prop and its rendered
// <SelectItem> children so the two never drift out of sync.
const STATUS_FILTER_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "pending", label: "Pending" },
  { value: "closed", label: "Closed" },
] as const

// Payload shape for a new outbound/inbound message. Hoisted out of
// handleSendMessage so it isn't redeclared on every call.
interface OutgoingMessagePayload {
  conversation_id: string
  direction: "inbound" | "outbound"
  external_id?: string
  message_type?: string
  content?: string
  media_url?: string
  metadata?: Record<string, unknown>
  status: "pending" | "sent" | "delivered" | "read" | "failed"
  sent_at?: string
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
  const { token, companies } = useApp()
  const companyId = params.companyId
  const timezone = React.useMemo(
    () =>
      companies.find((company) => company.id === companyId)?.timezone ?? "UTC",
    [companies, companyId]
  )

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [conversations, setConversations] = React.useState<
    WhatsAppConversation[]
  >([])
  const [integrations, setIntegrations] = React.useState<WhatsAppIntegration[]>(
    []
  )
  const [contacts, setContacts] = React.useState<WhatsAppContact[]>([])
  const [selectedId, setSelectedId] = useQueryState("conversation", {
    history: "replace",
  })
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
  const [companyAiEnabled, setCompanyAiEnabled] = React.useState<
    boolean | null
  >(null)
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
  const [search, setSearch] = useQueryState("q", {
    defaultValue: "",
    history: "replace",
  })
  const [statusFilter, setStatusFilter] = useQueryState("status", {
    defaultValue: "all",
    history: "replace",
  })
  const [searching, setSearching] = React.useState(false)

  // Pagination state: the conversation sidebar and the message timeline both
  // load in pages and append older items as the operator scrolls.
  const [conversationsHasMore, setConversationsHasMore] = React.useState(true)
  const [conversationsLoadingMore, setConversationsLoadingMore] =
    React.useState(false)
  const [messagesHasMore, setMessagesHasMore] = React.useState(false)
  const [messagesLoadingMore, setMessagesLoadingMore] = React.useState(false)
  const conversationsOffsetRef = React.useRef(0)
  const messagesOffsetRef = React.useRef(0)
  const conversationsLoadingMoreRef = React.useRef(false)
  const messagesLoadingMoreRef = React.useRef(false)
  const olderMessagesRef = React.useRef<WhatsAppMessage[]>([])
  const olderMessagesConversationRef = React.useRef<string | null>(null)

  // Older auto-replies were stored twice (an internal "ai" draft plus the
  // delivered text). Skip the internal drafts so the reply appears exactly
  // once, while keeping the operator-initiated AI drafts ("You asked the AI").
  const visibleMessages = React.useMemo(
    () =>
      messages.filter(
        (message) =>
          !(
            message.message_type === "ai" &&
            message.metadata?.ai_kind === "auto_reply"
          )
      ),
    [messages]
  )

  // --- Data-race guards -----------------------------------------------
  // Two *independent* counters per resource:
  //  - the "Seq" ref guards which async response is allowed to write state
  //    (applies to every call: initial load, background SSE/poll refreshes,
  //    user-driven search).
  //  - the "LoaderSeq" ref guards only the spinner/skeleton flag, and is
  //    bumped exclusively by calls made with showLoader=true.
  // Splitting these was the fix for the main bug: background refreshes (SSE
  // events, the 10s poll) call load*(…) with showLoader=false but still used
  // to bump the *same* counter the spinner relied on. If one of those fired
  // while the initial showLoader=true load was still in flight, the initial
  // call's `finally` block would find the shared counter had moved on and
  // would skip clearing isLoading/messagesLoading — even though the data
  // itself loaded and was applied correctly. The page would then sit on the
  // skeleton/spinner forever: no error, no failed request, just a stuck
  // loading flag hiding perfectly good data.
  const loadConversationsSeqRef = React.useRef(0)
  const conversationsLoaderSeqRef = React.useRef(0)
  const loadMessagesSeqRef = React.useRef(0)
  const messagesLoaderSeqRef = React.useRef(0)

  const messagesViewportRef = React.useRef<HTMLDivElement | null>(null)
  const stickToBottomRef = React.useRef(true)

  // Keeps the latest selected conversation available to long-lived
  // callbacks (the SSE subscription, the poll interval) without those
  // effects needing to depend on selectedId and therefore reconnect every
  // time the operator switches conversations.
  const selectedIdRef = React.useRef<string | null>(null)
  React.useEffect(() => {
    selectedIdRef.current = selectedId
  }, [selectedId])

  const handleMessagesViewportScroll = React.useCallback(() => {
    const viewport = messagesViewportRef.current
    if (!viewport) {
      return
    }
    const distanceFromBottom =
      viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
    stickToBottomRef.current = distanceFromBottom < 80
  }, [])

  const setMessagesViewport = React.useCallback(
    (node: HTMLDivElement | null) => {
      const previous = messagesViewportRef.current
      if (previous) {
        previous.removeEventListener("scroll", handleMessagesViewportScroll)
      }
      messagesViewportRef.current = node
      if (node) {
        node.addEventListener("scroll", handleMessagesViewportScroll, {
          passive: true,
        })
      }
    },
    [handleMessagesViewportScroll]
  )

  const scrollMessagesToBottom = React.useCallback(() => {
    const viewport = messagesViewportRef.current
    if (viewport) {
      viewport.scrollTop = viewport.scrollHeight
    }
  }, [])

  React.useEffect(() => {
    if (stickToBottomRef.current) {
      scrollMessagesToBottom()
    }
  }, [visibleMessages, scrollMessagesToBottom])

  React.useEffect(() => {
    stickToBottomRef.current = true
  }, [selectedId])

  const selected =
    conversations.find((conversation) => conversation.id === selectedId) ?? null

  // Keeps the active search/status filters applied on background refreshes
  // (SSE events and the polling fallback), so the list never "resets".
  const activeFiltersRef = React.useRef<{
    search?: string
    status?: string
  }>({})

  const loadConversations = React.useCallback(
    async (
      showLoader = false,
      filters?: { search?: string; status?: string }
    ) => {
      if (!token) {
        return
      }
      if (filters) {
        activeFiltersRef.current = filters
      }
      const effectiveFilters = filters ?? activeFiltersRef.current
      const isUserDriven = Boolean(filters)
      const seq = ++loadConversationsSeqRef.current
      const loaderSeq = showLoader ? ++conversationsLoaderSeqRef.current : null

      if (showLoader) {
        setIsLoading(true)
      }
      if (
        isUserDriven &&
        (effectiveFilters.search || effectiveFilters.status)
      ) {
        setSearching(true)
      }
      try {
        const [conversationsResult, integrationsResult, contactsResult] =
          await Promise.all([
            api.listConversations(token, {
              company_id: companyId,
              search: effectiveFilters.search,
              status: effectiveFilters.status,
              limit: CONVERSATIONS_PAGE_SIZE,
            }),
            api.listInstances(token, { company_id: companyId }),
            api.listContacts(token, { company_id: companyId, limit: 200 }),
          ])
        if (loadConversationsSeqRef.current === seq) {
          setConversations(conversationsResult)
          setIntegrations(integrationsResult)
          setContacts(contactsResult)
          setError(null)
          setSearching(false)
          // A full reload resets pagination: the sidebar starts from the
          // newest page and any older pages the user already scrolled get
          // discarded (they will be re-fetched when scrolling resumes).
          conversationsOffsetRef.current = conversationsResult.length
          setConversationsHasMore(
            conversationsResult.length >= CONVERSATIONS_PAGE_SIZE
          )
          setConversationsLoadingMore(false)
          setSelectedId((previous) => {
            if (
              previous &&
              conversationsResult.some((c) => c.id === previous)
            ) {
              return previous
            }
            return conversationsResult[0]?.id ?? null
          })
        }
      } catch (err) {
        if (loadConversationsSeqRef.current === seq) {
          if (err instanceof ApiClientError) {
            setError(err.message)
          } else {
            setError("Failed to load conversations.")
          }
          setSearching(false)
        }
      } finally {
        if (
          loaderSeq !== null &&
          conversationsLoaderSeqRef.current === loaderSeq
        ) {
          setIsLoading(false)
        }
      }
    },
    [token, companyId, setSelectedId]
  )

  const loadMoreConversations = React.useCallback(async () => {
    if (!token) {
      return
    }
    if (conversationsLoadingMoreRef.current) {
      return
    }
    const seq = ++loadConversationsSeqRef.current
    conversationsLoadingMoreRef.current = true
    setConversationsLoadingMore(true)
    const offset = conversationsOffsetRef.current
    const filters = activeFiltersRef.current
    try {
      const result = await api.listConversations(token, {
        company_id: companyId,
        search: filters.search,
        status: filters.status,
        limit: CONVERSATIONS_PAGE_SIZE,
        offset,
      })
      if (loadConversationsSeqRef.current === seq) {
        conversationsOffsetRef.current = offset + result.length
        setConversationsHasMore(result.length >= CONVERSATIONS_PAGE_SIZE)
        setConversations((previous) => {
          const knownIds = new Set(previous.map((item) => item.id))
          return [
            ...previous,
            ...result.filter((item) => !knownIds.has(item.id)),
          ]
        })
      }
    } catch {
      // A failed load-more leaves the already-loaded list untouched; the
      // observer will simply retry the next time the edge is in view.
    } finally {
      conversationsLoadingMoreRef.current = false
      setConversationsLoadingMore(false)
    }
  }, [token, companyId])

  const loadMessages = React.useCallback(
    async (conversationId: string | null, showLoader = false) => {
      if (!token || !conversationId) {
        loadMessagesSeqRef.current += 1
        messagesLoaderSeqRef.current += 1
        setMessages([])
        setMessagesLoading(false)
        return
      }
      const requestSeq = ++loadMessagesSeqRef.current
      const loaderSeq = showLoader ? ++messagesLoaderSeqRef.current : null
      if (showLoader) {
        setMessagesLoading(true)
      }
      try {
        const result = await api.listConversationMessages(
          companyId,
          conversationId,
          token,
          { limit: MESSAGES_PAGE_SIZE }
        )
        // SSE events, the poll fallback and optimistic updates can fire several
        // overlapping reloads. Only the newest request may write the list, or a
        // stale response (fetched before the AI reply was committed) would
        // overwrite newer messages and make the latest message "disappear".
        if (loadMessagesSeqRef.current === requestSeq) {
          if (olderMessagesConversationRef.current !== conversationId) {
            olderMessagesConversationRef.current = conversationId
            olderMessagesRef.current = []
          }
          // Rebuild the timeline without discarding pages the operator scrolled
          // up to: older messages are kept (deduped against the newest page) so
          // background refreshes never yank the scroll position back to bottom.
          const newestIds = new Set(result.map((message) => message.id))
          const keptOlder = olderMessagesRef.current.filter(
            (message) => !newestIds.has(message.id)
          )
          olderMessagesRef.current = keptOlder
          messagesOffsetRef.current = keptOlder.length + result.length
          setMessagesHasMore(
            result.length >= MESSAGES_PAGE_SIZE || keptOlder.length > 0
          )
          setMessagesLoadingMore(false)
          setMessages([...keptOlder, ...result])
        }
      } finally {
        if (loaderSeq !== null && messagesLoaderSeqRef.current === loaderSeq) {
          setMessagesLoading(false)
        }
      }
    },
    [token, companyId]
  )

  const loadMoreMessages = React.useCallback(async () => {
    if (!token || !selectedId) {
      return
    }
    if (messagesLoadingMoreRef.current || !messagesHasMore) {
      return
    }
    const requestSeq = ++loadMessagesSeqRef.current
    messagesLoadingMoreRef.current = true
    setMessagesLoadingMore(true)
    const offset = messagesOffsetRef.current
    try {
      const result = await api.listConversationMessages(
        companyId,
        selectedId,
        token,
        { limit: MESSAGES_PAGE_SIZE, offset }
      )
      if (loadMessagesSeqRef.current === requestSeq) {
        if (result.length === 0) {
          setMessagesHasMore(false)
          return
        }
        olderMessagesRef.current = [
          ...olderMessagesRef.current,
          ...result.filter(
            (message) =>
              !olderMessagesRef.current.some(
                (existing) => existing.id === message.id
              )
          ),
        ]
        messagesOffsetRef.current = offset + result.length
        setMessagesHasMore(result.length >= MESSAGES_PAGE_SIZE)
        setMessages((previous) => {
          const knownIds = new Set(previous.map((message) => message.id))
          const older = olderMessagesRef.current.filter(
            (message) => !knownIds.has(message.id)
          )
          return older.length > 0 ? [...older, ...previous] : previous
        })
      }
    } catch {
      // Keep the loaded timeline; the sentinel retries when scrolled again.
    } finally {
      messagesLoadingMoreRef.current = false
      setMessagesLoadingMore(false)
    }
  }, [token, companyId, selectedId, messagesHasMore])

  const conversationsSentinelRef = useInfiniteScroll<HTMLLIElement>({
    hasMore: conversationsHasMore,
    loading: conversationsLoadingMore,
    onLoadMore: () => void loadMoreConversations(),
    rootMargin: "240px",
  })

  const messagesOlderSentinelRef = useInfiniteScroll({
    hasMore: messagesHasMore,
    loading: messagesLoadingMore,
    onLoadMore: () => void loadMoreMessages(),
    rootMargin: "240px",
  })

  // The URL may already carry a search term or status (shared link or a page
  // reload). Capture it on the first render so the initial load applies it
  // instead of returning an unfiltered inbox on top of active query params.
  const initialFiltersRef = React.useRef({
    search: search.trim() || undefined,
    status: statusFilter === "all" ? undefined : statusFilter,
  })

  React.useEffect(() => {
    const initial = initialFiltersRef.current
    void loadConversations(true, {
      search: initial.search,
      status: initial.status,
    })
  }, [loadConversations])

  const debouncedSearch = useDebouncedValue(search, 300)
  const trimmedSearch = debouncedSearch.trim()

  const skipFirstRenderRef = React.useRef(true)
  React.useEffect(() => {
    if (skipFirstRenderRef.current) {
      skipFirstRenderRef.current = false
      return
    }
    void loadConversations(false, {
      search: trimmedSearch || undefined,
      status: statusFilter === "all" ? undefined : statusFilter,
    })
  }, [trimmedSearch, statusFilter, loadConversations])

  React.useEffect(() => {
    if (!token) {
      setCompanyAiEnabled(false)
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

  // Subscribes once per company/token instead of reconnecting on every
  // conversation switch — selectedIdRef (kept fresh above) supplies the
  // current conversation to the long-lived SSE/poll callbacks below.
  React.useEffect(() => {
    if (!token) {
      return
    }
    const unsubscribe = subscribeToWhatsAppEvents({
      companyId,
      token,
      onEvent: (event) => {
        void loadConversations()
        const currentId = selectedIdRef.current
        if (
          currentId &&
          (!event.conversation_id || event.conversation_id === currentId)
        ) {
          void loadMessages(currentId)
        }
      },
    })
    // Polling fallback: SSE is process-local, so with multiple backend workers
    // events may not reach this tab. A lightweight refresh keeps the inbox and
    // the open conversation up to date either way.
    const poll = window.setInterval(() => {
      void loadConversations()
      const currentId = selectedIdRef.current
      if (currentId) {
        void loadMessages(currentId)
      }
    }, 10_000)
    return () => {
      unsubscribe()
      window.clearInterval(poll)
    }
  }, [companyId, loadConversations, loadMessages, token])

  async function handleSendMessage(data: ComposerMessageData) {
    if (!token || !selectedId) {
      return
    }

    const message: OutgoingMessagePayload = {
      conversation_id: selectedId,
      direction: "outbound",
      message_type: data.message_type,
      content: data.content,
      media_url: data.media_url,
      metadata: data.metadata,
      status: "pending",
    }

    const tempId = `temp-${Date.now()}`

    const generated_message: WhatsAppMessage = {
      id: tempId,
      created_at: new Date().toISOString(),
      sent_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_active: true,
      company_id: companyId,
      instance_id: selected?.instance_id ?? "",
      content: message.content ?? "",
      media_url: message.media_url ?? "",
      direction: message.direction,
      message_type: message.message_type ?? "text",
      status: message.status,
      metadata: message.metadata ?? {},
      external_id: message.external_id ?? null,
      conversation_id: selectedId,
    }

    // Optimistic insert.
    setMessages((previous) =>
      previous.some((m) => m.id === generated_message.id)
        ? previous
        : [...previous, generated_message]
    )

    try {
      const created = await api.createMessage(message, token)

      // Swap the optimistic message in place (replace the temp id with the
      // real one and sync status) instead of trying to add it again.
      setMessages((previous) =>
        previous.map((m) =>
          m.id === tempId
            ? {
                ...m,
                ...(created ?? {}),
                id: created?.id ?? m.id,
                status: created?.status ?? "sent",
              }
            : m
        )
      )

      void loadConversations()
    } catch {
      setMessages((previous) =>
        previous.map((m) => (m.id === tempId ? { ...m, status: "failed" } : m))
      )
    }
  }

  async function handleCreateNote(content: string) {
    if (!token || !selectedId) {
      return
    }
    const created = await api.createNote(selectedId, content, token)
    setMessages((previous) =>
      previous.some((message) => message.id === created.id)
        ? previous
        : [...previous, created]
    )
    void loadConversations()
  }

  async function handleAskAi(prompt: string) {
    if (!token || !selectedId) {
      return
    }
    setAiPending(true)
    try {
      const result = await api.askAi(selectedId, compactPrompt(prompt), token)
      setMessages((previous) => {
        const next = [...previous]
        for (const message of [result.prompt_message, result.message]) {
          if (!next.some((item) => item.id === message.id)) {
            next.push(message)
          }
        }
        return next
      })
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
    const upload = await api.uploadWhatsAppMedia(file, companyId, token)
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
          icon={trimmedSearch || statusFilter !== "all" ? <Search /> : <Plus />}
          title={
            trimmedSearch || statusFilter !== "all"
              ? "No matching conversations"
              : "No conversations yet"
          }
          description={
            trimmedSearch || statusFilter !== "all"
              ? "Try a different search term or filter."
              : "Create a conversation to start messaging a contact."
          }
          action={
            trimmedSearch || statusFilter !== "all" ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearch("")
                  setStatusFilter("all")
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Button
                onClick={() => {
                  setEditingConversation(null)
                  setDialogOpen(true)
                }}
              >
                <Plus />
                New conversation
              </Button>
            )
          }
        />
      ) : (
        <div className="grid h-[75dvh] gap-3 lg:grid-cols-[320px_1fr]">
          <Card className="p-0">
            <div className="flex flex-col gap-2 border-b p-2">
              <SearchInput
                value={search}
                onValueChange={setSearch}
                placeholder="Search by phone or title…"
                loading={searching}
                shortcut="/"
              />
              <div className="flex items-center justify-between gap-2">
                <Select
                  items={STATUS_FILTER_OPTIONS}
                  value={statusFilter}
                  onValueChange={(value) => setStatusFilter(String(value))}
                >
                  <SelectTrigger className="h-7 w-36 py-1 text-[11px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_FILTER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="text-[10px] text-muted-foreground tabular-nums">
                  {conversations.length}{" "}
                  {conversations.length === 1
                    ? "conversation"
                    : "conversations"}
                </span>
              </div>
            </div>
            <ScrollArea className="h-[472px]">
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
                            {formatDateTime(
                              conversation.last_message_at,
                              timezone
                            )}
                          </span>
                        ) : null}
                      </button>
                    </li>
                  )
                })}
                {conversationsLoadingMore ? (
                  <li className="flex justify-center px-3 py-3 text-muted-foreground">
                    <LoaderCircle className="size-4 animate-spin" />
                  </li>
                ) : null}
                <li
                  ref={conversationsSentinelRef}
                  aria-hidden="true"
                  className="h-px w-full"
                />
              </ul>
            </ScrollArea>
          </Card>

          <Card className="flex flex-col p-0">
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

                <ScrollArea
                  viewportRef={setMessagesViewport}
                  className="min-h-0 flex-1"
                >
                  <div className="flex flex-col gap-2 p-3">
                    <div
                      ref={messagesOlderSentinelRef}
                      aria-hidden="true"
                      className="h-px w-full shrink-0"
                    />
                    {messagesLoadingMore ? (
                      <div className="flex justify-center py-2 text-muted-foreground">
                        <LoaderCircle className="size-4 animate-spin" />
                      </div>
                    ) : null}
                    {messagesLoading ? (
                      <div className="flex justify-center py-8 text-muted-foreground">
                        <LoaderCircle className="size-4 animate-spin" />
                      </div>
                    ) : visibleMessages.length === 0 ? (
                      <p className="py-8 text-center text-xs text-muted-foreground">
                        No messages yet. Send the first one below.
                      </p>
                    ) : (
                      visibleMessages.map((message) => (
                        <MessageBubble
                          key={message.id}
                          message={message}
                          timezone={timezone}
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
  timezone = "UTC",
  templates = [],
  onEdit,
  onDelete,
}: {
  message: WhatsAppMessage
  timezone?: string
  templates?: WhatsAppCloudApiTemplate[]
  onEdit: () => void
  onDelete: () => void
}) {
  const isOutbound = message.direction === "outbound"
  const isNote = message.message_type === "note"
  const isAi = message.message_type === "ai"
  const isAutoReply = message.metadata?.ai_kind === "auto_reply"
  const aiRole = isAi ? String(message.metadata?.role ?? "assistant") : null

  if (isNote || isAi) {
    return (
      <div className="group flex w-full justify-end">
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
          {isNote ? (
            <p className="break-words whitespace-pre-wrap">
              {message.content ?? ""}
            </p>
          ) : (
            <Markdown content={message.content ?? ""} />
          )}
          <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
            <span>
              {formatDateTime(message.sent_at ?? message.created_at, timezone)}
            </span>
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
        timezone={timezone}
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
            : "border-border bg-muted/40",
          message.status === "failed" &&
            "border-destructive/20 bg-destructive/10"
        )}
      >
        {message.media_url ? <MediaPreview message={message} /> : null}
        {message.content ? (
          <p className="break-words whitespace-pre-wrap">{message.content}</p>
        ) : null}
        <div
          className={cn(
            "mt-1 flex items-center gap-1 text-[10px] text-muted-foreground",
            isOutbound ? "justify-end" : "justify-start"
          )}
        >
          {isAutoReply ? (
            <span className="flex items-center gap-0.5 font-medium text-primary">
              <Bot className="size-3" />
              AI
            </span>
          ) : null}
          <span>
            {formatDateTime(message.sent_at ?? message.created_at, timezone)}
          </span>
          <MessageStatusIcon message={message} />
        </div>
        {message.direction == "outbound" && (
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
        )}
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

function extractTemplatePayload(
  message: WhatsAppMessage
): TemplatePayload | null {
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
      (item) => item.name === name && (!language || item.language === language)
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
  timezone = "UTC",
  templates,
  onEdit,
  onDelete,
}: {
  message: WhatsAppMessage
  timezone?: string
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
          <p className="text-xs leading-relaxed break-words whitespace-pre-wrap text-foreground/85">
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
          <span>
            {formatDateTime(message.sent_at ?? message.created_at, timezone)}
          </span>
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
