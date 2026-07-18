import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { ShieldCheck } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import type { MfaChallenge } from "@/lib/types/api"
import { requestMfaResend } from "./authApi"

const otpFormSchema = z.object({
  code: z.string().length(6, "Enter the 6-digit code"),
})

type OtpFormValues = z.infer<typeof otpFormSchema>

interface MfaChallengePageProps {
  challenge: MfaChallenge
  onVerified: (challengeId: string, code: string) => Promise<void>
  onBackToCredentials: () => void
}

function MfaChallengePage({ challenge, onVerified, onBackToCredentials }: MfaChallengePageProps) {
  const [activeChallenge, setActiveChallenge] = React.useState(challenge)
  const [serverError, setServerError] = React.useState<string | null>(null)
  const [isResending, setIsResending] = React.useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<OtpFormValues>({ resolver: zodResolver(otpFormSchema) })

  async function onSubmit(values: OtpFormValues) {
    setServerError(null)
    try {
      await onVerified(activeChallenge.challenge_id, values.code)
    } catch (error) {
      setServerError(extractApiErrorMessage(error, "That code didn't work — check it and try again."))
    }
  }

  async function initiateCodeResend() {
    setIsResending(true)
    setServerError(null)
    try {
      const next = (await requestMfaResend(activeChallenge.challenge_id)) as MfaChallenge
      setActiveChallenge(next)
    } catch (error) {
      setServerError(extractApiErrorMessage(error, "Couldn't send a new code."))
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-zinc-800 dark:text-zinc-100">
        <ShieldCheck className="size-5 text-accent-600 dark:text-accent-300" />
        <h2 className="text-base font-semibold">Verify it's you</h2>
      </div>

      {activeChallenge.simulated_code ? (
        <div className="rounded-md border border-caution-500/40 bg-caution-500/10 px-3 py-2 text-xs text-caution-600 dark:text-caution-500">
          Development mode — real delivery isn't configured yet. Your code is{" "}
          <span className="font-mono font-semibold">{activeChallenge.simulated_code}</span>.
        </div>
      ) : (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Enter the code sent to your registered device. It expires in {activeChallenge.expires_in_minutes} minutes.
        </p>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="otp-code">Verification code</Label>
          <Input
            id="otp-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="000000"
            className="text-center font-mono text-lg tracking-[0.5em]"
            {...register("code")}
          />
          {errors.code ? <p className="text-xs text-critical-500">{errors.code.message}</p> : null}
        </div>

        {serverError ? <p className="text-xs text-critical-500">{serverError}</p> : null}

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Verifying..." : "Verify and continue"}
        </Button>
      </form>

      <div className="flex items-center justify-between text-xs">
        <button type="button" onClick={onBackToCredentials} className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400">
          Use a different account
        </button>
        <button
          type="button"
          onClick={initiateCodeResend}
          disabled={isResending}
          className="font-medium text-accent-600 hover:text-accent-700 disabled:opacity-50 dark:text-accent-300"
        >
          {isResending ? "Sending..." : "Resend code"}
        </button>
      </div>
    </div>
  )
}

export { MfaChallengePage }
