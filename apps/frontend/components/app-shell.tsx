"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  Bot,
  Building2,
  ChevronRight,
  ChevronsUpDown,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  Plus,
  ShieldCheck,
  Smartphone,
  Sparkles,
  UserRound,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@workspace/ui/components/avatar"
import { Badge } from "@workspace/ui/components/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@workspace/ui/components/sidebar"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { cn } from "@workspace/ui/lib/utils"

import { useApp } from "@/components/app-provider"
import { ThemeToggle } from "@/components/theme-toggle"
import { getInitials } from "@/lib/format"
import { WhatsAppIcon } from "@/components/ui/whatsapp-icon"

type NavItem = {
  title: string
  icon: React.ComponentType<{ className?: string }>
  buildHref: (companyId: string | null | undefined) => string
  children?: NavItem[]
}

const WHATSAPP_SUB_NAV: NavItem[] = [
  {
    title: "Instances",
    icon: Smartphone,
    buildHref: (companyId: string | null | undefined) =>
      `/companies/${companyId ?? ""}/whatsapp/instances`,
  },
  {
    title: "Contacts",
    icon: UserRound,
    buildHref: (companyId: string | null | undefined) =>
      `/companies/${companyId ?? ""}/whatsapp/contacts`,
  },
  {
    title: "Conversations",
    icon: MessagesSquare,
    buildHref: (companyId: string | null | undefined) =>
      `/companies/${companyId ?? ""}/whatsapp/conversations`,
  },
]

const BASE_NAV: NavItem[] = [
  {
    title: "Dashboard",
    icon: LayoutDashboard,
    buildHref: (companyId: string | null | undefined) =>
      `/companies/${companyId ?? ""}`,
  },
  {
    title: "WhatsApp",
    icon: WhatsAppIcon,
    buildHref: (companyId: string | null | undefined) =>
      `/companies/${companyId ?? ""}/whatsapp`,
    children: WHATSAPP_SUB_NAV,
  },
  {
    title: "AI Chat",
    icon: Bot,
    buildHref: () => "/ai",
  },
]

function CompanySwitcher() {
  const { user, companies, currentCompanyId, switchCompany } = useApp()

  if (!user?.is_super_admin) {
    return (
      <div className="px-2 py-1.5 group-data-[collapsible=icon]:px-0">
        <div className="flex items-center gap-2 px-2 py-1.5 group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <Building2 className="size-4 shrink-0 text-muted-foreground" />
          <div className="flex min-w-0 flex-col group-data-[collapsible=icon]:hidden">
            <span className="truncate text-xs font-medium">
              {companies.find((c) => c.id === user?.company_id)?.name ??
                "No company"}
            </span>
            <span className="text-[10px] text-muted-foreground">Company</span>
          </div>
        </div>
      </div>
    )
  }

  if (companies.length === 0) {
    return (
      <Link
        href="/companies"
        className="mx-2 flex items-center gap-2 rounded-none border border-dashed border-border px-2 py-2 text-xs text-muted-foreground group-data-[collapsible=icon]:mx-0 group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
      >
        <Plus className="size-4" />
        <span className="group-data-[collapsible=icon]:hidden">
          Create your first company
        </span>
      </Link>
    )
  }

  return (
    <div className="px-2 group-data-[collapsible=icon]:px-0">
      <Select
        items={companies.map((company) => ({
          value: company.id,
          label: company.name,
        }))}
        value={currentCompanyId ?? undefined}
        onValueChange={(value) => switchCompany(String(value))}
      >
        <SelectTrigger className="w-full justify-start gap-2 bg-transparent group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:gap-0 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:[&_[data-slot=select-value]]:hidden group-data-[collapsible=icon]:[&>svg:last-child]:hidden">
          <Building2 className="size-4 shrink-0 text-muted-foreground" />
          <SelectValue className="truncate text-xs font-medium" />
        </SelectTrigger>
        <SelectContent>
          {companies.map((company) => (
            <SelectItem key={company.id} value={company.id}>
              {company.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function UserBlock() {
  const { user, signOut } = useApp()

  if (!user) {
    return null
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-none px-2 py-1.5 text-start transition-colors outline-none group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground"
          >
            <Avatar size="sm">
              <AvatarFallback className="bg-primary text-[10px] font-medium text-primary-foreground">
                {getInitials(user.email)}
              </AvatarFallback>
            </Avatar>
            <div className="flex min-w-0 flex-1 flex-col group-data-[collapsible=icon]:hidden">
              <span className="flex items-center gap-1.5 truncate text-xs font-medium">
                {user.is_super_admin ? (
                  <ShieldCheck className="size-3 shrink-0 text-primary" />
                ) : null}
                <span className="truncate">{user.email}</span>
              </span>
              <span className="text-[10px] text-muted-foreground">
                {user.is_super_admin ? "Super admin" : "Member"}
              </span>
            </div>
            <ChevronsUpDown className="size-3 shrink-0 text-muted-foreground group-data-[collapsible=icon]:hidden" />
          </button>
        }
      />
      <DropdownMenuContent align="start" side="right" className="min-w-52">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            <div className="flex flex-col gap-1">
              <span className="truncate font-medium">{user.email}</span>
              {user.is_super_admin ? (
                <Badge variant="secondary" className="w-fit text-[10px]">
                  <ShieldCheck />
                  Super admin
                </Badge>
              ) : (
                <span className="text-[10px] font-normal text-muted-foreground">
                  Member
                </span>
              )}
            </div>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        {user.is_super_admin ? (
          <DropdownMenuItem render={<Link href="/companies" />}>
            <Plus />
            Create company
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem variant="destructive" onClick={signOut}>
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function NavLinks() {
  const { user, currentCompanyId, companies } = useApp()
  const pathname = usePathname()

  const companyId =
    currentCompanyId ??
    (user?.is_super_admin ? companies[0]?.id : user?.company_id)

  const nav = BASE_NAV.map((item) => {
    const href = item.buildHref(companyId)
    const isActive =
      item.title === "AI Chat"
        ? pathname.startsWith("/ai")
        : item.title === "WhatsApp"
          ? pathname.startsWith(`/companies/${companyId ?? ""}/whatsapp`)
          : pathname === href

    return {
      ...item,
      href,
      isActive,
    }
  })

  return (
    <>
      <SidebarMenu>
        {nav.map((item) => {
          if (item.title === "WhatsApp") {
            return (
              <WhatsAppMenuItem
                key={item.title}
                item={item}
                companyId={companyId}
                pathname={pathname}
              />
            )
          }

          return (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                isActive={item.isActive}
                render={<Link href={item.href} />}
                tooltip={item.title}
              >
                <item.icon />
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )
        })}
      </SidebarMenu>

      {user?.is_super_admin ? (
        <>
          <SidebarSeparator className="my-2" />
          <SidebarGroupLabel>Management</SidebarGroupLabel>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={
                  pathname === "/companies" || pathname === "/companies/new"
                }
                render={<Link href="/companies" />}
                tooltip="Companies"
              >
                <Building2 />
                <span>Companies</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </>
      ) : null}
    </>
  )
}

function WhatsAppMenuItem({
  item,
  companyId,
  pathname,
}: {
  item: NavItem & { href: string; isActive: boolean }
  companyId: string | null | undefined
  pathname: string
}) {
  const [isOpen, setIsOpen] = React.useState(item.isActive)

  React.useEffect(() => {
    if (item.isActive) {
      setIsOpen(true)
    }
  }, [item.isActive])

  const childIsActive = (href: string) => pathname.startsWith(href)

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        isActive={item.isActive}
        tooltip="WhatsApp"
        onClick={() => setIsOpen((open) => !open)}
        className="justify-between"
      >
        <item.icon />
        <span>{item.title}</span>
        <ChevronRight
          className={cn(
            "ms-auto transition-transform duration-200 group-data-[collapsible=icon]:hidden",
            isOpen && "rotate-90"
          )}
        />
      </SidebarMenuButton>
      {isOpen && companyId ? (
        <SidebarMenuSub>
          {item.children?.map((child, index) => {
            const href = child.buildHref(companyId)
            return (
              <SidebarMenuSubItem
                key={child.title}
                className="stagger-enter"
                style={{ animationDelay: `${index * 40}ms` }}
              >
                <SidebarMenuSubButton
                  isActive={childIsActive(href)}
                  render={<Link href={href} />}
                >
                  <child.icon />
                  <span>{child.title}</span>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            )
          })}
        </SidebarMenuSub>
      ) : null}
    </SidebarMenuItem>
  )
}

function AppShell({ children }: { children: React.ReactNode }) {
  const { isLoading, user, companies, currentCompanyId } = useApp()
  const router = useRouter()
  const pathname = usePathname()

  React.useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login")
    }
  }, [isLoading, user, router])

  const companyName =
    companies.find((company) => company.id === currentCompanyId)?.name ?? null

  if (isLoading || !user) {
    return (
      <div className="flex min-h-svh flex-col">
        <div className="flex flex-1">
          <div className="hidden w-64 shrink-0 flex-col gap-4 border-e bg-sidebar p-3 md:flex">
            <Skeleton className="h-8 rounded-none" />
            <Skeleton className="h-8 rounded-none" />
            <Skeleton className="h-8 rounded-none" />
            <Skeleton className="h-8 rounded-none" />
          </div>
          <div className="flex flex-1 flex-col gap-4 p-6">
            <Skeleton className="h-6 w-48 rounded-none" />
            <Skeleton className="h-24 w-full rounded-none" />
            <Skeleton className="h-24 w-full rounded-none" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <UserBlock />
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Company</SidebarGroupLabel>
            <CompanySwitcher />
          </SidebarGroup>
          <SidebarSeparator className="my-2" />
          <SidebarGroup>
            <SidebarGroupLabel>Workspace</SidebarGroupLabel>
            <NavLinks />
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <div className="flex items-center justify-between px-2 py-1.5 group-data-[collapsible=icon]:justify-start group-data-[collapsible=icon]:px-0">
            <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground group-data-[collapsible=icon]:hidden">
              <Sparkles className="size-3" />
              Workspace
            </span>
            <SidebarTrigger className="group-data-[collapsible=icon]:size-8" />
          </div>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
      <SidebarInset>
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ms-1 md:hidden" />
          <div className="flex min-w-0 items-center gap-2 text-xs">
            {companyName ? (
              <>
                <span className="hidden truncate font-medium md:block">
                  {companyName}
                </span>
                <span className="hidden text-muted-foreground md:block">/</span>
              </>
            ) : null}
            <span
              className={cn(
                "truncate text-muted-foreground",
                companyName ? "md:hidden" : ""
              )}
            >
              {user.email}
            </span>
          </div>
          <div className="ms-auto" />
          <ThemeToggle />
          <Badge variant="outline" className="text-[10px]">
            {user.is_super_admin ? "Super admin" : "Member"}
          </Badge>
        </header>
        <div key={pathname} className="animate-fade-up min-h-0 flex-1">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export { AppShell }
