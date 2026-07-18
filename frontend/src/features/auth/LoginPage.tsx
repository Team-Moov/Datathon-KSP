import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { ShieldHalf } from "lucide-react"
import { useForm } from "react-hook-form"
import { useNavigate } from "react-router-dom"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { isMfaChallenge, type MfaChallenge, type TokenPair } from "@/lib/types/api"
import { submitLoginCredentials, submitMfaCode } from "./authApi"
import { useAuth } from "./AuthProvider"
import { MfaChallengePage } from "./MfaChallengePage"

const credentialsFormSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
})

type CredentialsFormValues = z.infer<typeof credentialsFormSchema>

function LoginPage() {
  const navigate = useNavigate()
  const { applyTokenPair } = useAuth()
  const [pendingChallenge, setPendingChallenge] = React.useState<MfaChallenge | null>(null)
  const [serverError, setServerError] = React.useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CredentialsFormValues>({ resolver: zodResolver(credentialsFormSchema) })

  async function completeSession(tokens: TokenPair) {
    await applyTokenPair(tokens)
    navigate("/", { replace: true })
  }

  async function onSubmitCredentials(values: CredentialsFormValues) {
    setServerError(null)
    try {
      const result = await submitLoginCredentials(values.email, values.password)
      if (isMfaChallenge(result)) {
        setPendingChallenge(result)
        return
      }
      await completeSession(result)
    } catch (error) {
      setServerError(extractApiErrorMessage(error, "Incorrect email or password."))
    }
  }

  async function onMfaVerified(challengeId: string, code: string) {
    const tokens = await submitMfaCode(challengeId, code)
    await completeSession(tokens)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-100 px-4 dark:bg-zinc-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="glass-surface flex size-11 items-center justify-center rounded-lg">
            <ShieldHalf className="size-5 text-accent-600 dark:text-accent-300" />
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Karnataka Crime Intelligence</p>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">Restricted access — authorized personnel only</p>
          </div>
        </div>

        <div className="glass-surface rounded-lg p-6">
          {pendingChallenge ? (
            <MfaChallengePage
              challenge={pendingChallenge}
              onVerified={onMfaVerified}
              onBackToCredentials={() => setPendingChallenge(null)}
            />
          ) : (
            <form onSubmit={handleSubmit(onSubmitCredentials)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="login-email">Email</Label>
                <Input id="login-email" type="email" autoComplete="username" {...register("email")} />
                {errors.email ? <p className="text-xs text-critical-500">{errors.email.message}</p> : null}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="login-password">Password</Label>
                <Input id="login-password" type="password" autoComplete="current-password" {...register("password")} />
                {errors.password ? <p className="text-xs text-critical-500">{errors.password.message}</p> : null}
              </div>

              {serverError ? <p className="text-xs text-critical-500">{serverError}</p> : null}

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Signing in..." : "Sign in"}
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

export { LoginPage }
