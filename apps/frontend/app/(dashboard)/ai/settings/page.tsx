"use client"

import * as React from "react"
import {
  CircleAlert,
  KeyRound,
  LoaderCircle,
  Save,
  Sparkles,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
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

import { useApp } from "@/components/app-provider"
import { LLMLogo } from "@/components/ai/llm-logos"
import { EmptyState } from "@/components/ui/empty-state"
import { PageContainer, PageHeader } from "@/components/ui/page-header"
import {
  api,
  ApiClientError,
  type AIGlobalSettings,
  type LLMProvider,
  type ReasoningLevel,
} from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

const LLM_PROVIDERS: Array<{
  value: LLMProvider
  label: string
  defaultModel: string
  description: string
}> = [
  {
    value: "deepseek",
    label: "DeepSeek",
    defaultModel: "deepseek-v4-flash",
    description: "Fast and cost-effective reasoning models.",
  },
  {
    value: "openai",
    label: "OpenAI",
    defaultModel: "gpt-5.6-luna",
    description: "General-purpose frontier models.",
  },
  {
    value: "gemini",
    label: "Gemini",
    defaultModel: "gemini-3.5-flash-lite",
    description: "Google multimodal models with deep thinking.",
  },
  {
    value: "groq",
    label: "Groq",
    defaultModel: "llama-3.1-8b-instant",
    description: "High-performance reasoning models.",
  },
]

const REASONING_LEVELS: Array<{
  value: ReasoningLevel
  label: string
  description: string
}> = [
  { value: "minimal", label: "Minimal", description: "Fastest responses" },
  { value: "low", label: "Low", description: "Light reasoning" },
  { value: "medium", label: "Medium", description: "Balanced reasoning" },
  { value: "high", label: "High", description: "Most thorough reasoning" },
]

export default function AISettingsPage() {
  const { token } = useApp()

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  const [settings, setSettings] = React.useState<AIGlobalSettings | null>(null)
  const [selectedProvider, setSelectedProvider] =
    React.useState<LLMProvider | null>(null)
  const [providerModels, setProviderModels] = React.useState<
    Record<LLMProvider, string>
  >({ deepseek: "", openai: "", gemini: "", groq: "" })
  const [providerKeys, setProviderKeys] = React.useState<
    Record<LLMProvider, string>
  >({ deepseek: "", openai: "", gemini: "", groq: "" })
  const [providerThinking, setProviderThinking] = React.useState<
    Record<
      LLMProvider,
      { supportsThinking: boolean; reasoning: ReasoningLevel }
    >
  >({
    deepseek: { supportsThinking: true, reasoning: "medium" },
    openai: { supportsThinking: true, reasoning: "medium" },
    gemini: { supportsThinking: true, reasoning: "medium" },
    groq: { supportsThinking: true, reasoning: "medium" },
  })

  const load = React.useCallback(
    async (showLoader = false) => {
      if (!token) {
        return
      }
      if (showLoader) {
        setIsLoading(true)
      }
      try {
        const result = await api.getAIGlobalSettings(token)
        setSettings(result)
        setSelectedProvider(result.selected_provider)
        setProviderModels(
          LLM_PROVIDERS.reduce(
            (acc, provider) => {
              acc[provider.value] =
                result.providers[provider.value].model ?? provider.defaultModel
              return acc
            },
            { deepseek: "", openai: "", gemini: "", groq: "" } as Record<
              LLMProvider,
              string
            >
          )
        )
        setProviderThinking(
          LLM_PROVIDERS.reduce(
            (acc, provider) => {
              acc[provider.value] = {
                supportsThinking:
                  result.providers[provider.value].supports_thinking,
                reasoning: result.providers[provider.value].reasoning_effort,
              }
              return acc
            },
            {
              deepseek: { supportsThinking: true, reasoning: "medium" },
              openai: { supportsThinking: true, reasoning: "medium" },
              gemini: { supportsThinking: true, reasoning: "medium" },
              groq: { supportsThinking: true, reasoning: "medium" },
            } as Record<
              LLMProvider,
              { supportsThinking: boolean; reasoning: ReasoningLevel }
            >
          )
        )
        setProviderKeys({ deepseek: "", openai: "", gemini: "", groq: "" })
        setError(null)
      } catch (err) {
        setError(
          err instanceof ApiClientError
            ? err.message
            : "Could not load the AI settings."
        )
      } finally {
        setIsLoading(false)
      }
    },
    [token]
  )

  React.useEffect(() => {
    void load(true)
  }, [load])

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    if (!token) {
      return
    }
    setSaving(true)
    setError(null)
    try {
      const result = await api.updateAIGlobalSettings(
        {
          selected_provider: selectedProvider,
          deepseek_model: providerModels.deepseek.trim() || "deepseek-v4-flash",
          openai_model: providerModels.openai.trim() || "gpt-5.6-luna",
          gemini_model: providerModels.gemini.trim() || "gemini-3.5-flash-lite",
          groq_model: providerModels.groq.trim() || "llama-3.1-8b-instant",
          deepseek_api_key: providerKeys.deepseek.trim() || null,
          openai_api_key: providerKeys.openai.trim() || null,
          gemini_api_key: providerKeys.gemini.trim() || null,
          groq_api_key: providerKeys.groq.trim() || null,
          deepseek_reasoning_effort: providerThinking.deepseek.reasoning,
          openai_reasoning_effort: providerThinking.openai.reasoning,
          gemini_reasoning_effort: providerThinking.gemini.reasoning,
          groq_reasoning_effort: providerThinking.groq.reasoning,
          deepseek_supports_thinking:
            providerThinking.deepseek.supportsThinking,
          openai_supports_thinking: providerThinking.openai.supportsThinking,
          gemini_supports_thinking: providerThinking.gemini.supportsThinking,
          groq_supports_thinking: providerThinking.groq.supportsThinking,
        },
        token
      )
      setSettings(result)
      setSelectedProvider(result.selected_provider)
      setProviderThinking(
        LLM_PROVIDERS.reduce(
          (acc, provider) => {
            acc[provider.value] = {
              supportsThinking:
                result.providers[provider.value].supports_thinking,
              reasoning: result.providers[provider.value].reasoning_effort,
            }
            return acc
          },
          {
            deepseek: { supportsThinking: true, reasoning: "medium" },
            openai: { supportsThinking: true, reasoning: "medium" },
            gemini: { supportsThinking: true, reasoning: "medium" },
            groq: { supportsThinking: true, reasoning: "medium" },
          } as Record<
            LLMProvider,
            { supportsThinking: boolean; reasoning: ReasoningLevel }
          >
        )
      )
      setProviderKeys({ deepseek: "", openai: "", gemini: "", groq: "" })
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Could not save the AI settings."
      )
    } finally {
      setSaving(false)
    }
  }

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <LoaderCircle className="size-5 animate-spin" />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <PageHeader
        title="AI Settings"
        description="Configure the global AI models used across the platform, including the WhatsApp assistant."
      >
        <Badge variant="outline">
          <Sparkles className="size-3" />
          Global
        </Badge>
      </PageHeader>

      {error && !settings ? (
        <Card className="p-0">
          <EmptyState
            icon={<CircleAlert />}
            title="Something went wrong"
            description={error}
            action={
              <Button variant="outline" onClick={() => void load(true)}>
                Retry
              </Button>
            }
          />
        </Card>
      ) : (
        <form
          onSubmit={(event) => void handleSave(event)}
          className="flex w-full flex-col gap-4"
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs">
                <Sparkles className="size-4" />
                AI provider
              </CardTitle>
              <CardDescription>
                Pick the primary provider. If it fails, the remaining providers
                with a key are tried in order. The chosen provider always moves to the front of the chain.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="grid gap-2 sm:grid-cols-3">
                {LLM_PROVIDERS.map((provider) => {
                  const isSelected = selectedProvider === provider.value
                  const configured =
                    settings?.providers[provider.value]?.configured

                  const model: string | undefined | null =
                    settings?.providers[provider.value]?.model
                  return (
                    <button
                      key={provider.value}
                      type="button"
                      onClick={() => setSelectedProvider(provider.value)}
                      className={cn(
                        "flex flex-col gap-2 rounded-none border p-3 text-start transition-colors",
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "hover:border-border hover:bg-accent"
                      )}
                    >
                      <span className="flex items-center justify-between">
                        <span className="flex size-7 items-center justify-center rounded-full border bg-muted/40">
                          <LLMLogo
                            provider={provider.value}
                            className="size-4"
                          />
                        </span>
                        <span
                          className={cn(
                            "flex size-3.5 items-center justify-center rounded-full border",
                            isSelected && "border-primary"
                          )}
                        >
                          {isSelected ? (
                            <span className="size-2 rounded-full bg-primary" />
                          ) : null}
                        </span>
                      </span>
                      <span className="text-xs font-medium">
                        {provider.label}
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {model || provider.defaultModel}
                      </span>
                      {configured ? (
                        <Badge
                          variant="secondary"
                          className="w-fit bg-green-50 text-[10px]"
                        >
                          key saved
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="w-fit text-[10px]">
                          no key
                        </Badge>
                      )}
                    </button>
                  )
                })}
              </div>
              <div className="flex items-center justify-between">
                <p className="text-[11px] text-muted-foreground">
                  {selectedProvider
                    ? `${LLM_PROVIDERS.find((p) => p.value === selectedProvider)?.label} will be tried first.`
                    : "No provider selected — the default order is used."}
                </p>
                {selectedProvider ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedProvider(null)}
                  >
                    Reset to default order
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs">
                <Sparkles className="size-4" />
                Model & thinking
              </CardTitle>
              <CardDescription>
                Set a model per provider and choose how much thinking effort the
                AI spends on each response. The model needs to support: A large
                number of parameters and JSON Schema.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {LLM_PROVIDERS.map((provider) => {
                const thinking = providerThinking[provider.value]
                return (
                  <div
                    key={provider.value}
                    className="flex flex-col gap-3 border-t pt-4 first:border-t-0 first:pt-0"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="inline-flex items-center gap-1.5 text-xs font-medium">
                        <LLMLogo
                          provider={provider.value}
                          className="size-3.5"
                        />
                        {provider.label}
                      </span>
                      <label className="flex cursor-pointer items-center gap-2 text-[11px] text-muted-foreground">
                        Supports thinking
                        <Switch
                          checked={thinking.supportsThinking}
                          onCheckedChange={(checked) =>
                            setProviderThinking((previous) => ({
                              ...previous,
                              [provider.value]: {
                                ...previous[provider.value],
                                supportsThinking: checked,
                              },
                            }))
                          }
                        />
                      </label>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor={`model-${provider.value}`}>Model</Label>
                      <Input
                        id={`model-${provider.value}`}
                        value={providerModels[provider.value]}
                        onChange={(event) =>
                          setProviderModels((previous) => ({
                            ...previous,
                            [provider.value]: event.target.value,
                          }))
                        }
                        placeholder={provider.defaultModel}
                        className="font-mono"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor={`reasoning-${provider.value}`}>
                        Thinking power
                      </Label>
                      <Select
                        items={REASONING_LEVELS.map((level) => ({
                          value: level.value,
                          label: level.label,
                        }))}
                        value={thinking.reasoning}
                        onValueChange={(value) =>
                          setProviderThinking((previous) => ({
                            ...previous,
                            [provider.value]: {
                              ...previous[provider.value],
                              reasoning: value as ReasoningLevel,
                            },
                          }))
                        }
                        disabled={!thinking.supportsThinking}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {REASONING_LEVELS.map((level) => (
                            <SelectItem key={level.value} value={level.value}>
                              {level.label} — {level.description}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs">
                <KeyRound className="size-4" />
                API keys
              </CardTitle>
              <CardDescription>
                Keys are encrypted and never shown again. Leave a field empty to
                keep the current key.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col divide-y">
              {LLM_PROVIDERS.map((provider) => {
                const configured =
                  settings?.providers[provider.value]?.configured
                return (
                  <div
                    key={provider.value}
                    className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-medium">
                        <span className="inline-flex items-center gap-1.5">
                          <LLMLogo
                            provider={provider.value}
                            className="size-3.5"
                          />
                          {provider.label}
                        </span>
                      </span>
                      {configured ? (
                        <Badge variant="secondary" className="text-[10px]">
                          key saved
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px]">
                          no key
                        </Badge>
                      )}
                    </div>
                    <Input
                      type="password"
                      autoComplete="off"
                      placeholder={
                        configured
                          ? "Saved — type a new key to replace it"
                          : "Paste your API key"
                      }
                      value={providerKeys[provider.value]}
                      onChange={(event) =>
                        setProviderKeys((previous) => ({
                          ...previous,
                          [provider.value]: event.target.value,
                        }))
                      }
                    />
                  </div>
                )
              })}
            </CardContent>
          </Card>

          {error ? <p className="text-xs text-destructive">{error}</p> : null}

          <div className="flex items-center justify-end gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? <LoaderCircle className="animate-spin" /> : <Save />}
              Save settings
            </Button>
          </div>
        </form>
      )}
    </PageContainer>
  )
}
