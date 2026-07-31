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

export type WhatsAppIntegration = {
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

export type WhatsAppContact = {
  id: string
  company_id: string
  integration_id: string
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
  integration_id: string
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
  integration_id: string
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
  integration: WhatsAppIntegration
  connection: WhatsAppCloudApiConnection
}

export type ApiError = {
  detail: string
}

export class ApiClientError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiClientError"
    this.status = status
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has("Content-Type")) {
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
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : "Request failed. Please try again."
    throw new ApiClientError(response.status, detail)
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
      { method: "POST" },
    )
  },

  resendVerificationEmail(email: string) {
    return request<{ message: string }>(
      `/auth/resend-verification-email${buildQuery({ email })}`,
      { method: "POST" },
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
      token,
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
      token,
    )
  },

  deleteCompany(companyId: string, token: string) {
    return request<void>(
      `/companies/${companyId}`,
      { method: "DELETE" },
      token,
    )
  },

  listMembers(companyId: string, token: string) {
    return request<Member[]>(`/companies/${companyId}/members`, {}, token)
  },

  createMember(
    companyId: string,
    data: { email: string; password: string },
    token: string,
  ) {
    return request<Member>(
      `/companies/${companyId}/members`,
      { method: "POST", body: JSON.stringify(data) },
      token,
    )
  },

  updateMember(
    companyId: string,
    memberId: string,
    data: { email?: string; password?: string; is_active?: boolean },
    token: string,
  ) {
    return request<Member>(
      `/companies/${companyId}/members/${memberId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    )
  },

  deleteMember(companyId: string, memberId: string, token: string) {
    return request<void>(
      `/companies/${companyId}/members/${memberId}`,
      { method: "DELETE" },
      token,
    )
  },

  // --- AI ---
  createChatSession(
    data: { title?: string; system_prompt?: string | null },
    token: string,
  ) {
    return request<ChatSession>(
      "/ai/sessions",
      { method: "POST", body: JSON.stringify(data) },
      token,
    )
  },

  listChatSessions(token: string, limit = 50, offset = 0) {
    return request<ChatSession[]>(
      `/ai/sessions${buildQuery({ limit, offset })}`,
      {},
      token,
    )
  },

  getChatSession(sessionId: string, token: string) {
    return request<ChatSession>(`/ai/sessions/${sessionId}`, {}, token)
  },

  getChatContext(sessionId: string, token: string) {
    return request<ContextSummary>(
      `/ai/sessions/${sessionId}/context`,
      {},
      token,
    )
  },

  getSystemPrompt(sessionId: string, token: string) {
    return request<{ session_id: string; system_prompt: string | null }>(
      `/ai/sessions/${sessionId}/system-prompt`,
      {},
      token,
    )
  },

  updateSystemPrompt(
    sessionId: string,
    system_prompt: string | null,
    token: string,
  ) {
    return request<{ session_id: string; system_prompt: string | null }>(
      `/ai/sessions/${sessionId}/system-prompt`,
      { method: "PUT", body: JSON.stringify({ system_prompt }) },
      token,
    )
  },

  deleteSystemPrompt(sessionId: string, token: string) {
    return request<{ session_id: string; system_prompt: string | null }>(
      `/ai/sessions/${sessionId}/system-prompt`,
      { method: "DELETE" },
      token,
    )
  },

  deleteChatSession(sessionId: string, token: string) {
    return request<{ message: string }>(
      `/ai/sessions/${sessionId}`,
      { method: "DELETE" },
      token,
    )
  },

  chat(sessionId: string, prompt: string, token: string) {
    return request<ChatResult>(
      `/ai/sessions/${sessionId}/chat`,
      { method: "POST", body: JSON.stringify({ prompt }) },
      token,
    )
  },

  // --- WhatsApp ---
  createCloudApiIntegration(
    data: {
      company_id: string
      name: string
      credentials: WhatsAppCloudApiCredentials
      subscribe_to_webhooks?: boolean
    },
    token: string,
  ) {
    return request<WhatsAppCloudApiConnectResponse>(
      "/whatsapp/cloud-api/integrations",
      { method: "POST", body: JSON.stringify(data) },
      token,
    )
  },

  updateCloudApiIntegration(
    integrationId: string,
    data: {
      name?: string
      credentials: WhatsAppCloudApiCredentials
      subscribe_to_webhooks?: boolean
    },
    token: string,
  ) {
    return request<WhatsAppCloudApiConnectResponse>(
      `/whatsapp/cloud-api/integrations/${integrationId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    )
  },

  verifyCloudApiIntegration(
    integrationId: string,
    token: string,
    subscribe_to_webhooks = true,
  ) {
    return request<WhatsAppCloudApiConnectResponse>(
      `/whatsapp/cloud-api/integrations/${integrationId}${buildQuery({ subscribe_to_webhooks: subscribe_to_webhooks ? "true" : "false" })}`,
      { method: "POST" },
      token,
    )
  },

  createIntegration(
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
    token: string,
  ) {
    return request<WhatsAppIntegration>(
      "/whatsapp/integrations",
      { method: "POST", body: JSON.stringify(data) },
      token,
    )
  },

  listIntegrations(token: string, company_id?: string) {
    return request<WhatsAppIntegration[]>(
      `/whatsapp/integrations${buildQuery({ company_id })}`,
      {},
      token,
    )
  },

  updateIntegration(
    integrationId: string,
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
    token: string,
  ) {
    return request<WhatsAppIntegration>(
      `/whatsapp/integrations/${integrationId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    )
  },

  deleteIntegration(integrationId: string, token: string) {
    return request<void>(
      `/whatsapp/integrations/${integrationId}`,
      { method: "DELETE" },
      token,
    )
  },

  createContact(
    data: {
      integration_id: string
      external_id?: string
      phone_number: string
      name?: string
      profile_picture_url?: string
      is_blocked?: boolean
      metadata?: Record<string, unknown>
    },
    token: string,
  ) {
    return request<WhatsAppContact>(
      "/whatsapp/contacts",
      { method: "POST", body: JSON.stringify(data) },
      token,
    )
  },

  listContacts(
    token: string,
    opts: { integration_id?: string; company_id?: string; limit?: number } = {},
  ) {
    return request<WhatsAppContact[]>(
      `/whatsapp/contacts${buildQuery(opts)}`,
      {},
      token,
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
    token: string,
  ) {
    return request<WhatsAppContact>(
      `/whatsapp/contacts/${contactId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    )
  },

  deleteContact(contactId: string, token: string) {
    return request<void>(
      `/whatsapp/contacts/${contactId}`,
      { method: "DELETE" },
      token,
    )
  },

  createConversation(
    data: {
      integration_id: string
      contact_id?: string
      external_id?: string
      title?: string
      status?: ConversationStatus
      metadata?: Record<string, unknown>
    },
    token: string,
  ) {
    return request<WhatsAppConversation>(
      "/whatsapp/conversations",
      { method: "POST", body: JSON.stringify(data) },
      token,
    )
  },

  listConversations(
    token: string,
    opts: {
      integration_id?: string
      company_id?: string
      contact_id?: string
      limit?: number
    } = {},
  ) {
    return request<WhatsAppConversation[]>(
      `/whatsapp/conversations${buildQuery(opts)}`,
      {},
      token,
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
    token: string,
  ) {
    return request<WhatsAppConversation>(
      `/whatsapp/conversations/${conversationId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    )
  },

  deleteConversation(conversationId: string, token: string) {
    return request<void>(
      `/whatsapp/conversations/${conversationId}`,
      { method: "DELETE" },
      token,
    )
  },

  listConversationMessages(conversationId: string, token: string) {
    return request<WhatsAppMessage[]>(
      `/whatsapp/conversations/${conversationId}/messages`,
      {},
      token,
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
    token: string,
  ) {
    return request<WhatsAppMessage>(
      "/whatsapp/messages",
      { method: "POST", body: JSON.stringify(data) },
      token,
    )
  },

  listMessages(
    token: string,
    opts: {
      conversation_id?: string
      integration_id?: string
      company_id?: string
      limit?: number
    } = {},
  ) {
    return request<WhatsAppMessage[]>(
      `/whatsapp/messages${buildQuery(opts)}`,
      {},
      token,
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
    token: string,
  ) {
    return request<WhatsAppMessage>(
      `/whatsapp/messages/${messageId}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    )
  },

  deleteMessage(messageId: string, token: string) {
    return request<void>(
      `/whatsapp/messages/${messageId}`,
      { method: "DELETE" },
      token,
    )
  },

  health() {
    return request<{ status: string }>("/health")
  },
}
