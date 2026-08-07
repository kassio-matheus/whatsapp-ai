"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowRight, CheckCircle2, LoaderCircle, MailCheck } from "lucide-react"

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

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_MIN_LENGTH = 12

function getPasswordStrength(password: string) {
  if (!password) {
    return 0
  }
  let score = 0
  if (password.length >= PASSWORD_MIN_LENGTH) {
    score += 1
  }
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) {
    score += 1
  }
  if (/\d/.test(password)) {
    score += 1
  }
  if (/[^a-zA-Z0-9]/.test(password)) {
    score += 1
  }
  return score
}

const STRENGTH_LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"]

function RegisterForm({ onSuccess }: { onSuccess: (email: string) => void }) {
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [confirmPassword, setConfirmPassword] = React.useState("")
  const [emailError, setEmailError] = React.useState<string | null>(null)
  const [passwordError, setPasswordError] = React.useState<string | null>(null)
  const [confirmError, setConfirmError] = React.useState<string | null>(null)
  const [formError, setFormError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  const strength = getPasswordStrength(password)

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    setEmailError(null)
    setPasswordError(null)
    setConfirmError(null)
    setFormError(null)

    let hasError = false
    if (!EMAIL_PATTERN.test(email)) {
      setEmailError("Enter a valid email address.")
      hasError = true
    }
    if (password.length < PASSWORD_MIN_LENGTH) {
      setPasswordError(
        `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`
      )
      hasError = true
    }
    if (confirmPassword !== password) {
      setConfirmError("Passwords do not match.")
      hasError = true
    }
    if (hasError) {
      return
    }

    setIsSubmitting(true)
    api
      .register(email, password)
      .then(() => onSuccess(email))
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
    <Card size="sm">
      <CardHeader>
        <CardTitle>Create an account</CardTitle>
        <CardDescription>
          Register with your email to get started. Your password must be at
          least {PASSWORD_MIN_LENGTH} characters.
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
              <p className="text-xs text-destructive" role="alert">
                {emailError}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <PasswordInput
              id="password"
              autoComplete="new-password"
              placeholder="At least 12 characters"
              value={password}
              aria-invalid={passwordError ? true : undefined}
              onChange={(event) => setPassword(event.target.value)}
            />
            {password ? (
              <div className="flex flex-col gap-1">
                <div className="flex gap-1">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <span
                      key={index}
                      className={`h-1 flex-1 rounded-none ${
                        index < strength ? "bg-primary" : "bg-border"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  Strength: {STRENGTH_LABELS[strength]}
                </p>
              </div>
            ) : null}
            {passwordError ? (
              <p className="text-xs text-destructive" role="alert">
                {passwordError}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirm-password">Confirm password</Label>
            <PasswordInput
              id="confirm-password"
              autoComplete="new-password"
              placeholder="Repeat your password"
              value={confirmPassword}
              aria-invalid={confirmError ? true : undefined}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
            {confirmError ? (
              <p className="text-xs text-destructive" role="alert">
                {confirmError}
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
          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <ArrowRight />
            )}
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
          <p className="text-xs text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  )
}

function RegisterSuccess({ email }: { email: string }) {
  const [isResending, setIsResending] = React.useState(false)
  const [resendState, setResendState] = React.useState<
    "idle" | "success" | "error"
  >("idle")

  function handleResend() {
    setIsResending(true)
    api
      .resendVerificationEmail(email)
      .then(() => setResendState("success"))
      .catch(() => setResendState("error"))
      .finally(() => setIsResending(false))
  }

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-primary" />
          Register successful!
        </CardTitle>
        <CardDescription>Thanks for register.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-3 text-center"></CardContent>
      <CardFooter className="flex-col gap-3">
        <Link
          href="/login"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Sign in now
        </Link>
      </CardFooter>
    </Card>
  )
}

export default function RegisterPage() {
  const [registeredEmail, setRegisteredEmail] = React.useState<string | null>(
    null
  )

  return (
    <AuthLayout>
      {registeredEmail ? (
        <RegisterSuccess email={registeredEmail} />
      ) : (
        <RegisterForm onSuccess={setRegisteredEmail} />
      )}
    </AuthLayout>
  )
}
