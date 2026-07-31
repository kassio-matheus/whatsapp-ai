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
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Switch } from "@workspace/ui/components/switch"

import type {
  WhatsAppCloudApiCredentials,
  WhatsAppIntegration,
} from "@/lib/api"

export type CloudApiConnectionFormData = {
  name: string
  credentials: WhatsAppCloudApiCredentials
  subscribe_to_webhooks: boolean
}

const EMPTY_CREDENTIALS: WhatsAppCloudApiCredentials = {
  app_id: "",
  app_secret: "",
  access_token: "",
  business_account_id: "",
  phone_number_id: "",
  webhook_verify_token: "",
  api_version: "v25.0",
}

function CloudApiConnectionDialog({
  open,
  onOpenChange,
  mode,
  integration,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "create" | "edit"
  integration?: WhatsAppIntegration | null
  onSave: (data: CloudApiConnectionFormData) => Promise<void>
}) {
  const [name, setName] = React.useState("")
  const [credentials, setCredentials] =
    React.useState<WhatsAppCloudApiCredentials>(EMPTY_CREDENTIALS)
  const [subscribeToWebhooks, setSubscribeToWebhooks] = React.useState(true)
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!open) {
      return
    }
    setName(integration?.name ?? "")
    setCredentials({ ...EMPTY_CREDENTIALS })
    setSubscribeToWebhooks(true)
    setError(null)
  }, [open, integration])

  function updateCredential(
    field: keyof WhatsAppCloudApiCredentials,
    value: string,
  ) {
    setCredentials((previous) => ({ ...previous, [field]: value }))
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedName = name.trim()
    const normalizedCredentials = Object.fromEntries(
      Object.entries(credentials).map(([key, value]) => [key, value.trim()]),
    ) as WhatsAppCloudApiCredentials

    if (!trimmedName) {
      setError("Give this connection a name.")
      return
    }
    const missingField = Object.entries(normalizedCredentials).find(
      ([, value]) => !value,
    )
    if (missingField) {
      setError("Fill in all Meta credentials to verify the connection.")
      return
    }

    setIsPending(true)
    setError(null)
    try {
      await onSave({
        name: trimmedName,
        credentials: normalizedCredentials,
        subscribe_to_webhooks: subscribeToWebhooks,
      })
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save connection.")
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <form onSubmit={(event) => void handleSubmit(event)}>
          <DialogHeader>
            <DialogTitle>
              {mode === "create"
                ? "Add Meta Cloud API connection"
                : `Replace credentials for ${integration?.name ?? "connection"}`}
            </DialogTitle>
            <DialogDescription>
              Meta validates the WABA and phone number before this connection is
              saved. Secrets are never shown again by the API.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="cloud-connection-name">Connection name</Label>
              <Input
                id="cloud-connection-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Support · Brazil"
                autoFocus
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <CredentialField
                id="cloud-app-id"
                label="Meta App ID"
                value={credentials.app_id}
                onChange={(value) => updateCredential("app_id", value)}
                placeholder="123456789012345"
              />
              <CredentialField
                id="cloud-business-account-id"
                label="WhatsApp Business Account ID"
                value={credentials.business_account_id}
                onChange={(value) => updateCredential("business_account_id", value)}
                placeholder="102030405060708"
              />
              <CredentialField
                id="cloud-phone-number-id"
                label="Phone number ID"
                value={credentials.phone_number_id}
                onChange={(value) => updateCredential("phone_number_id", value)}
                placeholder="109876543210987"
              />
              <CredentialField
                id="cloud-api-version"
                label="Graph API version"
                value={credentials.api_version}
                onChange={(value) => updateCredential("api_version", value)}
                placeholder="v25.0"
              />
              <CredentialField
                id="cloud-app-secret"
                label="App secret"
                value={credentials.app_secret}
                onChange={(value) => updateCredential("app_secret", value)}
                type="password"
              />
              <CredentialField
                id="cloud-access-token"
                label="System user access token"
                value={credentials.access_token}
                onChange={(value) => updateCredential("access_token", value)}
                type="password"
              />
              <CredentialField
                id="cloud-webhook-token"
                label="Webhook verify token"
                value={credentials.webhook_verify_token}
                onChange={(value) => updateCredential("webhook_verify_token", value)}
                type="password"
              />
            </div>

            <div className="flex items-start justify-between gap-4 border-t pt-3">
              <div className="flex flex-col gap-1">
                <Label htmlFor="cloud-subscribe-webhooks">
                  Subscribe to webhooks
                </Label>
                <p className="text-[11px] text-muted-foreground">
                  Receive inbound messages and delivery statuses from Meta.
                </p>
              </div>
              <Switch
                id="cloud-subscribe-webhooks"
                checked={subscribeToWebhooks}
                onCheckedChange={(checked) =>
                  setSubscribeToWebhooks(Boolean(checked))
                }
              />
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
              {mode === "create" ? "Verify and connect" : "Verify and update"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function CredentialField({
  id,
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: React.HTMLInputTypeAttribute
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete="off"
      />
    </div>
  )
}

export { CloudApiConnectionDialog }
