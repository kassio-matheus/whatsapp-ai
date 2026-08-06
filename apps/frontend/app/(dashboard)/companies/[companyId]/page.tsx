"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import {
  Bot,
  LoaderCircle,
  Mail,
  MessageSquareText,
  Phone,
  Plus,
  Trash2,
  Users,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"

import { useApp } from "@/components/app-provider"
import { MemberDialog } from "@/components/companies/member-dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { PageContainer, PageHeader } from "@/components/ui/page-header"
import { SearchInput } from "@/components/ui/search-input"
import { StatCard } from "@/components/ui/stat-card"
import {
  api,
  ApiClientError,
  type Member,
  type WhatsAppIntegration,
} from "@/lib/api"
import { formatDate } from "@/lib/format"

export default function CompanyDashboardPage() {
  const params = useParams<{ companyId: string }>()
  const { token, user, companies } = useApp()
  const companyId = params.companyId ?? ""
  const timezone =
    companies.find((company) => company.id === companyId)?.timezone ?? "UTC"

  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [members, setMembers] = React.useState<Member[]>([])
  const [integrations, setIntegrations] = React.useState<WhatsAppIntegration[]>([])
  const [conversationCount, setConversationCount] = React.useState(0)
  const [memberDialog, setMemberDialog] = React.useState(false)
  const [deletingMember, setDeletingMember] = React.useState<Member | null>(null)
  const [memberSearch, setMemberSearch] = React.useState("")

  React.useEffect(() => {
    if (!token) {
      return
    }
    const currentToken = token
    let cancelled = false
    async function load() {
      try {
        const [membersResult, integrationsResult, conversationsResult] =
          await Promise.all([
            api.listMembers(companyId, currentToken),
            api.listInstances(currentToken, { company_id: companyId }),
            api.listConversations(currentToken, {
              company_id: companyId,
              limit: 100,
            }),
          ])
        if (!cancelled) {
          setMembers(membersResult)
          setIntegrations(integrationsResult)
          setConversationCount(conversationsResult.length)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiClientError && (err.status === 403 || err.status === 404)) {
            setError(err.message)
          } else {
            setError(err instanceof Error ? err.message : "Failed to load data.")
          }
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [companyId, token])

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <LoaderCircle className="size-5 animate-spin" />
        </div>
      </PageContainer>
    )
  }

  if (error) {
    return (
      <PageContainer>
        <Card className="p-0">
          <EmptyState
            title="Something went wrong"
            description={error}
            action={
              <Button variant="outline" onClick={() => window.location.reload()}>
                Retry
              </Button>
            }
          />
        </Card>
      </PageContainer>
    )
  }

  const canManageMembers = user?.is_super_admin ?? false

  const memberQuery = memberSearch.trim().toLowerCase()
  const visibleMembers = React.useMemo(
    () =>
      memberQuery
        ? members.filter((member) =>
            member.email.toLowerCase().includes(memberQuery)
          )
        : members,
    [members, memberQuery]
  )

  async function handleDeleteMember() {
    if (!token || !deletingMember) {
      return
    }
    await api.deleteMember(companyId, deletingMember.id, token)
    setMembers((previous) =>
      previous.filter((member) => member.id !== deletingMember.id),
    )
    setDeletingMember(null)
  }

  return (
    <PageContainer>
      <PageHeader
        title="Overview"
        description="A summary of this company's workspace."
      >
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link href={`/companies/${companyId}/whatsapp`} />}
        >
          <MessageSquareText />
          WhatsApp
        </Button>
        <Button nativeButton={false} render={<Link href="/ai" />}>
          <Bot />
          AI Chat
        </Button>
      </PageHeader>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard
          index={0}
          label="Members"
          value={members.length}
          icon={<Users />}
          hint="People in this company"
        />
        <StatCard
          index={1}
          label="Integrations"
          value={integrations.length}
          icon={<MessageSquareText />}
          hint="Connected WhatsApp channels"
        />
        <StatCard
          index={2}
          label="Open conversations"
          value={conversationCount}
          icon={<Phone />}
          hint="Across active integrations"
        />
      </div>

      <Card className="p-0">
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle>Members</CardTitle>
            <div className="flex items-center gap-2">
              <SearchInput
                value={memberSearch}
                onValueChange={setMemberSearch}
                placeholder="Search members…"
                shortcut="/"
                containerClassName="w-52 sm:w-60"
              />
              {canManageMembers ? (
                <Button size="sm" onClick={() => setMemberDialog(true)}>
                  <Plus />
                  Add member
                </Button>
              ) : null}
            </div>
          </div>
        </CardHeader>
        {members.length === 0 ? (
          <CardContent>
            <EmptyState
              icon={<Users />}
              title="No members yet"
              description="Members can log in and access this company's WhatsApp workspace and AI chat."
            />
          </CardContent>
        ) : visibleMembers.length === 0 ? (
          <CardContent>
            <EmptyState
              icon={<Users />}
              title="No matching members"
              description="Try a different search term."
            />
          </CardContent>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Created</TableHead>
                {canManageMembers ? <TableHead className="w-10" /> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleMembers.map((member, index) => (
                <TableRow
                  key={member.id}
                  className="stagger-enter"
                  style={{ animationDelay: `${index * 40}ms` }}
                >
                  <TableCell>
                    <span className="flex items-center gap-2 font-medium">
                      <Mail className="size-4 text-muted-foreground" />
                      {member.email}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={member.is_active ? "secondary" : "outline"}
                    >
                      {member.is_active
                        ? member.is_verified
                          ? "Active"
                          : "Pending"
                        : "Deactivated"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {member.is_super_admin ? "Super admin" : "Member"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(member.created_at, timezone)}
                  </TableCell>
                  {canManageMembers ? (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setDeletingMember(member)}
                      >
                        <Trash2 />
                      </Button>
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {canManageMembers ? (
        <MemberDialog
          open={memberDialog}
          onOpenChange={setMemberDialog}
          onSave={async (email, password) => {
            if (!token) {
              return
            }
            const member = await api.createMember(
              companyId,
              { email, password },
              token,
            )
            setMembers((previous) => [...previous, member])
          }}
        />
      ) : null}

      <ConfirmDialog
        open={deletingMember !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeletingMember(null)
          }
        }}
        title="Remove member"
        description={`Remove ${deletingMember?.email ?? "this member"} from this company? The account will be deactivated.`}
        confirmLabel="Remove"
        destructive
        onConfirm={handleDeleteMember}
      />
    </PageContainer>
  )
}
