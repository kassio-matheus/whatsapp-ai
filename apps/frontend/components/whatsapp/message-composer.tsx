"use client"

import * as React from "react"
import {
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
  Users,
} from "lucide-react"

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

import type { WhatsAppMessage } from "@/lib/api"

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
  { value: "contacts", label: "Contacts", icon: Users },
  { value: "interactive", label: "Interactive", icon: MessageCircleMore },
  { value: "template", label: "Template", icon: FileText },
  { value: "reaction", label: "Reaction", icon: SmilePlus },
]

function MessageComposer({
  messages,
  disabled,
  onSend,
}: {
  messages: WhatsAppMessage[]
  disabled?: boolean
  onSend: (data: ComposerMessageData) => Promise<void>
}) {
  const [messageType, setMessageType] = React.useState("text")
  const [content, setContent] = React.useState("")
  const [mediaUrl, setMediaUrl] = React.useState("")
  const [advancedJson, setAdvancedJson] = React.useState("")
  const [latitude, setLatitude] = React.useState("")
  const [longitude, setLongitude] = React.useState("")
  const [locationName, setLocationName] = React.useState("")
  const [locationAddress, setLocationAddress] = React.useState("")
  const [reactionEmoji, setReactionEmoji] = React.useState("👍")
  const [reactionTarget, setReactionTarget] = React.useState("")
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const reactionMessages = React.useMemo(
    () => messages.filter((message) => message.external_id),
    [messages],
  )
  const defaultReactionTarget =
    reactionMessages[reactionMessages.length - 1]?.external_id ?? ""

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

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (disabled || isPending) {
      return
    }

    const trimmedContent = content.trim()
    const trimmedMediaUrl = mediaUrl.trim()
    let metadata: Record<string, unknown> | undefined

    try {
      if (messageType === "text" && !trimmedContent) {
        throw new Error("Write a message before sending.")
      }
      if (
        ["image", "video", "audio", "document", "sticker"].includes(
          messageType,
        ) && !trimmedMediaUrl
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
            ...(locationAddress.trim() ? { address: locationAddress.trim() } : {}),
          },
        }
      }
      if (["contacts", "interactive", "template"].includes(messageType)) {
        const parsed = parseJsonObject(
          advancedJson,
          messageType === "contacts" ? "Contacts" : `${messageType} payload`,
        )
        metadata = {
          [messageType]: parsed,
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
      setError(null)
      await onSend({
        message_type: messageType,
        content: trimmedContent || undefined,
        media_url: trimmedMediaUrl || undefined,
        metadata,
      })
      setContent("")
      setMediaUrl("")
      setAdvancedJson("")
      setLatitude("")
      setLongitude("")
      setLocationName("")
      setLocationAddress("")
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
    <form onSubmit={(event) => void handleSubmit(event)} className="border-t p-3">
      <div className="flex flex-wrap items-center gap-2 pb-2">
        <Select
          items={MESSAGE_TYPES.map(({ value, label }) => ({ value, label }))}
          value={messageType}
          onValueChange={(value) => {
            setMessageType(String(value))
            setError(null)
          }}
          disabled={disabled || isPending}
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
      </div>

      {isMediaType ? (
        <div className="mb-2 flex flex-col gap-1.5">
          <Label htmlFor="message-media-url">Media ID or public URL</Label>
          <Input
            id="message-media-url"
            value={mediaUrl}
            onChange={(event) => setMediaUrl(event.target.value)}
            placeholder="https://cdn.example.com/file.jpg or Meta media ID"
            disabled={disabled || isPending}
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
            disabled={disabled || isPending}
          />
          <Input
            aria-label="Longitude"
            value={longitude}
            onChange={(event) => setLongitude(event.target.value)}
            placeholder="Longitude"
            disabled={disabled || isPending}
          />
          <Input
            aria-label="Location name"
            value={locationName}
            onChange={(event) => setLocationName(event.target.value)}
            placeholder="Place name (optional)"
            disabled={disabled || isPending}
          />
          <Input
            aria-label="Location address"
            value={locationAddress}
            onChange={(event) => setLocationAddress(event.target.value)}
            placeholder="Address (optional)"
            disabled={disabled || isPending}
          />
        </div>
      ) : null}

      {["contacts", "interactive", "template"].includes(messageType) ? (
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
              messageType === "template"
                ? '{"name":"hello_world","language":{"code":"en_US"}}'
                : messageType === "interactive"
                  ? '{"type":"button","body":{"text":"Choose an option"},"action":{"buttons":[]}}'
                  : '[{"name":{"formatted_name":"Jane Doe"},"phones":[{"phone":"+15551234567"}]}]'
            }
            rows={3}
            disabled={disabled || isPending}
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
            disabled={disabled || isPending || reactionMessages.length === 0}
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
                  {message.direction === "inbound" ? "Incoming" : "Sent"} · {(
                    message.content ?? message.message_type
                  ).slice(0, 36)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            aria-label="Reaction emoji"
            value={reactionEmoji}
            onChange={(event) => setReactionEmoji(event.target.value)}
            placeholder="👍"
            disabled={disabled || isPending}
          />
        </div>
      ) : null}

      <div className="flex items-end gap-2">
        <textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={
            messageType === "text"
              ? "Type a message…"
              : "Caption or optional message text…"
          }
          rows={1}
          disabled={disabled || isPending}
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
          disabled={disabled || isPending}
          aria-label="Send message"
        >
          {isPending ? <LoaderCircle className="animate-spin" /> : <Send />}
        </Button>
      </div>
      {error ? <p className="pt-2 text-xs text-destructive">{error}</p> : null}
    </form>
  )
}

export { MessageComposer }
