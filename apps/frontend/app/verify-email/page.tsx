"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { CheckCircle2, LoaderCircle, ShieldAlert } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"

import { AuthLayout } from "@/components/auth/auth-layout"
import { api, ApiClientError } from "@/lib/api"
import { saveToken } from "@/lib/session"

type VerifyState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success" }

function getTokenFromHash(): string | null {
  const raw = window.location.hash
  const params = new URLSearchParams(raw.replace(/^#/, ""))
  return params.get("token")
}

export default function VerifyEmailPage() {
  const router = useRouter()
  const [state, setState] = React.useState<VerifyState>({ status: "loading" })

  React.useEffect(() => {
    const token = getTokenFromHash()

    if (!token) {
      const timer = window.setTimeout(() => {
        setState({
          status: "error",
          message: "No verification token found in the link.",
        })
      }, 0)
      return () => window.clearTimeout(timer)
    }

    let cancelled = false

    api
      .verifyEmail(token)
      .then(({ access_token }) => {
        if (cancelled) {
          return
        }
        saveToken(access_token)
        setState({ status: "success" })
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return
        }
        if (error instanceof ApiClientError) {
          setState({ status: "error", message: error.message })
        } else {
          setState({
            status: "error",
            message: "Unable to connect to the server. Please try again.",
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <AuthLayout>
      <Card size="sm">
        <CardHeader>
          {state.status === "success" ? (
            <>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="size-4 text-primary" />
                Email verified
              </CardTitle>
              <CardDescription>
                Your email has been verified. You are now signed in.
              </CardDescription>
            </>
          ) : (
            <>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-destructive" />
                Email verification
              </CardTitle>
              <CardDescription>
                {state.status === "loading"
                  ? "Verifying your email address…"
                  : "We could not verify your email."}
              </CardDescription>
            </>
          )}
        </CardHeader>

        <CardContent>
          {state.status === "loading" ? (
            <div className="flex items-center justify-center py-4">
              <LoaderCircle className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : null}
          {state.status === "error" ? (
            <p
              className="rounded-none border border-destructive/30 bg-destructive/10 px-2.5 py-2 text-xs text-destructive"
              role="alert"
            >
              {state.message}
            </p>
          ) : null}
        </CardContent>

        <CardFooter>
          {state.status === "success" ? (
            <Button className="w-full" size="lg" onClick={() => router.push("/")}>
              Continue
            </Button>
          ) : (
            <Link href="/login" className="w-full">
              <Button variant="outline" className="w-full" size="lg">
                Back to sign in
              </Button>
            </Link>
          )}
        </CardFooter>
      </Card>
    </AuthLayout>
  )
}
