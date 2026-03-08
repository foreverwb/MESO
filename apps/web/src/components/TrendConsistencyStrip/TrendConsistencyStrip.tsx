import type { TrendConsistencySummary } from "../../types/dashboard";


export type TrendCategoryKey = "directional" | "volatility";

type TrendConsistencyStripProps = {
  summary?: TrendConsistencySummary;
  isLoading: boolean;
  error?: Error | null;
  activeCategory: TrendCategoryKey | null;
  onToggleCategory: (category: TrendCategoryKey) => void;
};

type TrendCard = {
  key: TrendCategoryKey;
  label: string;
  count: number;
};


export function TrendConsistencyStrip({
  summary,
  isLoading,
  error,
  activeCategory,
  onToggleCategory,
}: TrendConsistencyStripProps) {
  const cards: TrendCard[] = [
    {
      key: "directional",
      label: "方向",
      count: summary?.directional.overlap.length ?? 0,
    },
    {
      key: "volatility",
      label: "波动",
      count: summary?.volatility.overlap.length ?? 0,
    },
  ];

  return (
    <div className="trend-summary" aria-label="多日趋势一致标的摘要">
      {cards.map((card) => {
        const isActive = activeCategory === card.key;
        const isDisabled = isLoading || error !== null;
        const toneClassName = card.key === "directional"
          ? "trend-summary-card--directional"
          : "trend-summary-card--volatility";
        let value = String(card.count);
        if (isLoading) {
          value = "...";
        } else if (error) {
          value = "!";
        }

        return (
          <button
            key={card.key}
            className={[
              "trend-summary-card",
              toneClassName,
              isActive ? "trend-summary-card--active" : "",
            ].filter(Boolean).join(" ")}
            type="button"
            onClick={() => onToggleCategory(card.key)}
            disabled={isDisabled}
            aria-pressed={isActive}
            aria-label={buildAriaLabel({
              label: card.label,
              count: card.count,
              isLoading,
              hasError: error !== null,
            })}
          >
            <span className="trend-summary-card__label">{card.label}</span>
            <strong className="trend-summary-card__value">{value}</strong>
          </button>
        );
      })}
    </div>
  );
}


function buildAriaLabel(options: {
  label: string;
  count: number;
  isLoading: boolean;
  hasError: boolean;
}): string {
  if (options.isLoading) {
    return `${options.label}详情正在加载`;
  }
  if (options.hasError) {
    return `${options.label}详情加载失败`;
  }
  return `${options.label}趋势一致标的 ${options.count} 个，点击查看详情`;
}
