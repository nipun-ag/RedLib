import type { ConfidenceLevel, PromptResult } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { categoryLabel } from "@/lib/taxonomy"
import { cn } from "@/lib/utils"

type ResultCardProps = {
  result: PromptResult
  showConfidence?: boolean
  onOpen: (result: PromptResult) => void
}

function confidenceClass(level: ConfidenceLevel | undefined): string {
  switch (level) {
    case "HIGH":
      return "bg-primary/20 text-primary"
    case "MED":
      return "bg-secondary text-muted-foreground"
    case "LOW":
      return "bg-muted text-muted-foreground/80"
    default:
      return "bg-muted text-muted-foreground"
  }
}

export function ResultCard({
  result,
  showConfidence = false,
  onOpen,
}: ResultCardProps) {
  return (
    <article className="panel px-5 py-5 transition-[transform,border-color] duration-300 hover:-translate-y-0.5 hover:border-primary/30">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Badge
          variant="outline"
          title={result.technique || undefined}
          className="rounded-none border-primary/30 bg-primary/10 font-mono text-[11px] tracking-[0.12em] text-primary uppercase"
        >
          {result.technique ? categoryLabel(result.technique) : "Unknown"}
        </Badge>
        {showConfidence && result.confidence ? (
          <span
            className={cn(
              "inline-flex items-center gap-2 px-2 py-1 font-mono text-[11px] tracking-[0.1em] uppercase",
              confidenceClass(result.confidence),
            )}
          >
            <span
              className={cn(
                "size-1.5",
                result.confidence === "HIGH" && "bg-primary",
                result.confidence === "MED" && "bg-platinum",
                result.confidence === "LOW" && "bg-muted-foreground",
              )}
              aria-hidden="true"
            />
            {result.confidence}
          </span>
        ) : null}
        <span className="ml-auto text-sm text-muted-foreground">
          {result.source || "Unknown source"}
        </span>
      </div>

      <p className="mb-4 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
        {result.prompt_excerpt}
      </p>

      <Button
        type="button"
        variant="ghost"
        className="label-mono h-11 min-h-11 px-3 text-primary hover:bg-secondary/50 hover:text-foreground"
        onClick={() => onOpen(result)}
      >
        View Full Prompt →
      </Button>
    </article>
  )
}
