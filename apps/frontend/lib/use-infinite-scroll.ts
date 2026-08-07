"use client"

import * as React from "react"

//
// IntersectionObserver-based sentinel that triggers `onLoadMore` when a
// placeholder element at the edge of a scrollable list becomes visible.
//
// Works for three layouts with zero configuration:
//   - "load more at the bottom": render the sentinel as the last child.
//   - "load older" (chat-style): render the sentinel as the FIRST child, so it
//     only becomes visible when the user scrolls the list all the way up.
//   - Pages that scroll on the window: the sentinel at the end of the document
//     is observed against the viewport automatically.
//
// The observer re-arms in the render lifecycle of the hook, so as soon as a
// page finishes loading and `hasMore`/`loading` stop changing, it keeps firing
// until the viewport is filled (or the cursor runs out).
//

export function useInfiniteScroll<T extends HTMLElement = HTMLDivElement>({
  hasMore,
  loading,
  onLoadMore,
  rootMargin = "160px",
  disabled = false,
  threshold = 0,
}: {
  hasMore: boolean
  loading: boolean
  onLoadMore: () => void
  /** Grow the observed area by this amount, in CSS lengths. Larger = earlier trigger. */
  rootMargin?: string
  /** Disables observing (e.g. while filters are being applied externally). */
  disabled?: boolean
  threshold?: number | number[]
}) {
  const sentinelRef = React.useRef<T | null>(null)

  const hasMoreRef = React.useRef(hasMore)
  const loadingRef = React.useRef(loading)
  const onLoadMoreRef = React.useRef(onLoadMore)
  const disabledRef = React.useRef(disabled)

  React.useEffect(() => {
    hasMoreRef.current = hasMore
  }, [hasMore])
  React.useEffect(() => {
    loadingRef.current = loading
  }, [loading])
  React.useEffect(() => {
    onLoadMoreRef.current = onLoadMore
  }, [onLoadMore])
  React.useEffect(() => {
    disabledRef.current = disabled
  }, [disabled])

  React.useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel || disabled) {
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries.some((entry) => entry.isIntersecting) &&
          hasMoreRef.current &&
          !loadingRef.current &&
          !disabledRef.current
        ) {
          onLoadMoreRef.current()
        }
      },
      { rootMargin, threshold }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [rootMargin, threshold, disabled, hasMore, loading])

  return sentinelRef
}

export type InfiniteScrollSentinelProps = {
  ref: React.RefCallback<HTMLElement> | React.RefObject<HTMLElement | null>
  className?: string
}