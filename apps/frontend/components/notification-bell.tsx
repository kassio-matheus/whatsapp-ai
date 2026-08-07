"use client"

import * as React from "react"
import Link from "next/link"
import { Bell, BellRing, Check, LoaderCircle } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { ScrollArea } from "@workspace/ui/components/scroll-area"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { cn } from "@workspace/ui/lib/utils"

import { useApp } from "@/components/app-provider"
import { api, type NotificationItem } from "@/lib/api"
import { formatRelative } from "@/lib/format"
import { useInfiniteScroll } from "@/lib/use-infinite-scroll"

const POLL_INTERVAL_MS = 30_000
const PAGE_SIZE = 20

function NotificationBell() {
  const { token, currentCompanyId } = useApp()
  const [unread, setUnread] = React.useState(0)
  const [items, setItems] = React.useState<NotificationItem[]>([])
  const [open, setOpen] = React.useState(false)
  const [loading, setLoading] = React.useState(true)
  const [markingAll, setMarkingAll] = React.useState(false)
  const [hasMore, setHasMore] = React.useState(true)
  const [loadingMore, setLoadingMore] = React.useState(false)
  const loadingMoreRef = React.useRef(false)

  const companyId = currentCompanyId ?? undefined

  const refreshUnread = React.useCallback(async () => {
    if (!token || !companyId) {
      return
    }
    try {
      const { unread_count } = await api.unreadNotificationsCount(
        token,
        companyId
      )
      setUnread(unread_count)
    } catch {
      // The API may be briefly unavailable; keep the previous count.
    }
  }, [token, companyId])

  React.useEffect(() => {
    void refreshUnread()
    const timer = window.setInterval(
      () => void refreshUnread(),
      POLL_INTERVAL_MS
    )
    return () => window.clearInterval(timer)
  }, [refreshUnread])

  const loadItems = React.useCallback(async () => {
    if (!token || !companyId) {
      setItems([])
      return
    }
    setLoading(true)
    try {
      const response = await api.listNotifications(token, {
        companyId,
        limit: PAGE_SIZE,
      })
      setItems(response.items)
      setHasMore(response.items.length >= PAGE_SIZE)
      setUnread(response.unread_count)
    } catch {
      // ...
    } finally {
      setLoading(false)
    }
  }, [token, companyId])

  const loadMoreItems = React.useCallback(async () => {
    if (!token || !companyId || loadingMoreRef.current || !hasMore) {
return
    }
    loadingMoreRef.current = true
    setLoadingMore(true)
    const offset = items.length
    try {
      const response = await api.listNotifications(token, {
        companyId,
        limit: PAGE_SIZE,
        offset,
      })
      setHasMore(response.items.length >= PAGE_SIZE)
      setItems((previous) => {
        const knownIds = new Set(previous.map((item) => item.id))
        return [
          ...previous,
          ...response.items.filter((item) => !knownIds.has(item.id)),
        ]
      })
      setUnread(response.unread_count)
    } catch {
      // ...
    } finally {
      loadingMoreRef.current = false
      setLoadingMore(false)
    }
  }, [token, companyId, hasMore, items.length])

  const sentinelRef = useInfiniteScroll({
    hasMore,
    loading: loadingMore,
    onLoadMore: () => void loadMoreItems(),
    rootMargin: "240px",
  })

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen)
      if (nextOpen) {
        void loadItems()
      } else {
        void refreshUnread()
      }
    },
    [loadItems, refreshUnread]
  )

  const markAllRead = React.useCallback(async () => {
    if (!token || !companyId) {
      return
    }
    setMarkingAll(true)
    try {
      await api.markAllNotificationsRead(token, companyId)
      setItems((previous) =>
        previous.map((item) => ({ ...item, is_read: true }))
      )
      setUnread(0)
    } catch {
      // Keep current state; the request can be retried.
    } finally {
      setMarkingAll(false)
    }
  }, [token, companyId])

  return (
    <DropdownMenuGroup>
      <DropdownMenu open={open} onOpenChange={handleOpenChange}>
        <DropdownMenuTrigger
          render={
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="relative"
              aria-label={
                unread > 0 ? `${unread} unread notifications` : "Notifications"
              }
            >
              {unread > 0 ? (
                <BellRing className="size-4" />
              ) : (
                <Bell className="size-4" />
              )}
              {unread > 0 ? (
                <Badge className="pointer-events-none absolute -end-0.5 -top-0.5 size-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] leading-none font-semibold">
                  {unread > 99 ? "99+" : unread}
                </Badge>
              ) : null}
            </Button>
          }
        />

        <DropdownMenuContent
          align="end"
          sideOffset={6}
          className="w-80 overflow-visible"
        >
          <DropdownMenuLabel className="flex items-center justify-between gap-2 pe-2">
            <span className="text-xs font-medium text-foreground">
              Notifications
            </span>
            {unread > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="xs"
                disabled={markingAll}
                onClick={markAllRead}
              >
                <Check />
                Mark all read
              </Button>
            ) : null}
          </DropdownMenuLabel>

          <DropdownMenuSeparator />

          <DropdownMenuGroup>
            <ScrollArea className="h-80 w-full">
              {loading == true && items.length === 0 ? (
                <div className="flex flex-col gap-2 p-3">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : loading == false && items.length === 0 ? (
                <div className="flex flex-col items-center gap-1 px-4 py-10 text-center">
                  <Bell className="size-5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    No notifications yet.
                  </span>
                </div>
              ) : (
                <React.Fragment>
                  {items.map((item) => (
                    <NotificationRow
                      key={item.id}
                      item={item}
                      companyId={companyId}
                      token={token}
                      onMarkedRead={() => {
                        setUnread((previous) =>
                          previous > 0 && !item.is_read
                            ? previous - 1
                            : previous
                        )
                      }}
                    />
                  ))}
                  {loadingMore ? (
                    <div className="flex justify-center py-3 text-muted-foreground">
                      <LoaderCircle className="size-4 animate-spin" />
                    </div>
                  ) : null}
                  <div
                    ref={sentinelRef}
                    aria-hidden="true"
                    className="h-px w-full"
                  />
                </React.Fragment>
              )}
            </ScrollArea>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </DropdownMenuGroup>
  )
}

function NotificationRow({
  item,
  companyId,
  token,
  onMarkedRead,
}: {
  item: NotificationItem
  companyId: string | undefined
  token: string | null
  onMarkedRead: () => void
}) {
  const href = item.conversation_id
    ? `/companies/${companyId}/whatsapp/conversations?conversation=${item.conversation_id}`
    : `/companies/${companyId}/whatsapp/conversations`

  const handleClick = React.useCallback(() => {
    if (!item.is_read && token) {
      void api
        .markNotificationRead(item.id, token, companyId)
        .then(onMarkedRead)
        .catch(() => {
          // Navigation still proceeds; the read state syncs on the next poll.
        })
    }
  }, [item, token, companyId, onMarkedRead])

  return (
    <DropdownMenuItem
      render={<Link href={href} onClick={handleClick} />}
      className={cn(
        "items-start gap-2.5 px-3 py-2.5",
        !item.is_read && "bg-accent/50"
      )}
    >
      <span
        className={cn(
          "mt-1 size-2 shrink-0 rounded-full",
          item.is_read ? "bg-transparent ring-1 ring-border" : "bg-primary"
        )}
        aria-hidden="true"
      />
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="flex items-center justify-between gap-2">
          <span className="truncate text-xs font-medium">{item.title}</span>
          <span className="shrink-0 text-[10px] text-muted-foreground">
            {formatRelative(item.created_at)}
          </span>
        </span>
        {item.body ? (
          <span className="line-clamp-2 text-[11px] text-muted-foreground">
            {item.body}
          </span>
        ) : null}
      </span>
    </DropdownMenuItem>
  )
}

export { NotificationBell }
