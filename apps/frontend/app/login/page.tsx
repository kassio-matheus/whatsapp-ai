"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowRight, LoaderCircle } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import { AuthLayout } from "@/components/auth/auth-layout"
import { PasswordInput } from "@/components/auth/password-input"
import { api, ApiClientError } from "@/lib/api"
import { saveToken } from "@/lib/session"

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function LoginPage() {
  const router = useRouter()

  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [emailError, setEmailError] = React.useState<string | null>(null)
  const [passwordError, setPasswordError] = React.useState<string | null>(null)
  const [formError, setFormError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    setEmailError(null)
    setPasswordError(null)
    setFormError(null)

    let hasError = false
    if (!EMAIL_PATTERN.test(email)) {
      setEmailError("Enter a valid email address.")
      hasError = true
    }
    if (!password) {
      setPasswordError("Password is required.")
      hasError = true
    }
    if (hasError) {
      return
    }

    setIsSubmitting(true)
    api
      .login(email, password)
      .then(({ access_token }) => {
        saveToken(access_token)
        router.push("/")
        router.refresh()
      })
      .catch((error: unknown) => {
        if (error instanceof ApiClientError) {
          setFormError(error.message)
        } else {
          setFormError("Unable to connect to the server. Please try again.")
        }
      })
      .finally(() => setIsSubmitting(false))
  }

  return (
    <AuthLayout>
      <Card size="sm">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>
            Enter your email and password to access your account.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} noValidate>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                aria-invalid={emailError ? true : undefined}
                onChange={(event) => setEmail(event.target.value)}
              />
              {emailError ? (
                <p
                  className="animate-slide-down text-xs text-destructive"
                  role="alert"
                >
                  {emailError}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <PasswordInput
                id="password"
                autoComplete="current-password"
                placeholder="••••••••••••"
                value={password}
                aria-invalid={passwordError ? true : undefined}
                onChange={(event) => setPassword(event.target.value)}
              />
              {passwordError ? (
                <p className="text-xs text-destructive" role="alert">
                  {passwordError}
                </p>
              ) : null}
            </div>

            {formError ? (
              <p
                className="rounded-none border border-destructive/30 bg-destructive/10 px-2.5 py-2 text-xs text-destructive"
                role="alert"
              >
                {formError}
              </p>
            ) : null}
          </CardContent>

          <CardFooter className="flex-col gap-3">
            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <ArrowRight />
              )}
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Don&apos;t have an account?{" "}
              <Link
                href="/register"
                className="font-medium text-foreground underline-offset-4 hover:underline"
              >
                Create one
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </AuthLayout>
  )
}
