import { useEffect, useState } from "react"
import { X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { getPrompt, type PromptResult } from "@/lib/api"
import { categoryLabel } from "@/lib/taxonomy"

type PromptModalProps = {
  result: PromptResult | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function PromptModal({ result, open, onOpenChange }: PromptModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fullPrompt, setFullPrompt] = useState("")
  const [technique, setTechnique] = useState("")
  const [source, setSource] = useState("")
  const [promptId, setPromptId] = useState("")

  useEffect(() => {
    if (!open || !result) {
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setError(null)
    setFullPrompt("")
    setTechnique(result.technique || "")
    setSource(result.source || "")
    setPromptId(result.id || "")

    getPrompt(result.id, controller.signal)
      .then((data) => {
        setFullPrompt(data.full_prompt || "")
        setTechnique(data.technique || result.technique || "")
        setSource(data.source || result.source || "")
        setPromptId(data.id || result.id || "")
      })
      .catch((err: Error) => {
        if (err.name === "AbortError") {
          return
        }
        setError(err.message || "Failed to load prompt")
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })

    return () => controller.abort()
  }, [open, result])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="flex max-h-[calc(100vh-2rem)] w-[min(100%,980px)] max-w-[980px] flex-col gap-0 rounded-none border-border bg-popover p-0 sm:max-w-[980px] [&+[data-slot=dialog-overlay]]:bg-black/80"
      >
        <DialogHeader className="border-b border-border px-6 py-5 text-left">
          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-2">
              <p className="label-mono text-primary">Full prompt</p>
              <div className="flex flex-wrap items-center gap-3">
                <DialogTitle className="font-display text-2xl text-foreground">
                  Prompt detail
                </DialogTitle>
                {technique ? (
                  <Badge
                    variant="outline"
                    title={technique}
                    className="rounded-none border-primary/30 bg-primary/10 font-mono text-[11px] tracking-[0.12em] text-primary uppercase"
                  >
                    {categoryLabel(technique)}
                  </Badge>
                ) : null}
              </div>
              <DialogDescription className="font-mono text-xs text-muted-foreground">
                {promptId}
              </DialogDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="size-11 min-h-11 min-w-11 rounded-none"
              aria-label="Close full prompt"
              onClick={() => onOpenChange(false)}
            >
              <X className="size-4" />
            </Button>
          </div>
        </DialogHeader>

        <ScrollArea className="min-h-0 flex-1">
          <div className="px-6 py-6">
            {loading ? (
              <Skeleton className="h-48 w-full rounded-none bg-muted" />
            ) : null}
            {error ? (
              <p className="panel px-4 py-4 text-sm text-destructive">{error}</p>
            ) : null}
            {!loading && !error ? (
              <pre className="font-mono text-[13px] leading-6 whitespace-pre-wrap text-foreground/90">
                {fullPrompt}
              </pre>
            ) : null}
          </div>
        </ScrollArea>

        <footer className="border-t border-border px-6 py-4 text-sm text-muted-foreground">
          Source: {source || "Unknown source"}
        </footer>
      </DialogContent>
    </Dialog>
  )
}
