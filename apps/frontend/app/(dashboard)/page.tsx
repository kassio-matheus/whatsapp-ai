"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { useApp } from "@/components/app-provider"

export default function HomePage() {
  const { isLoading, user, companies, currentCompanyId } = useApp()
  const router = useRouter()
  const redirected = React.useRef(false)

  React.useEffect(() => {
    if (redirected.current) {
      return
    }
    if (isLoading) {
      return
    }
    redirected.current = true

    if (!user) {
      router.replace("/login")
      return
    }

    if (user.is_super_admin) {
      if (companies.length === 0) {
        router.replace("/companies")
      } else {
        router.replace(`/companies/${currentCompanyId ?? companies[0]?.id}`)
      }
      return
    }

    if (user.company_id) {
      router.replace(`/companies/${user.company_id}`)
    } else {
      router.replace("/login")
    }
  }, [isLoading, user, companies, currentCompanyId, router])

  return null
}
