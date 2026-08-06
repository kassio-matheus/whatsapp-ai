"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  Building2,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card } from "@workspace/ui/components/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"

import { useApp } from "@/components/app-provider"
import { CompanyDialog } from "@/components/companies/company-dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { PageContainer, PageHeader } from "@/components/ui/page-header"
import { SearchInput } from "@/components/ui/search-input"
import { api } from "@/lib/api"
import { formatDate } from "@/lib/format"

export default function CompaniesPage() {
  const { token, user, companies, refreshCompanies, switchCompany } = useApp()
  const router = useRouter()

  const [isLoading, setIsLoading] = React.useState(true)
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [renaming, setRenaming] = React.useState<string | null>(null)
  const [deleting, setDeleting] = React.useState<string | null>(null)
  const [search, setSearch] = React.useState("")

  React.useEffect(() => {
    if (!token || !user?.is_super_admin) {
      return
    }
    let cancelled = false
    async function load() {
      try {
        await refreshCompanies()
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
  }, [token, user, refreshCompanies])

  async function handleCreate(name: string, timezone: string) {
    if (!token) {
      return
    }
    const company = await api.createCompany({ name, timezone }, token)
    await refreshCompanies()
    switchCompany(company.id)
    router.push(`/companies/${company.id}`)
  }

  async function handleRename(name: string, timezone: string) {
    if (!token || !renaming) {
      return
    }
    await api.updateCompany(renaming, { name, timezone }, token)
    await refreshCompanies()
    setRenaming(null)
  }

  async function handleDelete() {
    if (!token || !deleting) {
      return
    }
    await api.deleteCompany(deleting, token)
    await refreshCompanies()
    setDeleting(null)
  }

  const renameTarget = companies.find((company) => company.id === renaming)
  const deleteTarget = companies.find((company) => company.id === deleting)

  const query = search.trim().toLowerCase()
  const visibleCompanies = React.useMemo(
    () =>
      query
        ? companies.filter((company) =>
            company.name.toLowerCase().includes(query)
          )
        : companies,
    [companies, query]
  )

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
        title="Companies"
        description="Manage the companies in this workspace. Only super admins can access this area."
      >
        <Button onClick={() => setDialogOpen(true)}>
          <Plus />
          New company
        </Button>
      </PageHeader>

      {companies.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={<Building2 />}
            title="No companies yet"
            description="Create your first company to get started. Each company gets its own dashboard, WhatsApp workspace, and AI assistant."
            action={
              <Button onClick={() => setDialogOpen(true)}>
                <Plus />
                Create company
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <SearchInput
                value={search}
                onValueChange={setSearch}
                placeholder="Search companies…"
                shortcut="/"
                containerClassName="w-full sm:w-72"
              />
              <Badge
                variant={search.trim() ? "outline" : "secondary"}
                className="shrink-0 text-[10px]"
              >
                {visibleCompanies.length}
                {search.trim() ? ` / ${companies.length}` : ""} companies
              </Badge>
            </div>
            <Button variant="outline" onClick={() => setDialogOpen(true)}>
              <Plus />
              New company
            </Button>
          </div>
          {visibleCompanies.length === 0 ? (
            <Card className="p-0">
              <EmptyState
                title="No matching companies"
                description="Try a different search term."
              />
            </Card>
          ) : (
            <Card className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Timezone</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleCompanies.map((company, index) => (
                    <TableRow
                      key={company.id}
                      className="group stagger-enter"
                      style={{ animationDelay: `${index * 40}ms` }}
                    >
                      <TableCell>
                        <Link
                          href={`/companies/${company.id}`}
                          className="flex items-center gap-2 font-medium hover:underline"
                        >
                          <Building2 className="size-4 text-muted-foreground" />
                          {company.name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {company.timezone}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={company.is_active ? "secondary" : "outline"}
                        >
                          {company.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(company.created_at, company.timezone)}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            render={
                              <Button variant="ghost" size="icon-sm">
                                <MoreHorizontal />
                              </Button>
                            }
                          />
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => {
                                switchCompany(company.id)
                                router.push(`/companies/${company.id}`)
                              }}
                            >
                              Open dashboard
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => {
                                setRenaming(company.id)
                              }}
                            >
                              <Pencil />
                              Update
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => setDeleting(company.id)}
                            >
                              <Trash2 />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </div>
      )}

      <CompanyDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode="create"
        onSave={handleCreate}
      />

      <CompanyDialog
        open={renaming !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRenaming(null)
          }
        }}
        mode="rename"
        initialName={renameTarget?.name ?? ""}
        initialTimezone={renameTarget?.timezone ?? "UTC"}
        onSave={handleRename}
      />

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleting(null)
          }
        }}
        title="Delete company"
        description={
          deleteTarget
            ? `Permanently delete "${deleteTarget.name}"? This will remove the company and its associated data.`
            : "Permanently delete this company?"
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />
    </PageContainer>
  )
}
