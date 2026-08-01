"use client"

import Link from "next/link"
import {
  LayoutTemplate,
  MessagesSquare,
  Smartphone,
  UserRound,
} from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

function WhatsAppSectionTabs({
  companyId,
  active,
}: {
  companyId: string
  active: "instances" | "contacts" | "conversations" | "templates"
}) {
  const tabs = [
    {
      key: "instances" as const,
      label: "Instances",
      href: `/companies/${companyId}/whatsapp/instances`,
      icon: Smartphone,
    },
    {
      key: "contacts" as const,
      label: "Contacts",
      href: `/companies/${companyId}/whatsapp/contacts`,
      icon: UserRound,
    },
    {
      key: "conversations" as const,
      label: "Conversations",
      href: `/companies/${companyId}/whatsapp/conversations`,
      icon: MessagesSquare,
    },
    {
      key: "templates" as const,
      label: "Templates",
      href: `/companies/${companyId}/whatsapp/templates`,
      icon: LayoutTemplate,
    },
  ]

  return (
    <nav
      aria-label="WhatsApp sections"
      className="flex w-fit animate-fade-in items-center gap-1 border-b"
    >
      {tabs.map((tab) => {
        const isActive = active === tab.key
        return (
          <Link
            key={tab.key}
            href={tab.href}
            className={cn(
              "relative flex items-center gap-1.5 px-2.5 py-2 text-xs text-muted-foreground transition-colors after:absolute after:inset-x-0 after:-bottom-px after:h-px after:origin-left after:scale-x-0 after:bg-foreground after:transition-transform after:duration-200 hover:text-foreground",
              isActive && "font-medium text-foreground after:scale-x-100"
            )}
            aria-current={isActive ? "page" : undefined}
          >
            <tab.icon className="size-3.5" />
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}

export { WhatsAppSectionTabs }
