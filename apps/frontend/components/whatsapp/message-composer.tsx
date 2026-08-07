"use client"

import * as React from "react"
import {
  Bot,
  FileAudio,
  FileText,
  FileVideo,
  Image,
  LoaderCircle,
  MapPin,
  MessageCircleMore,
  Paperclip,
  Send,
  SmilePlus,
  Sparkles,
  StickyNote,
  Users,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import type { WhatsAppCloudApiTemplate, WhatsAppMessage } from "@/lib/api"

import { AudioRecorder } from "@/components/whatsapp/audio-recorder"

export type ComposerMessageData = {
  message_type: string
  content?: string
  media_url?: string
  metadata?: Record<string, unknown>
}

const MESSAGE_TYPES = [
  { value: "text", label: "Text", icon: MessageCircleMore },
  { value: "image", label: "Image", icon: Image },
  { value: "video", label: "Video", icon: FileVideo },
  { value: "audio", label: "Audio", icon: FileAudio },
  { value: "document", label: "Document", icon: FileText },
  { value: "sticker", label: "Sticker", icon: SmilePlus },
  { value: "location", label: "Location", icon: MapPin },
  //{ value: "contacts", label: "Contacts", icon: Users },
  //{ value: "interactive", label: "Interactive", icon: MessageCircleMore },
  { value: "template", label: "Template", icon: FileText },
  //{ value: "reaction", label: "Reaction", icon: SmilePlus },
]

type TemplateField = {
  id: string
  componentType: "body" | "header" | "button"
  parameterType: "text" | "media"
  mediaType?: "image" | "video" | "document"
  buttonIndex?: number
  label: string
}

function templateFields(template: WhatsAppCloudApiTemplate): TemplateField[] {
  const fields: TemplateField[] = []
  for (const component of template.components) {
    const type = String(component.type ?? "").toUpperCase()
    if (type === "HEADER") {
      const format = String(component.format ?? "TEXT").toUpperCase()
      if (["IMAGE", "VIDEO", "DOCUMENT"].includes(format)) {
        fields.push({
          id: "header:media",
          componentType: "header",
          parameterType: "media",
          mediaType: format.toLowerCase() as "image" | "video" | "document",
          label: `Header ${format.toLowerCase()} URL`,
        })
        continue
      }
    }
    if (type === "HEADER" || type === "BODY") {
      const text = typeof component.text === "string" ? component.text : ""
      for (const match of text.matchAll(/{{\s*(\d+)\s*}}/g)) {
        fields.push({
          id: `${type.toLowerCase()}:${match[1]}`,
          componentType: type.toLowerCase() as "body" | "header",
          parameterType: "text",
          label: `${type === "BODY" ? "Body" : "Header"} variable ${match[1]}`,
        })
      }
    }
    if (type === "BUTTON" && Array.isArray(component.buttons)) {
      component.buttons.forEach((button, index) => {
        if (
          button &&
          typeof button === "object" &&
          String(
            (button as Record<string, unknown>).type ?? ""
          ).toUpperCase() === "URL" &&
          /{{\s*\d+\s*}}/.test(
            String((button as Record<string, unknown>).url ?? "")
          )
        ) {
          fields.push({
            id: `button:${index}`,
            componentType: "button",
            parameterType: "text",
            buttonIndex: index,
            label: `URL button ${index + 1} suffix`,
          })
        }
      })
    }
  }
  return fields
}

function templatePayload(
  template: WhatsAppCloudApiTemplate,
  values: Record<string, string>
) {
  const grouped = new Map<string, Record<string, unknown>>()
  for (const field of templateFields(template)) {
    const value = values[field.id]?.trim()
    if (!value) {
      throw new Error(`Complete ${field.label.toLowerCase()} before sending.`)
    }
    const key =
      field.componentType === "button"
        ? `button:${field.buttonIndex}`
        : field.componentType
    const component = grouped.get(key) ?? {
      type: field.componentType,
      ...(field.componentType === "button"
        ? { sub_type: "url", index: String(field.buttonIndex) }
        : {}),
      parameters: [],
    }
    const parameters = component.parameters as Record<string, unknown>[]
    parameters.push(
      field.parameterType === "media"
        ? {
            type: field.mediaType,
            [field.mediaType ?? "image"]: { link: value },
          }
        : { type: "text", text: value }
    )
    grouped.set(key, component)
  }
  return {
    name: template.name,
    language: { code: template.language },
    ...(grouped.size ? { components: [...grouped.values()] } : {}),
  }
}

function templatePreview(
  template: WhatsAppCloudApiTemplate,
  values: Record<string, string>
) {
  const body = template.components.find(
    (component) => String(component.type ?? "").toUpperCase() === "BODY"
  )
  if (!body || typeof body.text !== "string") {
    return "This approved template does not have a text body preview."
  }
  return body.text.replace(/{{\s*(\d+)\s*}}/g, (_, position: string) => {
    return values[`body:${position}`]?.trim() || `{{${position}}}`
  })
}

function MessageComposer({
  messages,
  disabled,
  templates = [],
  templatesLoading = false,
  templatesError,
  onSend,
  onNote,
  onAi,
  onUpload,
  aiPending = false,
}: {
  messages: WhatsAppMessage[]
  disabled?: boolean
  templates?: WhatsAppCloudApiTemplate[]
  templatesLoading?: boolean
  templatesError?: string | null
  onSend: (data: ComposerMessageData) => Promise<void>
  onNote?: (content: string) => Promise<void>
  onAi?: (prompt: string) => Promise<void>
  onUpload?: (file: File) => Promise<string>
  aiPending?: boolean
}) {
  const [messageType, setMessageType] = React.useState("text")
  const [content, setContent] = React.useState("")
  const [mediaUrl, setMediaUrl] = React.useState("")
  const [advancedJson, setAdvancedJson] = React.useState("")
  const [templateId, setTemplateId] = React.useState("")
  const [templateValues, setTemplateValues] = React.useState<
    Record<string, string>
  >({})

  const [coords, setCoords] = React.useState<{
    lat: number
    lng: number
  } | null>(null)

  const [latitude, setLatitude] = React.useState("")
  const [longitude, setLongitude] = React.useState("")
  const [locationName, setLocationName] = React.useState("")
  const [locationAddress, setLocationAddress] = React.useState("")
  const [reactionEmoji, setReactionEmoji] = React.useState("👍")
  const [reactionTarget, setReactionTarget] = React.useState("")
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [uploading, setUploading] = React.useState(false)
  const [recorderActive, setRecorderActive] = React.useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const composerRef = React.useRef<HTMLTextAreaElement>(null)
  const composing = disabled || aiPending || uploading

  function insertCommand(prefix: string) {
    setMessageType("text")
    setContent(prefix)
    composerRef.current?.focus()
  }

  const reactionMessages = React.useMemo(
    () => messages.filter((message) => message.external_id),
    [messages]
  )
  const defaultReactionTarget =
    reactionMessages[reactionMessages.length - 1]?.external_id ?? ""
  const approvedTemplates = React.useMemo(
    () =>
      templates.filter(
        (template) => template.status.toUpperCase() === "APPROVED"
      ),
    [templates]
  )
  const selectedTemplate = approvedTemplates.find(
    (template) => template.id === templateId
  )

  function parseJsonObject(value: string, label: string) {
    try {
      const parsed = JSON.parse(value) as unknown
      if (parsed === null || typeof parsed !== "object") {
        throw new Error(`${label} must be a JSON object or array.`)
      }
      return parsed
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : `Invalid ${label}.`)
    }
  }

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) {
      return
    }
    if (!onUpload) {
      setError("Media upload is unavailable for this conversation.")
      return
    }
    setUploading(true)
    setError(null)
    try {
      const url = await onUpload(file)
      setMediaUrl(url)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not upload the media file."
      )
    } finally {
      setUploading(false)
    }
  }

  async function handleAudioSend(data: ComposerMessageData) {
    if (!onUpload) {
      setError("Audio recording is unavailable for this conversation.")
      return
    }
    setIsPending(true)
    setError(null)
    try {
      await onSend(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not send the audio message."
      )
    } finally {
      setIsPending(false)
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (composing) {
      return
    }

    const trimmedContent = content.trim()
    const trimmedMediaUrl = mediaUrl.trim()
    let metadata: Record<string, unknown> | undefined

    try {
      if (messageType === "text") {
        const aiMatch = trimmedContent.match(/^\/ai(?:\s+([\s\S]*))?$/)
        const noteMatch = trimmedContent.match(/^\/note(?:\s+([\s\S]*))?$/)
        if (aiMatch || noteMatch) {
          const isAi = Boolean(aiMatch)
          const commandText = (
            (isAi ? aiMatch![1] : noteMatch![1]) ?? ""
          ).trim()
          if (!commandText) {
            throw new Error(
              isAi
                ? "Write a prompt after /ai."
                : "Write the note content after /note."
            )
          }
          setIsPending(true)
          setError(null)
          if (isAi) {
            if (!onAi) {
              throw new Error("The AI assistant is unavailable.")
            }
            await onAi(commandText)
          } else {
            if (!onNote) {
              throw new Error("Notes are unavailable.")
            }
            await onNote(commandText)
          }
          setContent("")
          return
        }
      }
      if (messageType === "text" && !trimmedContent) {
        throw new Error("Write a message before sending.")
      }
      if (
        ["image", "video", "audio", "document", "sticker"].includes(
          messageType
        ) &&
        !trimmedMediaUrl
      ) {
        throw new Error("Add a Meta media ID or public media URL.")
      }
      if (messageType === "location") {
        if (!latitude.trim() || !longitude.trim()) {
          throw new Error("Latitude and longitude are required.")
        }
        metadata = {
          location: {
            latitude: Number(latitude),
            longitude: Number(longitude),
            ...(locationName.trim() ? { name: locationName.trim() } : {}),
            ...(locationAddress.trim()
              ? { address: locationAddress.trim() }
              : {}),
          },
        }
      }
      if (["contacts", "interactive"].includes(messageType)) {
        const parsed = parseJsonObject(
          advancedJson,
          messageType === "contacts" ? "Contacts" : `${messageType} payload`
        )
        metadata = {
          [messageType]: parsed,
        }
      }
      if (messageType === "template") {
        if (!selectedTemplate) {
          throw new Error("Choose an approved Meta template before sending.")
        }
        metadata = {
          template: templatePayload(selectedTemplate, templateValues),
        }
      }
      if (messageType === "reaction") {
        const target = reactionTarget || defaultReactionTarget
        if (!target) {
          throw new Error("Choose the message to react to.")
        }
        metadata = {
          reaction: {
            message_id: target,
            emoji: reactionEmoji.trim() || "👍",
          },
        }
      }

      setIsPending(true)
      setAdvancedJson("")
      setContent("")
      setMediaUrl("")
      setTemplateId("")
      setTemplateValues({})
      setLatitude("")
      setLongitude("")
      setLocationName("")
      setLocationAddress("")

      setError(null)
      await onSend({
        message_type: messageType,
        content: trimmedContent || undefined,
        media_url: trimmedMediaUrl || undefined,
        metadata,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message.")
    } finally {
      setIsPending(false)
    }
  }

  const selectedType = MESSAGE_TYPES.find((item) => item.value === messageType)
  const isMediaType = [
    "image",
    "video",
    "audio",
    "document",
    "sticker",
  ].includes(messageType)

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      className="border-t p-3"
    >
      <div className="flex flex-wrap items-center gap-2 pb-2">
        <Select
          items={MESSAGE_TYPES.map(({ value, label }) => ({ value, label }))}
          value={messageType}
          onValueChange={(value) => {
            setMessageType(String(value))
            setError(null)
          }}
          disabled={composing}
        >
          <SelectTrigger className="w-36">
            {selectedType ? <selectedType.icon className="size-3.5" /> : null}
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MESSAGE_TYPES.map(({ value, label, icon: Icon }) => (
              <SelectItem key={value} value={value}>
                <Icon />
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <Paperclip className="size-3" />
          Meta message format
        </span>
        <span className="ms-auto flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-primary hover:bg-primary/10 hover:text-primary [&_svg]:size-3.5"
            onClick={() => insertCommand("/ai ")}
            disabled={composing}
            title="Ask the AI assistant to draft a reply — type /ai"
            aria-label="Ask the AI assistant"
          >
            {aiPending ? <LoaderCircle className="animate-spin" /> : <Bot />}
            AI
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-amber-600 hover:bg-amber-500/10 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-300 [&_svg]:size-3.5"
            onClick={() => insertCommand("/note ")}
            disabled={composing}
            title="Add an internal note — type /note"
            aria-label="Add an internal note"
          >
            <StickyNote />
            Note
          </Button>
        </span>
      </div>

      {isMediaType ? (
        <div className="mb-2 flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor="message-media-url">Media ID or public URL</Label>
            {onUpload ? (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={
                    selectedType?.value == "IMAGE"
                      ? "image/*,"
                      : selectedType?.value == "VIDEO"
                        ? "video/*"
                        : selectedType?.value == "audio"
                          ? "audio/*"
                          : selectedType?.value == "document"
                            ? "application/pdf, text/plain, application/octet-stream"
                            : selectedType?.value == "sticker"
                              ? "image/gif"
                              : "image/*,video/*,audio/*,application/pdf, text/plain,application/octet-stream"
                  }
                  className="hidden"
                  disabled={composing}
                  onChange={(event) => void handleFileChange(event)}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1.5 text-[11px] [&_svg]:size-3.5"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={composing}
                  title="Upload a local file to R2 and use its public URL"
                  aria-label="Upload a media file"
                >
                  {uploading ? (
                    <LoaderCircle className="animate-spin" />
                  ) : (
                    <Paperclip />
                  )}
                  {uploading ? "Uploading…" : "Upload file"}
                </Button>
              </>
            ) : null}
          </div>
          <Input
            id="message-media-url"
            value={mediaUrl}
            onChange={(event) => setMediaUrl(event.target.value)}
            placeholder="https://cdn.example.com/file.jpg or Meta media ID"
            disabled={composing}
          />
          <p className="text-[10px] text-muted-foreground">
            Upload the asset to Meta first, or provide a URL reachable by Meta.
          </p>
        </div>
      ) : null}

      {messageType === "location" ? (
        <div className="mb-2 grid gap-2 sm:grid-cols-2">
          <Input
            aria-label="Latitude"
            value={latitude}
            onChange={(event) => setLatitude(event.target.value)}
            placeholder="Latitude"
            disabled={composing}
          />
          <Input
            aria-label="Longitude"
            value={longitude}
            onChange={(event) => setLongitude(event.target.value)}
            placeholder="Longitude"
            disabled={composing}
          />
          <Input
            aria-label="Location name"
            value={locationName}
            onChange={(event) => setLocationName(event.target.value)}
            placeholder="Place name (optional)"
            disabled={composing}
          />
          <Input
            aria-label="Location address"
            value={locationAddress}
            onChange={(event) => setLocationAddress(event.target.value)}
            placeholder="Address (optional)"
            disabled={composing}
          />
        </div>
      ) : null}

      {messageType === "location" && (
        <Button
          className="mb-2 w-full"
          onClick={async () => {
            if (!("geolocation" in navigator)) {
              console.error("Seu navegador não suporta geolocalização.")
              return
            }

            try {
              // Verifica o estado da permissão (quando suportado)
              if ("permissions" in navigator) {
                const permission = await navigator.permissions.query({
                  name: "geolocation",
                })

                if (permission.state === "denied") {
                  alert(
                    "A permissão de localização foi negada. Habilite-a nas configurações do navegador."
                  )
                  return
                }
              }

              const position = await new Promise<GeolocationPosition>(
                (resolve, reject) => {
                  navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0,
                  })
                }
              )

              const { latitude, longitude, accuracy } = position.coords

              setLatitude(latitude.toString())
              setLongitude(longitude.toString())

              const response = await fetch(
                `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}`,
                {
                  headers: {
                    Accept: "application/json",
                  },
                }
              )

              if (!response.ok) {
                throw new Error("Não foi possível obter o endereço.")
              }

              const location = await response.json()

              const result = {
                latitude,
                longitude,
                accuracy,
                name: location.name ?? "",
                displayName: location.display_name,
                street: location.address?.road ?? "",
                number: location.address?.house_number ?? "",
                neighborhood:
                  location.address?.suburb ??
                  location.address?.neighbourhood ??
                  "",
                city:
                  location.address?.city ??
                  location.address?.town ??
                  location.address?.village ??
                  "",
                state: location.address?.state ?? "",
                country: location.address?.country ?? "",
                zipCode: location.address?.postcode ?? "",
              }

              setLocationName(result.name)

              setLocationAddress(
                `${result.street}, ${result.number || "S/N"}, ${result.state}, ${result.city} - ${result.zipCode}`
              )
            } catch (error) {
              if (error instanceof GeolocationPositionError) {
                switch (error.code) {
                  case error.PERMISSION_DENIED:
                    alert("Permissão de localização negada.")
                    break
                  case error.POSITION_UNAVAILABLE:
                    alert("Não foi possível obter sua localização.")
                    break
                  case error.TIMEOUT:
                    alert("Tempo limite excedido ao obter a localização.")
                    break
                  default:
                    alert(error.message)
                }
              } else {
                console.error(error)
                alert("Ocorreu um erro ao buscar sua localização.")
              }
            }
          }}
        >
          Compartilhar localização
        </Button>
      )}

      {messageType === "template" ? (
        <div className="mb-3 overflow-hidden border border-primary/20 bg-primary/[0.03]">
          <div className="flex items-center justify-between gap-3 border-b border-primary/15 bg-primary/[0.05] px-3 py-2">
            <div className="flex items-center gap-2">
              <div className="flex size-6 items-center justify-center bg-primary text-primary-foreground">
                <Sparkles className="size-3.5" />
              </div>
              <div>
                <p className="text-xs font-medium">Meta template</p>
                <p className="text-[10px] text-muted-foreground">
                  Only approved templates can be sent.
                </p>
              </div>
            </div>
            <Badge variant="outline" className="text-[9px]">
              Cloud API
            </Badge>
          </div>
          <div className="grid gap-2 p-3">
            <Select
              items={approvedTemplates.map((template) => ({
                value: template.id,
                label: `${template.name} · ${template.language}`,
              }))}
              value={templateId || undefined}
              onValueChange={(value) => {
                setTemplateId(String(value))
                setTemplateValues({})
                setError(null)
              }}
              disabled={
                disabled || templatesLoading || approvedTemplates.length === 0
              }
            >
              <SelectTrigger className="w-full bg-background">
                <SelectValue
                  placeholder={
                    templatesLoading
                      ? "Loading approved templates…"
                      : "Choose an approved template"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {approvedTemplates.map((template) => (
                  <SelectItem key={template.id} value={template.id}>
                    {template.name} · {template.language}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {templatesError ? (
              <p className="text-[10px] text-destructive">{templatesError}</p>
            ) : null}
            {!templatesLoading &&
            !templatesError &&
            approvedTemplates.length === 0 ? (
              <p className="text-[10px] text-muted-foreground">
                No approved templates are available for this Cloud API number.
              </p>
            ) : null}
            {selectedTemplate ? (
              <>
                <div className="border border-border bg-background px-3 py-2.5 shadow-sm">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="truncate text-[11px] font-medium">
                      {selectedTemplate.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {selectedTemplate.category ?? "Template"}
                    </span>
                  </div>
                  <p className="text-[11px] leading-relaxed whitespace-pre-wrap text-foreground/85">
                    {templatePreview(selectedTemplate, templateValues)}
                  </p>
                </div>
                {templateFields(selectedTemplate).map((field) => (
                  <div key={field.id} className="grid gap-1">
                    <Label htmlFor={`template-${field.id}`}>
                      {field.label}
                    </Label>
                    <Input
                      id={`template-${field.id}`}
                      value={templateValues[field.id] ?? ""}
                      onChange={(event) =>
                        setTemplateValues((previous) => ({
                          ...previous,
                          [field.id]: event.target.value,
                        }))
                      }
                      placeholder={
                        field.parameterType === "media"
                          ? "https://…"
                          : "Value sent to the recipient"
                      }
                      disabled={composing}
                    />
                  </div>
                ))}
              </>
            ) : null}
          </div>
        </div>
      ) : null}

      {["contacts", "interactive"].includes(messageType) ? (
        <div className="mb-2 flex flex-col gap-1.5">
          <Label htmlFor="message-advanced-json">
            {messageType === "contacts"
              ? "Contacts JSON"
              : `${messageType.charAt(0).toUpperCase()}${messageType.slice(1)} JSON`}
          </Label>
          <textarea
            id="message-advanced-json"
            value={advancedJson}
            onChange={(event) => setAdvancedJson(event.target.value)}
            placeholder={
              messageType === "interactive"
                ? '{"type":"button","body":{"text":"Choose an option"},"action":{"buttons":[]}}'
                : '[{"name":{"formatted_name":"Jane Doe"},"phones":[{"phone":"+15551234567"}]}]'
            }
            rows={3}
            disabled={composing}
            className="w-full resize-y rounded-none border border-input bg-transparent px-2.5 py-2 font-mono text-[11px] focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
          />
        </div>
      ) : null}

      {messageType === "reaction" ? (
        <div className="mb-2 grid gap-2 sm:grid-cols-[1fr_120px]">
          <Select
            items={reactionMessages.map((message) => ({
              value: message.external_id ?? message.id,
              label: `${message.direction === "inbound" ? "Incoming" : "Sent"} · ${(message.content ?? message.message_type).slice(0, 36)}`,
            }))}
            value={reactionTarget || defaultReactionTarget || undefined}
            onValueChange={(value) => setReactionTarget(String(value))}
            disabled={disabled || reactionMessages.length === 0}
          >
            <SelectTrigger>
              <SelectValue placeholder="Message to react to" />
            </SelectTrigger>
            <SelectContent>
              {reactionMessages.map((message) => (
                <SelectItem
                  key={message.external_id ?? message.id}
                  value={message.external_id ?? message.id}
                >
                  {message.direction === "inbound" ? "Incoming" : "Sent"} ·{" "}
                  {(message.content ?? message.message_type).slice(0, 36)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            aria-label="Reaction emoji"
            value={reactionEmoji}
            onChange={(event) => setReactionEmoji(event.target.value)}
            placeholder="👍"
            disabled={composing}
          />
        </div>
      ) : null}

      <div className="flex items-end gap-2">
        <AudioRecorder
          disabled={disabled || !onUpload}
          onUpload={onUpload}
          onSend={(data) => handleAudioSend(data)}
          onActiveChange={setRecorderActive}
          onError={setError}
        />
        {!recorderActive ? (
          <>
            <textarea
              ref={composerRef}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder={
                messageType === "text"
                  ? "Type a message… or use /ai or /note"
                  : "Caption or optional message text…"
              }
              rows={1}
              disabled={composing}
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
              disabled={composing}
              aria-label="Send message"
            >
              {isPending ? <LoaderCircle className="animate-spin" /> : <Send />}
            </Button>
          </>
        ) : null}
      </div>
      {aiPending ? (
        <p className="flex items-center gap-1.5 pt-2 text-[10px] text-primary">
          <LoaderCircle className="size-3 animate-spin" />
          AI assistant is reading the conversation…
        </p>
      ) : null}
      {error ? <p className="pt-2 text-xs text-destructive">{error}</p> : null}
    </form>
  )
}

export { MessageComposer }
