const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"

export type TokenResponse = {
  access_token: string
  token_type: string
}

export type UserProfile = {
  email: string
  is_super_admin: boolean
  company_id: string | null
}

export type Company = {
  id: string
  name: string
  is_active: boolean
  created_at: string
  owner_id: string
}

export type Member = {
  id: string
  email: string
  is_active: boolean
  is_verified: boolean
  is_super_admin: boolean
  company_id: string | null
  created_at: string
}

export type ChatSession = {
  id: string
  title: string
  system_prompt: string | null
  is_active: boolean
  created_at: string
  expires_at: string
  message_count: number
}

export type ChatMessage = {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  created_at: string
}

export type ContextSummary = {
  session_id: string
  context_summary: string | null
  messages: ChatMessage[]
}

export type ChatResult = {
  response: string
  session_id: string
}

export type IntegrationType = "official" | "unofficial"
export type ConversationStatus = "open" | "pending" | "closed"
export type MessageDirection = "inbound" | "outbound"
export type MessageStatus = "pending" | "sent" | "delivered" | "read" | "failed"

export type WhatsAppInstance = {
  id: string
  company_id: string
  name: string
  integration_type: IntegrationType
  adapter: string
  phone_number: string | null
  external_account_id: string | null
  config: Record<string, unknown>
  credentials_configured: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

// Kept only as a source-compatible alias while feature components move to the
// product term used in the UI and public API.
export type WhatsAppIntegration = WhatsAppInstance

export type WhatsAppContact = {
  id: string
  company_id: string
  instance_id: string
  external_id: string | null
  phone_number: string
  name: string | null
  profile_picture_url: string | null
  is_blocked: boolean
  metadata: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export type WhatsAppConversation = {
  id: string
  company_id: string
  instance_id: string
  contact_id: string | null
  external_id: string | null
  title: string | null
  status: ConversationStatus
  metadata: Record<string, unknown>
  last_message_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type WhatsAppMessage = {
  id: string
  company_id: string
  instance_id: string
  conversation_id: string
  external_id: string | null
  direction: MessageDirection
  message_type: string
  content: string | null
  media_url: string | null
  status: MessageStatus
  metadata: Record<string, unknown>
  sent_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type WhatsAppCloudApiCredentials = {
  app_id: string
  app_secret: string
  access_token: string
  business_account_id: string
  phone_number_id: string
  webhook_verify_token: string
  api_version: string
}

export type WhatsAppCloudApiConnection = {
  app_id: string
  business_account_id: string
  business_account_name: string | null
  phone_number_id: string
  display_phone_number: string | null
  verified_name: string | null
  quality_rating: string | null
  webhook_subscribed: boolean
  coexistence: false
}

export type WhatsAppCloudApiConnectResponse = {
  instance: WhatsAppInstance
  verification: WhatsAppCloudApiConnection
}

export type WhatsAppCloudApiTemplate = {
  id: string
  name: string
  language: string
  status: string
  category: string | null
  components: Record<string, unknown>[]
  quality_score: Record<string, unknown> | null
  rejected_reason: string | null
}

export type WhatsAppCloudApiTemplatePage = {
  data: WhatsAppCloudApiTemplate[]
  next_cursor: string | null
}

export type WhatsAppAiResult = {
  prompt_message: WhatsAppMessage
  message: WhatsAppMessage
  response: string
}

export type WhatsAppAISettings = {
  company_id: string
  enabled: boolean
  system_prompt: string | null
  trusted_phone_numbers: string[]
  allowed_contact_tools: string[]
  reply_cooldown_seconds: number
  updated_at: string
}

export type ConversationAISettings = {
  conversation_id: string
  enabled: boolean | null
  system_prompt: string | null
}

export type LLMProvider = "deepseek" | "openai" | "gemini" | "groq"

export type ReasoningLevel = "minimal" | "low" | "medium" | "high"

export type LLMProviderConfig = {
  configured: boolean
  model: string | null
  supports_thinking: boolean
  reasoning_effort: ReasoningLevel
}

export type LLMSettings = {
  selected_provider: LLMProvider | null
  providers: Record<LLMProvider, LLMProviderConfig>
}

export type AIGlobalSettings = LLMSettings

export type CompanyLLMSettings = LLMSettings & {
  company_id: string
}

export type AIGlobalSettingsUpdate = {
  selected_provider?: LLMProvider | null
  deepseek_api_key?: string | null
  openai_api_key?: string | null
  gemini_api_key?: string | null
  groq_api_key?: string | null
  deepseek_model?: string | null
  openai_model?: string | null
  gemini_model?: string | null
  groq_model?: string | null
  deepseek_reasoning_effort?: ReasoningLevel | null
  openai_reasoning_effort?: ReasoningLevel | null
  gemini_reasoning_effort?: ReasoningLevel | null
  groq_reasoning_effort?: ReasoningLevel | null
  deepseek_supports_thinking?: boolean | null
  openai_supports_thinking?: boolean | null
  gemini_supports_thinking?: boolean | null
  groq_supports_thinking?: boolean | null
}

export type McpToolInfo = {
  name: string
  method: string
  path: string
  summary: string | null
  description: string
  requires_auth: boolean
}

export type McpToolsPage = {
  tools: McpToolInfo[]
  allowed: string[]
}

export type WhatsAppMediaUpload = {
  key: string
  url: string
  filename: string
  mime_type: string
  size_bytes: number
}

export type WhatsAppRealtimeEvent = {
  type: string
  company_id: string
  instance_id: string | null
  conversation_id: string | null
  message_id: string | null
  occurred_at: string
}

export type NotificationItem = {
  id: string
  type: string
  title: string
  body: string | null
  conversation_id: string | null
  integration_id: string | null
  message_id: string | null
  is_read: boolean
  created_at: string
}

export type NotificationListResponse = {
  items: NotificationItem[]
  unread_count: number
}

export type UnreadCountResponse = {
  unread_count: number
}

export type ApiError = {
  detail: unknown
}

export class ApiClientError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiClientError"
    this.status = status
  }
}

function formatApiError(detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail)) {
    const lines = detail
      .map((item) => {
        if (!item || typeof item !== "object") {
          return ""
        }
        const error = item as { loc?: unknown; msg?: unknown }
        const location = Array.isArray(error.loc)
          ? error.loc.map((part) => String(part)).join(".")
          : ""
        const message =
          typeof error.msg === "string" && error.msg
            ? error.msg
            : "Invalid value"
        return location ? `${location}: ${message}` : message
      })
      .filter(Boolean)
    if (lines.length > 0) {
      return lines.join("\n")
    }
  }
  if (detail && typeof detail === "object") {
    return JSON.stringify(detail)
  }
  return "Request failed. Please try again."
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(init.headers)
  if (
    init.body &&
    !headers.has("Content-Type") &&
    !(init.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json")
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as Partial<ApiError>
    throw new ApiClientError(response.status, formatApiError(body.detail))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

function buildQuery(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return query ? `?${query}` : ""
}

export function subscribeToWhatsAppEvents({
  companyId,
  token,
  onEvent,
  onError,
}: {
  companyId: string
  token: string
  onEvent: (event: WhatsAppRealtimeEvent) => void
  onError?: (error: Error) => void
}) {
  const controller = new AbortController()
  let retryTimer: ReturnType<typeof setTimeout> | undefined

  async function connect() {
    try {
      const response = await fetch(
        `${API_BASE}/whatsapp/instances/events${buildQuery({ company_id: companyId })}`,
        {
          headers: {
            Accept: "text/event-stream",
            Authorization: `Bearer ${token}`,
          },
          cache: "no-store",
          signal: controller.signal,
        }
      )
      if (!response.ok || !response.body) {
        throw new Error("Could not connect to WhatsApp live updates.")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      while (!controller.signal.aborted) {
        const { value, done } = await reader.read()
        if (done) {
          break
        }
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split("\n\n")
        buffer = frames.pop() ?? ""
        for (const frame of frames) {
          const data = frame
            .split("\n")
            .find((line) => line.startsWith("data: "))
            ?.slice(6)
          if (!data) {
            continue
          }
          try {
            onEvent(JSON.parse(data) as WhatsAppRealtimeEvent)
          } catch {
            // Ignore malformed event frames and keep the subscription alive.
          }
        }
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        onError?.(
          error instanceof Error
            ? error
            : new Error("WhatsApp live updates were interrupted.")
        )
      }
    } finally {
      if (!controller.signal.aborted) {
        retryTimer = setTimeout(() => void connect(), 1500)
      }
    }
  }

  void connect()
  return () => {
    controller.abort()
    if (retryTimer) {
      clearTimeout(retryTimer)
    }
  }
}

export const api = {
  // --- Auth ---
  register(email: string, password: string) {
    return request<{ message: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
  },

  login(email: string, password: string) {
    return request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
  },

  verifyEmail(token: string) {
    return request<TokenResponse>(
      `/auth/verify-email${buildQuery({ token })}`,
      { method: "POST" }
    )
  },

  resendVerificationEmail(email: string) {
    return request<{ message: string }>(
      `/auth/resend-verification-email${buildQuery({ email })}`,
      { method: "POST" }
    )
  },

  getCurrentUser(token: string) {
    return request<UserProfile>("/auth/user", {}, token)
  },

  // --- Companies (super admin) ---
  createCompany(name: string, token: string) {
    return request<Company>(
      "/companies",
      { method: "POST", body: JSON.stringify({ name }) },
      token
    )
  },

  listCompanies(token: string) {
    return request<Company[]>("/companies", {}, token)
  },

  getCompany(companyId: string, token: string) {
    return request<Company>(`/companies/${companyId}`, {}, token)
  },

  updateCompany(companyId: string, name: string, token: string) {
    return request<Company>(
      `/companies/${companyId}`,
      { method: "PUT", body: JSON.stringify({ name }) },
      token
    )
  },

  deleteCompany(companyId: string, token: string) {
    return request<void>(`/companies/${companyId}`, { method: "DELETE" }, token)
  },

  listMembers(companyId: string, token: string) {
    return request<Member[]>(`/companies/${companyId}/members`, {}, token)
  },

  createMember(
    companyId: string,
    data: { email: string; password: string },
    token: string
  ) {
    return request<Member>(
      `/companies/${companyId}/members`,
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  updateMember(
    companyId: string,
    memberId: string,
    data: { email?: string; password?: string; is_active?: boolean },
    token: string
  ) {
    return request<Member>(
      `/companies/${companyId}/members/${memberId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  deleteMember(companyId: string, memberId: string, token: string) {
    return request<void>(
      `/companies/${companyId}/members/${memberId}`,
      { method: "DELETE" },
      token
    )
  },

  // --- AI ---
  createChatSession(
    data: { title?: string; system_prompt?: string | null },
    token: string
  ) {
    return request<ChatSession>(
      "/ai/sessions",
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  listChatSessions(token: string, limit = 50, offset = 0) {
    return request<ChatSession[]>(
      `/ai/sessions${buildQuery({ limit, offset })}`,
      {},
      token
    )
  },

  getChatSession(sessionId: string, token: string) {
    return request<ChatSession>(`/ai/sessions/${sessionId}`, {}, token)
  },

  getChatContext(sessionId: string, token: string) {
    return request<ContextSummary>(
      `/ai/sessions/${sessionId}/context`,
      {},
      token
    )
  },

  getSystemPrompt(sessionId: string, token: string) {
    return request<{ session_id: string; system_prompt: string | null }>(
      `/ai/sessions/${sessionId}/system-prompt`,
      {},
      token
    )
  },

  updateSystemPrompt(
    sessionId: string,
    system_prompt: string | null,
    token: string
  ) {
    return request<{ session_id: string; system_prompt: string | null }>(
      `/ai/sessions/${sessionId}/system-prompt`,
      { method: "PUT", body: JSON.stringify({ system_prompt }) },
      token
    )
  },

  deleteSystemPrompt(sessionId: string, token: string) {
    return request<{ session_id: string; system_prompt: string | null }>(
      `/ai/sessions/${sessionId}/system-prompt`,
      { method: "DELETE" },
      token
    )
  },

  deleteChatSession(sessionId: string, token: string) {
    return request<{ message: string }>(
      `/ai/sessions/${sessionId}`,
      { method: "DELETE" },
      token
    )
  },

  chat(sessionId: string, prompt: string, token: string) {
    return request<ChatResult>(
      `/ai/sessions/${sessionId}/chat`,
      { method: "POST", body: JSON.stringify({ prompt }) },
      token
    )
  },

  uploadSessionFile(sessionId: string, file: File, token: string) {
    const form = new FormData()
    form.append("file", file)
    return request<{ message: string }>(
      `/ai/sessions/${sessionId}/files`,
      { method: "POST", body: form },
      token
    )
  },

  sessionFileUrl(sessionId: string, fileId: string) {
    return `${API_BASE}/ai/sessions/${sessionId}/files/${fileId}`
  },

  // --- WhatsApp ---
  createCloudApiInstance(
    data: {
      company_id: string
      name: string
      credentials: WhatsAppCloudApiCredentials
      subscribe_to_webhooks?: boolean
    },
    token: string
  ) {
    return request<WhatsAppCloudApiConnectResponse>(
      "/whatsapp/instances/cloud-api",
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  updateCloudApiInstance(
    instanceId: string,
    data: {
      name?: string
      credentials: WhatsAppCloudApiCredentials
      subscribe_to_webhooks?: boolean
    },
    token: string
  ) {
    return request<WhatsAppCloudApiConnectResponse>(
      `/whatsapp/instances/${instanceId}/cloud-api`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  verifyCloudApiInstance(
    instanceId: string,
    token: string,
    subscribe_to_webhooks = true
  ) {
    return request<WhatsAppCloudApiConnectResponse>(
      `/whatsapp/instances/${instanceId}/verify${buildQuery({ subscribe_to_webhooks: subscribe_to_webhooks ? "true" : "false" })}`,
      { method: "POST" },
      token
    )
  },

  createInstance(
    data: {
      company_id: string
      name: string
      integration_type: IntegrationType
      adapter: string
      phone_number?: string
      external_account_id?: string
      credentials?: Record<string, unknown>
      config?: Record<string, unknown>
    },
    token: string
  ) {
    return request<WhatsAppInstance>(
      "/whatsapp/instances",
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  listInstances(token: string, company_id?: string) {
    return request<WhatsAppInstance[]>(
      `/whatsapp/instances${buildQuery({ company_id })}`,
      {},
      token
    )
  },

  updateInstance(
    instanceId: string,
    data: {
      name?: string
      integration_type?: IntegrationType
      adapter?: string
      phone_number?: string
      external_account_id?: string
      credentials?: Record<string, unknown>
      config?: Record<string, unknown>
      is_active?: boolean
    },
    token: string
  ) {
    return request<WhatsAppInstance>(
      `/whatsapp/instances/${instanceId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  deleteInstance(instanceId: string, token: string) {
    return request<void>(
      `/whatsapp/instances/${instanceId}`,
      { method: "DELETE" },
      token
    )
  },

  createContact(
    data: {
      instance_id: string
      external_id?: string
      phone_number: string
      name?: string
      profile_picture_url?: string
      is_blocked?: boolean
      metadata?: Record<string, unknown>
    },
    token: string
  ) {
    return request<WhatsAppContact>(
      "/whatsapp/contacts",
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  listContacts(
    token: string,
    opts: { instance_id?: string; company_id?: string; limit?: number } = {}
  ) {
    return request<WhatsAppContact[]>(
      `/whatsapp/contacts${buildQuery(opts)}`,
      {},
      token
    )
  },

  updateContact(
    contactId: string,
    data: {
      external_id?: string
      phone_number?: string
      name?: string
      profile_picture_url?: string
      is_blocked?: boolean
      metadata?: Record<string, unknown>
      is_active?: boolean
    },
    token: string
  ) {
    return request<WhatsAppContact>(
      `/whatsapp/contacts/${contactId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  deleteContact(contactId: string, token: string) {
    return request<void>(
      `/whatsapp/contacts/${contactId}`,
      { method: "DELETE" },
      token
    )
  },

  createConversation(
    data: {
      instance_id: string
      contact_id?: string
      external_id?: string
      title?: string
      status?: ConversationStatus
      metadata?: Record<string, unknown>
    },
    token: string
  ) {
    return request<WhatsAppConversation>(
      "/whatsapp/conversations",
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  listConversations(
    token: string,
    opts: {
      instance_id?: string
      company_id?: string
      contact_id?: string
      limit?: number
    } = {}
  ) {
    return request<WhatsAppConversation[]>(
      `/whatsapp/conversations${buildQuery(opts)}`,
      {},
      token
    )
  },

  updateConversation(
    conversationId: string,
    data: {
      contact_id?: string
      external_id?: string
      title?: string
      status?: ConversationStatus
      metadata?: Record<string, unknown>
      is_active?: boolean
    },
    token: string
  ) {
    return request<WhatsAppConversation>(
      `/whatsapp/conversations/${conversationId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  deleteConversation(conversationId: string, token: string) {
    return request<void>(
      `/whatsapp/conversations/${conversationId}`,
      { method: "DELETE" },
      token
    )
  },

  listConversationMessages(conversationId: string, token: string) {
    return request<WhatsAppMessage[]>(
      `/whatsapp/conversations/${conversationId}/messages`,
      {},
      token
    )
  },

  createMessage(
    data: {
      conversation_id: string
      external_id?: string
      direction: MessageDirection
      message_type?: string
      content?: string
      media_url?: string
      status?: MessageStatus
      metadata?: Record<string, unknown>
      sent_at?: string
    },
    token: string
  ) {
    return request<WhatsAppMessage>(
      "/whatsapp/messages",
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  createNote(conversationId: string, content: string, token: string) {
    return request<WhatsAppMessage>(
      `/whatsapp/conversations/${conversationId}/note`,
      { method: "POST", body: JSON.stringify({ content }) },
      token
    )
  },

  askAi(conversationId: string, prompt: string, token: string) {
    return request<WhatsAppAiResult>(
      `/whatsapp/conversations/${conversationId}/ai`,
      { method: "POST", body: JSON.stringify({ prompt }) },
      token
    )
  },

  listMessages(
    token: string,
    opts: {
      conversation_id?: string
      instance_id?: string
      company_id?: string
      limit?: number
    } = {}
  ) {
    return request<WhatsAppMessage[]>(
      `/whatsapp/messages${buildQuery(opts)}`,
      {},
      token
    )
  },

  updateMessage(
    messageId: string,
    data: {
      content?: string
      status?: MessageStatus
      direction?: MessageDirection
      message_type?: string
    },
    token: string
  ) {
    return request<WhatsAppMessage>(
      `/whatsapp/messages/${messageId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  deleteMessage(messageId: string, token: string) {
    return request<void>(
      `/whatsapp/messages/${messageId}`,
      { method: "DELETE" },
      token
    )
  },

  listCloudApiTemplates(
    instanceId: string,
    token: string,
    opts: { limit?: number; after?: string } = {}
  ) {
    return request<WhatsAppCloudApiTemplatePage>(
      `/whatsapp/instances/${instanceId}/cloud-api/templates${buildQuery(opts)}`,
      {},
      token
    )
  },

  createCloudApiTemplate(
    instanceId: string,
    data: {
      name: string
      language: string
      category: string
      components: Record<string, unknown>[]
      allow_category_change?: boolean
    },
    token: string
  ) {
    return request<WhatsAppCloudApiTemplate>(
      `/whatsapp/instances/${instanceId}/cloud-api/templates`,
      { method: "POST", body: JSON.stringify(data) },
      token
    )
  },

  deleteCloudApiTemplate(
    instanceId: string,
    name: string,
    token: string,
    opts: { hsm_id?: string } = {}
  ) {
    return request<void>(
      `/whatsapp/instances/${instanceId}/cloud-api/templates${buildQuery({ name, hsm_id: opts.hsm_id })}`,
      { method: "DELETE" },
      token
    )
  },

  updateCloudApiTemplate(
    instanceId: string,
    previousName: string,
    data: {
      name: string
      language: string
      category: string
      components: Record<string, unknown>[]
      allow_category_change?: boolean
    },
    token: string,
    opts: { previous_hsm_id?: string } = {}
  ) {
    return request<WhatsAppCloudApiTemplate>(
      `/whatsapp/instances/${instanceId}/cloud-api/templates${buildQuery({ previous_name: previousName, previous_hsm_id: opts.previous_hsm_id })}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  uploadWhatsAppMedia(file: File, token: string) {
    const form = new FormData()
    form.append("file", file)
    return request<WhatsAppMediaUpload>(
      "/whatsapp/media/upload",
      { method: "POST", body: form },
      token
    )
  },

  getCompanyAISettings(companyId: string, token: string) {
    return request<WhatsAppAISettings>(
      `/whatsapp/companies/${companyId}/ai/settings`,
      {},
      token
    )
  },

  updateCompanyAISettings(
    companyId: string,
    data: {
      enabled?: boolean
      system_prompt?: string | null
      trusted_phone_numbers?: string[]
      allowed_contact_tools?: string[]
      reply_cooldown_seconds?: number
    },
    token: string
  ) {
    return request<WhatsAppAISettings>(
      `/whatsapp/companies/${companyId}/ai/settings`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  listCompanyAIMcpTools(companyId: string, token: string) {
    return request<McpToolsPage>(
      `/whatsapp/companies/${companyId}/ai/mcp-tools`,
      {},
      token
    )
  },

  getAIGlobalSettings(token: string) {
    return request<AIGlobalSettings>(`/ai/settings`, {}, token)
  },

  updateAIGlobalSettings(data: AIGlobalSettingsUpdate, token: string) {
    return request<AIGlobalSettings>(
      `/ai/settings`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  getCompanyLLMSettings(companyId: string, token: string) {
    return request<CompanyLLMSettings>(
      `/ai/companies/${companyId}/llm-settings`,
      {},
      token
    )
  },

  updateCompanyLLMSettings(
    companyId: string,
    data: {
      selected_provider?: LLMProvider | null
      deepseek_api_key?: string | null
      openai_api_key?: string | null
      gemini_api_key?: string | null
      supports_thinking?: boolean | null
    },
    token: string
  ) {
    return request<CompanyLLMSettings>(
      `/ai/companies/${companyId}/llm-settings`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  getConversationAISettings(conversationId: string, token: string) {
    return request<ConversationAISettings>(
      `/whatsapp/conversations/${conversationId}/ai/settings`,
      {},
      token
    )
  },

  updateConversationAISettings(
    conversationId: string,
    data: {
      enabled?: boolean | null
      system_prompt?: string | null
    },
    token: string
  ) {
    return request<ConversationAISettings>(
      `/whatsapp/conversations/${conversationId}/ai/settings`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    )
  },

  health() {
    return request<{ status: string }>("/health")
  },

  // --- Notifications ---
  listNotifications(
    token: string,
    options: {
      companyId?: string
      unreadOnly?: boolean
      limit?: number
      offset?: number
    } = {}
  ) {
    return request<NotificationListResponse>(
      `/notifications${buildQuery({
        company_id: options.companyId,
        unread_only: options.unreadOnly ? "true" : undefined,
        limit: options.limit,
        offset: options.offset,
      })}`,
      {},
      token
    )
  },

  unreadNotificationsCount(token: string, companyId?: string) {
    return request<UnreadCountResponse>(
      `/notifications/unread-count${buildQuery({ company_id: companyId })}`,
      {},
      token
    )
  },

  markNotificationRead(notificationId: string, token: string, companyId?: string) {
    return request<NotificationItem>(
      `/notifications/${notificationId}/read${buildQuery({ company_id: companyId })}`,
      { method: "PATCH" },
      token
    )
  },

  markAllNotificationsRead(token: string, companyId?: string) {
    return request<{ success: boolean }>(
      `/notifications/read-all${buildQuery({ company_id: companyId })}`,
      { method: "POST" },
      token
    )
  },
}
