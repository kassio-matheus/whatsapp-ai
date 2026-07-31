"use client"

import * as React from "react"

import { api, ApiClientError, type Company, type UserProfile } from "@/lib/api"
import { clearToken, getToken } from "@/lib/session"

const CURRENT_COMPANY_KEY = "app.current_company_id"

type AppContextValue = {
  token: string | null
  user: UserProfile | null
  companies: Company[]
  currentCompanyId: string | null
  isLoading: boolean
  setUser: (user: UserProfile | null) => void
  refreshCompanies: () => Promise<void>
  switchCompany: (companyId: string) => void
  signOut: () => void
}

const AppContext = React.createContext<AppContextValue | null>(null)

function AppProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = React.useState<string | null>(null)
  const [user, setUser] = React.useState<UserProfile | null>(null)
  const [companies, setCompanies] = React.useState<Company[]>([])
  const [currentCompanyId, setCurrentCompanyId] = React.useState<string | null>(
    null,
  )
  const [isLoading, setIsLoading] = React.useState(true)

  const refreshCompanies = React.useCallback(async () => {
    const currentToken = getToken()
    if (!currentToken) {
      return
    }
    const fetched = await api.listCompanies(currentToken)
    setCompanies(fetched)
    setCurrentCompanyId((previous) => {
      const stored = localStorage.getItem(CURRENT_COMPANY_KEY)
      const valid =
        stored && fetched.some((company) => company.id === stored)
          ? stored
          : null
      const next = previous && fetched.some((c) => c.id === previous) ? previous : valid
      return next ?? fetched[0]?.id ?? null
    })
  }, [])

  const switchCompany = React.useCallback((companyId: string) => {
    localStorage.setItem(CURRENT_COMPANY_KEY, companyId)
    setCurrentCompanyId(companyId)
  }, [])

  const signOut = React.useCallback(() => {
    clearToken()
    setToken(null)
    setUser(null)
    setCompanies([])
    setCurrentCompanyId(null)
    localStorage.removeItem(CURRENT_COMPANY_KEY)
  }, [])

  React.useEffect(() => {
    const storedToken = getToken()
    if (!storedToken) {
      setIsLoading(false)
      return
    }

    setToken(storedToken)

    async function bootstrap() {
      const currentToken = getToken()
      if (!currentToken) {
        return
      }
      try {
        const profile = await api.getCurrentUser(currentToken)
        setUser(profile)
        if (profile.is_super_admin) {
          await refreshCompanies()
        } else {
          setCurrentCompanyId(profile.company_id)
          localStorage.removeItem(CURRENT_COMPANY_KEY)
        }
      } catch (error) {
        if (error instanceof ApiClientError && error.status === 401) {
          signOut()
        }
      } finally {
        setIsLoading(false)
      }
    }

    void bootstrap()
  }, [refreshCompanies, signOut])

  const value = React.useMemo<AppContextValue>(
    () => ({
      token,
      user,
      companies,
      currentCompanyId,
      isLoading,
      setUser,
      refreshCompanies,
      switchCompany,
      signOut,
    }),
    [token, user, companies, currentCompanyId, isLoading, refreshCompanies, switchCompany, signOut],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

function useApp() {
  const context = React.useContext(AppContext)
  if (!context) {
    throw new Error("useApp must be used within an AppProvider")
  }
  return context
}

export { AppProvider, useApp }
