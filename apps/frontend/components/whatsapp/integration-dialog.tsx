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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Switch } from "@workspace/ui/components/switch"

import { api, type IntegrationType, type WhatsAppIntegration } from "@/lib/api"

const ADAPTERS = ["whatsapp_cloud", "baileys", "venom", "whatsapp_web"]
const DEFAULT_ADAPTER = "whatsapp_cloud"

function IntegrationDialog({
  open,
  onOpenChange,
  mode,
  integration,
  companyId,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "create" | "edit"
  integration?: WhatsAppIntegration | null
  companyId: string
  onSave: (data: {
    company_id: string
    name: string
    integration_type: IntegrationType
    adapter: string
    phone_number?: string
    external_account_id?: string
    config?: Record<string, unknown>
  }) => Promise<void>
}) {
  const [name, setName] = React.useState("")
  const [type, setType] = React.useState<IntegrationType>("official")
  const [adapter, setAdapter] = React.useState<string>(DEFAULT_ADAPTER)
  const [phone, setPhone] = React.useState("")
  const [externalAccountId, setExternalAccountId] = React.useState("")
  const [config, setConfig] = React.useState("")
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!open) {
      return
    }
    setName(integration?.name ?? "")
    setType(integration?.integration_type ?? "official")
    setAdapter(integration?.adapter ?? DEFAULT_ADAPTER)
    setPhone(integration?.phone_number ?? "")
    setExternalAccountId(integration?.external_account_id ?? "")
    setConfig(
      integration?.config && Object.keys(integration.config).length > 0
        ? JSON.stringify(integration.config, null, 2)
        : "",
    )
    setError(null)
  }, [open, integration])

  function parseConfig(): Record<string, unknown> | undefined {
    const trimmed = config.trim()
    if (!trimmed) {
      return undefined
    }
    try {
      const parsed = JSON.parse(trimmed) as unknown
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Config must be a JSON object.")
      }
      return parsed as Record<string, unknown>
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : "Invalid JSON config.")
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError("Name is required.")
      return
    }
    let parsedConfig: Record<string, unknown> | undefined
    try {
      parsedConfig = parseConfig()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid config.")
      return
    }
    setIsPending(true)
    setError(null)
    try {
      await onSave({
        company_id: companyId,
        name: trimmedName,
        integration_type: type,
        adapter,
        phone_number: phone.trim() || undefined,
        external_account_id: externalAccountId.trim() || undefined,
        config: parsedConfig,
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
            <DialogTitle>
              {mode === "create" ? "New integration" : `Edit ${integration?.name ?? "integration"}`}
            </DialogTitle>
            <DialogDescription>
              Connect a WhatsApp channel to this company.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="integration-name">Name</Label>
              <Input
                id="integration-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Support line"
                autoFocus
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-2">
                <Label>Type</Label>
                <Select
                  items={[
                    { value: "official", label: "Official (Cloud API)" },
                    { value: "unofficial", label: "Unofficial" },
                  ]}
                  value={type}
                  onValueChange={(value) => setType(value as IntegrationType)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="official">Official (Cloud API)</SelectItem>
                    <SelectItem value="unofficial">Unofficial</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Adapter</Label>
                <Select
                  items={ADAPTERS.map((adapter) => ({
                    value: adapter,
                    label: adapter,
                  }))}
                  value={adapter}
                  onValueChange={(value) => setAdapter(String(value))}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ADAPTERS.map((item) => (
                      <SelectItem key={item} value={item}>
                        {item}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="integration-phone">Phone number</Label>
              <Input
                id="integration-phone"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="+15551234567"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="integration-account">External account ID</Label>
              <Input
                id="integration-account"
                value={externalAccountId}
                onChange={(event) => setExternalAccountId(event.target.value)}
                placeholder="WABA ID or account reference"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="integration-config">Config (JSON)</Label>
              <textarea
                id="integration-config"
                value={config}
                onChange={(event) => setConfig(event.target.value)}
                placeholder='{"business_account_id": "123", "verify_token": "..."}'
                rows={3}
                className="w-full resize-y rounded-none border border-input bg-transparent px-2.5 py-2 font-mono text-xs focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
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
              {mode === "create" ? "Create" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function IntegrationActiveToggle({
  integration,
  token,
  onChange,
}: {
  integration: WhatsAppIntegration
  token: string
  onChange: (updated: WhatsAppIntegration) => void
}) {
  const [isPending, setIsPending] = React.useState(false)

  async function toggle() {
    setIsPending(true)
    try {
      const updated = await api.updateIntegration(
        integration.id,
        { is_active: !integration.is_active },
        token,
      )
      onChange(updated)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Switch
      checked={integration.is_active}
      disabled={isPending}
      onCheckedChange={() => void toggle()}
    />
  )
}

export { IntegrationDialog, IntegrationActiveToggle }
