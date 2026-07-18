import { motion, useReducedMotion } from "motion/react"
import { useMemo } from "react"

import { AnimatedNumber } from "@/components/AnimatedNumber"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { categoryLabel, formatNumber } from "@/lib/taxonomy"
import { cn } from "@/lib/utils"

export type TechniqueCategory = {
  name: string
  count: number | null
}

type TechniqueSidebarProps = {
  categories: TechniqueCategory[]
  activeCategory: string
  attention: boolean
  loading: boolean
  onSelect: (name: string) => void
  onClear: () => void
}

export function TechniqueSidebar({
  categories,
  activeCategory,
  attention,
  loading,
  onSelect,
  onClear,
}: TechniqueSidebarProps) {
  const reducedMotion = useReducedMotion()

  const { maxCount, knownCount, totalRecords } = useMemo(() => {
    const counts = categories
      .map((item) => item.count)
      .filter((count): count is number => typeof count === "number")

    return {
      maxCount: counts.length ? Math.max(...counts) : 0,
      knownCount: counts.length,
      totalRecords: counts.reduce((sum, count) => sum + count, 0),
    }
  }, [categories])

  return (
    <aside className="panel flex h-full min-h-0 flex-col">
      <div className="border-b border-border px-5 py-5">
        <p className="label-mono text-primary">Techniques</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Filter search or browse by mechanism family.
        </p>
        <div className="mt-4 font-mono text-xs tracking-wide text-muted-foreground tabular-nums">
          {loading ? (
            <Skeleton className="inline-block h-3.5 w-40 rounded-none bg-muted align-middle" />
          ) : (
            <>
              {knownCount} families
              <span className="mx-2 text-border" aria-hidden="true">
                ·
              </span>
              {formatNumber(totalRecords)} records
            </>
          )}
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <nav className="grid gap-1.5 p-3" aria-label="Technique filters">
          {categories.map((category) => {
            const isActive = category.name === activeCategory
            const count = category.count
            const share =
              typeof count === "number" && maxCount > 0
                ? Math.max((count / maxCount) * 100, 4)
                : 0

            return (
              <motion.button
                key={category.name}
                type="button"
                onClick={() => onSelect(category.name)}
                animate={
                  attention && !reducedMotion
                    ? {
                        boxShadow: [
                          "0 0 0 0 transparent",
                          "0 0 0 1px oklch(0.52 0.086 170 / 0.55)",
                          "0 0 0 0 transparent",
                        ],
                      }
                    : undefined
                }
                transition={
                  attention
                    ? { duration: 0.55, repeat: 2, ease: "easeInOut" }
                    : undefined
                }
                className={cn(
                  "relative isolate w-full overflow-hidden px-3 py-3 text-left transition-colors",
                  isActive
                    ? "bg-primary/12 text-foreground outline outline-1 outline-primary/45"
                    : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
                )}
              >
                {typeof count === "number" ? (
                  <span
                    className={cn(
                      "pointer-events-none absolute inset-y-0 left-0 -z-10 transition-[width] duration-300",
                      isActive ? "bg-primary/18" : "bg-primary/10",
                    )}
                    style={{ width: `${share}%` }}
                    aria-hidden="true"
                  />
                ) : null}

                <span className="grid grid-cols-[1fr_auto] items-start gap-3">
                  <span className="text-sm leading-snug" title={category.name}>
                    {categoryLabel(category.name)}
                  </span>
                  {count === null ? (
                    <Skeleton className="mt-0.5 h-3.5 w-10 rounded-none bg-muted" />
                  ) : (
                    <AnimatedNumber
                      value={count}
                      className={cn(
                        "font-mono text-xs tabular-nums",
                        isActive ? "text-primary" : "text-platinum/80",
                      )}
                    />
                  )}
                </span>
              </motion.button>
            )
          })}
        </nav>
      </ScrollArea>

      <div className="border-t border-border p-3">
        <Button
          type="button"
          variant="ghost"
          className="label-mono h-11 min-h-11 w-full justify-start px-3 text-muted-foreground hover:text-primary"
          onClick={onClear}
          disabled={!activeCategory}
        >
          Clear filter
        </Button>
      </div>
    </aside>
  )
}
