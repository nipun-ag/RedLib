import { ArrowRight } from "lucide-react"
import { useEffect, useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"

import { AnimatedNumber } from "@/components/AnimatedNumber"
import { LiquidAtmosphere } from "@/components/LiquidAtmosphere"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Separator } from "@/components/ui/separator"
import { getStats } from "@/lib/api"
import {
  acknowledgeGate,
  CORPUS_FALLBACK_COUNT,
  isGateAcknowledged,
} from "@/lib/taxonomy"

const CONDITIONS = [
  "Use this corpus for defensive analysis, evaluation, or safety research only.",
  "Do not use these prompts to facilitate illegal acts or generate harmful outcomes.",
  "Do not reproduce or redistribute full prompts outside approved research contexts.",
] as const

export function GatePage() {
  const navigate = useNavigate()
  const [agreed, setAgreed] = useState(false)
  const [totalPrompts, setTotalPrompts] = useState(CORPUS_FALLBACK_COUNT)

  useEffect(() => {
    if (isGateAcknowledged()) {
      navigate("/workspace", { replace: true })
    }
  }, [navigate])

  useEffect(() => {
    const controller = new AbortController()

    getStats(controller.signal)
      .then((data) => {
        if (typeof data.total_prompts === "number") {
          setTotalPrompts(data.total_prompts)
        }
      })
      .catch(() => {
        setTotalPrompts(CORPUS_FALLBACK_COUNT)
      })

    return () => controller.abort()
  }, [])

  function handleEnter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!agreed) {
      return
    }

    acknowledgeGate()
    navigate("/workspace")
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
      <LiquidAtmosphere intensity="gate" />

      <section className="panel relative z-10 w-full max-w-xl px-7 py-8 sm:px-10 sm:py-10">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />

        <p className="label-mono text-primary">Responsible access gate</p>

        <h1 className="font-display mt-5 text-4xl text-foreground sm:text-5xl">
          RedLib
        </h1>

        <p className="mt-3 max-w-prose text-base text-muted-foreground">
          Secure access to adversarial intelligence for AI safety research.
        </p>

        <div className="mt-8 flex items-end gap-4 border border-border bg-secondary/40 px-4 py-4">
          <div>
            <p className="label-mono text-muted-foreground">Curated corpus</p>
            <AnimatedNumber
              value={totalPrompts}
              className="mt-2 block font-mono text-4xl font-medium tracking-tight text-foreground tabular-nums sm:text-5xl"
            />
          </div>
          <p className="mb-1 text-sm text-muted-foreground">
            classified adversarial records
          </p>
        </div>

        <div className="mt-8">
          <p className="label-mono text-primary">Research conditions</p>
          <ol className="mt-4 grid gap-4">
            {CONDITIONS.map((condition, index) => (
              <li key={condition} className="grid grid-cols-[2.5rem_1fr] gap-3">
                <span className="font-mono text-sm text-primary/80">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {condition}
                </p>
              </li>
            ))}
          </ol>
        </div>

        <Separator className="my-8 bg-border" />

        <form className="grid gap-6" onSubmit={handleEnter}>
          <label className="flex cursor-pointer items-start gap-3">
            <Checkbox
              checked={agreed}
              onCheckedChange={(value) => setAgreed(value === true)}
              className="mt-0.5 size-5 rounded-none border-border data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
              aria-describedby="agreement-copy"
            />
            <span id="agreement-copy" className="text-sm text-muted-foreground">
              I understand these conditions and I am entering for legitimate
              research use.
            </span>
          </label>

          <Button
            type="submit"
            size="lg"
            disabled={!agreed}
            className="h-12 w-full rounded-none bg-primary text-primary-foreground hover:bg-primary/90"
          >
            Enter Research Workspace
            <ArrowRight className="size-4" />
          </Button>
        </form>
      </section>
    </main>
  )
}
