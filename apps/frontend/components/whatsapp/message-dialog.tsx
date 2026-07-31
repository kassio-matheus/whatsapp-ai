"use client"

import * as React from "react"
import { LoaderCircle } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import type {
  MessageDirection,
  MessageStatus,
  WhatsAppMessage,
} from "@/lib/api"

function MessageDialog({
  open,
  onOpenChange,
  message,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  message: WhatsAppMessage | null
  onSave: (data: {
    content?: string
    status?: MessageStatus
    direction?: MessageDirection
    message_type?: string
  }) => Promise<void>
}) {
  const [content, setContent] = React.useState("")
  const [status, setStatus] = React.useState<MessageStatus>("sent")
  const [direction, setDirection] = React.useState<MessageDirection>("outbound")
  const [messageType, setMessageType] = React.useState("text")
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!open || !message) {
      return
    }
    setContent(message.content ?? "")
    setStatus(message.status ?? "sent")
    setDirection(message.direction ?? "outbound")
    setMessageType(message.message_type ?? "text")
    setError(null)
  }, [open, message])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setIsPending(true)
    setError(null)
    try {
      await onSave({
        content,
        status,
        direction,
        message_type: messageType,
      })
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={(event) => void handleSubmit(event)}>
          <DialogHeader>
            <DialogTitle>Edit message</DialogTitle>
            <DialogDescription>
              Update the message content or delivery metadata.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="message-content">Content</Label>
              <textarea
                id="message-content"
                value={content}
                onChange={(event) => setContent(event.target.value)}
                rows={3}
                className="w-full resize-y rounded-none border border-input bg-transparent px-2.5 py-2 text-xs focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-2">
                <Label>Direction</Label>
                <Select
                  items={[
                    { value: "inbound", label: "Inbound" },
                    { value: "outbound", label: "Outbound" },
                  ]}
                  value={direction}
                  onValueChange={(value) =>
                    setDirection(value as MessageDirection)
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inbound">Inbound</SelectItem>
                    <SelectItem value="outbound">Outbound</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Status</Label>
                <Select
                  items={[
                    "pending",
                    "sent",
                    "delivered",
                    "read",
                    "failed",
                  ].map((value) => ({ value, label: value }))}
                  value={status}
                  onValueChange={(value) => setStatus(value as MessageStatus)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(["pending", "sent", "delivered", "read", "failed"] as const).map(
                      (item) => (
                        <SelectItem key={item} value={item}>
                          {item}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="message-type">Type</Label>
              <Select
                items={["text", "image", "audio", "video", "document"].map(
                  (value) => ({ value, label: value }),
                )}
                value={messageType}
                onValueChange={(value) => setMessageType(String(value))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["text", "image", "audio", "video", "document"].map((item) => (
                    <SelectItem key={item} value={item}>
                      {item}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {error ? <p className="text-xs text-destructive">{error}</p> : null}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={isPending}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? <LoaderCircle className="animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export { MessageDialog }
