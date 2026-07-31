"use client"

import Link from "next/link"
import { SlidersHorizontal, Smartphone } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

function WhatsAppSectionTabs({
  companyId,
  active,
}: {
  companyId: string
  active: "integrations" | "configuration"
}) {
  const tabs = [
    {
      key: "integrations" as const,
      label: "Integration",
      href: `/companies/${companyId}/whatsapp/integrations`,
      icon: Smartphone,
    },
    {
      key: "configuration" as const,
      label: "Configuration",
      href: `/companies/${companyId}/whatsapp/configuration`,
      icon: SlidersHorizontal,
    },
  ]

  return (
    <nav
      aria-label="WhatsApp setup"
      className="flex w-fit items-center gap-1 border-b"
    >
      {tabs.map((tab) => (
        <Link
          key={tab.key}
          href={tab.href}
          className={cn(
            "flex items-center gap-1.5 border-b-2 border-transparent px-2.5 py-2 text-xs text-muted-foreground transition-colors hover:text-foreground",
            active === tab.key && "border-foreground font-medium text-foreground",
          )}
          aria-current={active === tab.key ? "page" : undefined}
        >
          <tab.icon className="size-3.5" />
          {tab.label}
        </Link>
      ))}
    </nav>
  )
}

export { WhatsAppSectionTabs }
