import type { TrendConsistencySummary } from "../../types/dashboard";
import { EmptyState } from "../EmptyState/EmptyState";
import { XIcon } from "../Icons/Icons";
import { LoadingState } from "../LoadingState/LoadingState";
import type { TrendCategoryKey } from "../TrendConsistencyStrip/TrendConsistencyStrip";


type TrendConsistencyDrawerProps = {
  category: TrendCategoryKey | null;
  summary?: TrendConsistencySummary;
  tradeDate: string;
  isLoading: boolean;
  error?: Error | null;
  onClose: () => void;
  onSelectSymbol: (symbol: string) => void;
};


export function TrendConsistencyDrawer({
  category,
  summary,
  tradeDate,
  isLoading,
  error,
  onClose,
  onSelectSymbol,
}: TrendConsistencyDrawerProps) {
  if (category === null) {
    return null;
  }

  const title = category === "directional" ? "方向" : "波动";
  const description = category === "directional"
    ? "展示 Δ3D / Δ5D 同向变化的方向标的。"
    : "展示 Δ3D / Δ5D 同向变化的波动标的。";
  const emptyCategorySummary = {
    overlap: [],
    delta_3d: [],
    delta_5d: [],
  };
  const categorySummary = category === "directional"
    ? (summary?.directional ?? emptyCategorySummary)
    : (summary?.volatility ?? emptyCategorySummary);
  const overlapItems = categorySummary.overlap ?? [];
  const delta3dItems = categorySummary.delta_3d ?? [];
  const delta5dItems = categorySummary.delta_5d ?? [];
  const overlapSymbols = new Set(overlapItems.map((item) => item.symbol));
  const sections = [
    {
      key: "delta_3d",
      label: "Δ3D",
      items: delta3dItems,
      primaryMetric: "delta_3d" as const,
      secondaryMetric: "delta_5d" as const,
    },
    {
      key: "delta_5d",
      label: "Δ5D",
      items: delta5dItems,
      primaryMetric: "delta_5d" as const,
      secondaryMetric: "delta_3d" as const,
    },
  ];

  return (
    <aside className="detail-drawer trend-detail-drawer">
      <div className="detail-drawer__header trend-detail-drawer__header">
        <div>
          <p className="eyebrow">趋势详情</p>
          <h3>{title}</h3>
          <p className="trend-detail-drawer__description">{description}</p>
        </div>
        <button
          className="button button--ghost button--icon"
          type="button"
          onClick={onClose}
          aria-label={`关闭${title}趋势详情`}
          title={`关闭${title}趋势详情`}
        >
          <XIcon aria-hidden="true" />
        </button>
      </div>

      {isLoading ? (
        <LoadingState title={`正在加载${title}详情`} note="正在整理多日趋势一致标的。" />
      ) : null}

      {!isLoading && error ? (
        <EmptyState
          tone="error"
          title={`${title}详情加载失败`}
          note={error.message}
        />
      ) : null}

      {!isLoading && !error ? (
        <div className="detail-drawer__body">
          <div className="trend-detail-drawer__meta">
            <div>
              <span>交易日</span>
              <strong>{tradeDate || "--"}</strong>
            </div>
            <div>
              <span>交集标的</span>
              <strong>{overlapItems.length}</strong>
            </div>
          </div>

          {delta3dItems.length > 0 || delta5dItems.length > 0 ? (
            <div className="trend-detail-sections">
              {sections.map((section) => (
                <section key={section.key} className="trend-detail-section">
                  <header className="trend-detail-section__header">
                    <h4>{section.label}</h4>
                    <span>{section.items.length} 个</span>
                  </header>

                  {section.items.length > 0 ? (
                    <ul className="trend-detail-list">
                      {section.items.map((item) => {
                        const isOverlap = overlapSymbols.has(item.symbol);
                        const primaryValue = item[section.primaryMetric];
                        const secondaryValue = item[section.secondaryMetric];

                        return (
                          <li key={`${category}-${section.key}-${item.symbol}`}>
                            <button
                              className={[
                                "trend-detail-list__item",
                                isOverlap ? "trend-detail-list__item--overlap" : "",
                              ].filter(Boolean).join(" ")}
                              type="button"
                              onClick={() => onSelectSymbol(item.symbol)}
                            >
                              <div className="trend-detail-list__main">
                                <div className="trend-detail-list__headline">
                                  <strong>{item.symbol}</strong>
                                  {isOverlap ? <span className="trend-overlap-badge">交集</span> : null}
                                  <span className={`trend-pill trend-pill--${item.trend}`}>
                                    {formatTrendLabel(item.trend)}
                                  </span>
                                </div>
                                <span className="trend-detail-list__score">
                                  当前分值 {formatScore(item.current_score)}
                                </span>
                              </div>
                              <div className="trend-detail-list__metrics">
                                <span
                                  className={`trend-detail-list__metric trend-detail-list__metric--${section.primaryMetric.replace("_", "-")}`}
                                >
                                  {section.label} {formatDelta(primaryValue)}
                                </span>
                                <span
                                  className={`trend-detail-list__metric trend-detail-list__metric--${section.secondaryMetric.replace("_", "-")}`}
                                >
                                  {section.secondaryMetric === "delta_5d" ? "Δ5D" : "Δ3D"} {formatDelta(secondaryValue)}
                                </span>
                              </div>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <div className="trend-detail-section__empty">
                      <span>{section.label} 暂无可展示数据</span>
                    </div>
                  )}
                </section>
              ))}
            </div>
          ) : (
            <EmptyState
              title={`暂无${title}一致标的`}
              note="当前交易日没有同时满足 Δ3D 与 Δ5D 同向变化的标的。"
            />
          )}
        </div>
      ) : null}
    </aside>
  );
}


function formatDelta(value: number): string {
  return value > 0 ? `+${value.toFixed(1)}` : value.toFixed(1);
}


function formatScore(value: number): string {
  return value.toFixed(1);
}


function formatTrendLabel(value: "up" | "down" | "mixed"): string {
  if (value === "up") {
    return "上行";
  }
  if (value === "down") {
    return "下行";
  }
  return "分歧";
}
