"use client"

import * as React from "react"
import { LoaderCircle, Trash2 } from "lucide-react"

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

import type { ChatSession } from "@/lib/api"

function SystemPromptDialog({
  session,
  onOpenChange,
  onSave,
  onClear,
}: {
  session: ChatSession | null
  onOpenChange: (open: boolean) => void
  onSave: (sessionId: string, systemPrompt: string | null) => Promise<void>
  onClear: (sessionId: string) => Promise<void>
}) {
  const [systemPrompt, setSystemPrompt] = React.useState("")
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (session) {
      setSystemPrompt(session.system_prompt ?? "")
      setError(null)
    }
  }, [session])

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    if (!session) {
      return
    }
    setIsPending(true)
    setError(null)
    try {
      await onSave(session.id, systemPrompt.trim() || null)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setIsPending(false)
    }
  }

  async function handleClear() {
    if (!session) {
      return
    }
    setIsPending(true)
    setError(null)
    try {
      await onClear(session.id)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Dialog open={session !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={(event) => void handleSave(event)}>
          <DialogHeader>
            <DialogTitle>System prompt</DialogTitle>
            <DialogDescription>
              Controls how the assistant behaves for{" "}
              {session?.title ?? "this session"}.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-3">
            <Label htmlFor="system-prompt">Prompt</Label>
            <textarea
              id="system-prompt"
              value={systemPrompt}
              onChange={(event) => setSystemPrompt(event.target.value)}
              placeholder="You are a helpful assistant for this company…"
              rows={5}
              className="w-full resize-y rounded-none border border-input bg-transparent px-2.5 py-2 text-xs focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
            />
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
            <Button
              type="button"
              variant="outline"
              disabled={isPending || !session?.system_prompt}
              onClick={() => void handleClear()}
            >
              {isPending ? <LoaderCircle className="animate-spin" /> : <Trash2 />}
              Clear
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

export { SystemPromptDialog }
