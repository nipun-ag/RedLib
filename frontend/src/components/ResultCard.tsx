import type { PromptResult } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { categoryLabel } from "@/lib/taxonomy"

type ResultCardProps = {
  result: PromptResult
  onOpen: (result: PromptResult) => void
}

export function ResultCard({ result, onOpen }: ResultCardProps) {
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
