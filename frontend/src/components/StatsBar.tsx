import { ArrowUpRight, Library } from "lucide-react"

import { AnimatedNumber } from "@/components/AnimatedNumber"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Skeleton } from "@/components/ui/skeleton"
import type { StatsResponse } from "@/lib/api"
import { CORPUS_SOURCES, formatNumber } from "@/lib/taxonomy"

type StatsBarProps = {
  stats: StatsResponse | null
  loading: boolean
}

export function StatsBar({ stats, loading }: StatsBarProps) {
  return (
    <section
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      aria-label="Corpus statistics"
    >
      <article className="panel px-5 py-5 transition-transform duration-300 hover:-translate-y-0.5">
        <p className="label-mono text-muted-foreground">Total prompts</p>
        {loading ? (
          <Skeleton className="mt-3 h-9 w-28 rounded-none bg-muted" />
        ) : (
          <AnimatedNumber
            value={stats?.total_prompts}
            className="font-display mt-2 block text-3xl tracking-tight text-foreground tabular-nums"
          />
        )}
      </article>

      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="panel group w-full px-5 py-5 text-left transition-[transform,border-color] duration-300 hover:-translate-y-0.5 hover:border-primary/35 focus-visible:border-primary/50"
            aria-label="View corpus sources"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono text-muted-foreground">Sources</p>
              <Library className="size-4 text-primary/70 transition-colors group-hover:text-primary" />
            </div>
            {loading ? (
              <Skeleton className="mt-3 h-9 w-16 rounded-none bg-muted" />
            ) : (
              <p className="font-display mt-2 text-3xl tracking-tight text-foreground tabular-nums">
                {formatNumber(stats?.total_sources)}
              </p>
            )}
            <p className="mt-3 text-xs text-muted-foreground transition-colors group-hover:text-primary/90">
              Open dataset provenance →
            </p>
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          side="bottom"
          sideOffset={8}
          className="w-[min(100vw-2rem,22rem)] rounded-none border-border bg-popover p-0 shadow-none"
        >
          <div className="border-b border-border px-4 py-3">
            <p className="label-mono text-primary">Corpus sources</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Public datasets snapshotted into the RedLib corpus.
            </p>
          </div>
          <ul className="grid max-h-[min(60vh,22rem)] gap-px overflow-y-auto bg-border/40 p-px">
            {CORPUS_SOURCES.map((source) => (
              <li key={source.id}>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group/source flex items-start justify-between gap-3 bg-popover px-4 py-3 transition-colors hover:bg-secondary/70 focus-visible:bg-secondary/70 focus-visible:outline-none"
                >
                  <span className="min-w-0">
                    <span className="block text-sm text-foreground group-hover/source:text-primary">
                      {source.label}
                    </span>
                    <span className="mt-1 block truncate font-mono text-[11px] tracking-wide text-muted-foreground">
                      {source.datasetId}
                    </span>
                    <span className="mt-1 block font-mono text-[10px] tracking-[0.14em] text-muted-foreground/80 uppercase">
                      {source.host}
                    </span>
                  </span>
                  <ArrowUpRight
                    className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-colors group-hover/source:text-primary"
                    aria-hidden="true"
                  />
                </a>
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>

      <article className="panel px-5 py-5 transition-transform duration-300 hover:-translate-y-0.5 sm:col-span-2 lg:col-span-1">
        <p className="label-mono text-muted-foreground">Last sync</p>
        {loading ? (
          <Skeleton className="mt-3 h-9 w-36 rounded-none bg-muted" />
        ) : (
          <p className="font-display mt-2 text-2xl tracking-tight text-foreground sm:text-3xl">
            {stats?.last_sync || "—"}
          </p>
        )}
      </article>
    </section>
  )
}
