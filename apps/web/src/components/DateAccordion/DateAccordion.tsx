import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { DateGroupSummary } from "../../types/dashboard";
import type { DirectionFilter, SortOption } from "../../types/dashboard";
import { FilterBar } from "../FilterBar/FilterBar";
import { ChevronDownIcon, EyeIcon, TrashIcon } from "../Icons/Icons";


type DateAccordionProps = {
  groups: DateGroupSummary[];
  activeDate: string;
  searchTerm: string;
  directionFilter: DirectionFilter;
  sortBy: SortOption;
  visibleCount: number;
  onSelectDate: (tradeDate: string) => void;
  onSearchChange: (value: string) => void;
  onDirectionChange: (value: DirectionFilter) => void;
  onSortChange: (value: SortOption) => void;
  onDeleteDate: (tradeDate: string) => Promise<void>;
  deletingTradeDate: string | null;
  onClearFilters: () => void;
};

type StatItem = {
  label: string;
  value: number;
  toneClassName: string;
  tooltipTitle?: string;
  tooltipSymbols?: string[];
};

type ActiveTooltip = {
  title: string;
  symbols: string[];
  x: number;
  y: number;
  placement: "top" | "bottom";
};


export function DateAccordion({
  groups,
  activeDate,
  searchTerm,
  directionFilter,
  sortBy,
  visibleCount,
  onSelectDate,
  onSearchChange,
  onDirectionChange,
  onSortChange,
  onDeleteDate,
  deletingTradeDate,
  onClearFilters,
}: DateAccordionProps) {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [activeTooltip, setActiveTooltip] = useState<ActiveTooltip | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const latestDate = groups[0]?.trade_date ?? "";

  useEffect(() => {
    if (groups.length === 0) {
      return;
    }
    setExpandedGroups((currentState) => {
      if (Object.keys(currentState).length > 0) {
        return currentState;
      }
      return { [groups[0].trade_date]: true };
    });
  }, [groups]);

  useEffect(() => {
    if (!activeDate) {
      return;
    }

    setExpandedGroups((currentState) => {
      if (currentState[activeDate]) {
        return currentState;
      }

      return {
        ...currentState,
        [activeDate]: true,
      };
    });
  }, [activeDate]);

  useEffect(() => {
    const handleDismissTooltip = () => {
      setActiveTooltip(null);
    };

    const listElement = listRef.current;
    window.addEventListener("resize", handleDismissTooltip);
    window.addEventListener("scroll", handleDismissTooltip, true);
    listElement?.addEventListener("scroll", handleDismissTooltip);

    return () => {
      window.removeEventListener("resize", handleDismissTooltip);
      window.removeEventListener("scroll", handleDismissTooltip, true);
      listElement?.removeEventListener("scroll", handleDismissTooltip);
    };
  }, []);

  const revealGroup = (tradeDate: string) => {
    requestAnimationFrame(() => {
      const target = listRef.current?.querySelector<HTMLElement>(`[data-trade-date="${tradeDate}"]`);
      target?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    });
  };

  const showTooltip = (target: HTMLElement, title: string, symbols: string[]) => {
    const tooltipWidth = 272;
    const viewportPadding = 16;
    const anchorRect = target.getBoundingClientRect();
    const centeredX = anchorRect.left + (anchorRect.width / 2);
    const minX = viewportPadding + (tooltipWidth / 2);
    const maxX = window.innerWidth - viewportPadding - (tooltipWidth / 2);
    const x = Math.min(Math.max(centeredX, minX), maxX);
    const placement = anchorRect.top < 220 ? "bottom" : "top";
    const y = placement === "top" ? anchorRect.top - 12 : anchorRect.bottom + 12;

    setActiveTooltip({
      title,
      symbols,
      x,
      y,
      placement,
    });
  };

  const handleDeleteDate = async (tradeDate: string) => {
    if (deletingTradeDate) {
      return;
    }

    if (typeof window !== "undefined") {
      const confirmed = window.confirm(`确认删除 ${tradeDate} 的导入数据吗？此操作不可撤销。`);
      if (!confirmed) {
        return;
      }
    }

    try {
      await onDeleteDate(tradeDate);
    } catch (error) {
      const message = error instanceof Error ? error.message : `删除 ${tradeDate} 失败。`;
      if (typeof window !== "undefined") {
        window.alert(message);
      }
    }
  };

  return (
    <>
      <div className="date-accordion">
        <FilterBar
          availableDates={groups.map((group) => group.trade_date)}
          selectedDate={activeDate}
          latestDate={latestDate}
          searchTerm={searchTerm}
          directionFilter={directionFilter}
          sortBy={sortBy}
          visibleCount={visibleCount}
          onDateChange={onSelectDate}
          onSearchChange={onSearchChange}
          onDirectionChange={onDirectionChange}
          onSortChange={onSortChange}
          onClear={onClearFilters}
        />

        <div ref={listRef} className="date-accordion__list">
          {groups.map((group) => {
            const isExpanded = expandedGroups[group.trade_date] ?? false;
            const isActive = activeDate === group.trade_date;
            const isDeleting = deletingTradeDate === group.trade_date;
            const statItems: StatItem[] = [
              {
                label: "方向",
                value: group.directional_count,
                toneClassName: "date-card__stat--direction",
                tooltipTitle: "方向标的",
                tooltipSymbols: group.directional_symbols,
              },
              {
                label: "波动",
                value: group.volatility_count,
                toneClassName: "date-card__stat--volatility",
                tooltipTitle: "波动标的",
                tooltipSymbols: group.volatility_symbols,
              },
              {
                label: "中性",
                value: group.neutral_count,
                toneClassName: "date-card__stat--neutral",
              },
              {
                label: "观察",
                value: group.watchlist_count,
                toneClassName: "date-card__stat--watchlist",
              },
            ];

            return (
              <article
                key={group.trade_date}
                data-trade-date={group.trade_date}
                className={`date-card${isActive ? " date-card--active" : ""}`}
              >
                <button
                  className="date-card__toggle"
                  type="button"
                  aria-expanded={isExpanded}
                  aria-controls={`date-card-body-${group.trade_date}`}
                  onClick={() => {
                    const nextExpanded = !isExpanded;
                    setExpandedGroups((currentState) => ({
                      ...currentState,
                      [group.trade_date]: nextExpanded,
                    }));

                    if (nextExpanded) {
                      revealGroup(group.trade_date);
                    }
                  }}
                >
                  <div>
                    <strong>{group.trade_date}</strong>
                    <span>{group.total_signals} 个标的</span>
                  </div>
                  <ChevronDownIcon
                    className={`date-card__toggle-icon${isExpanded ? " date-card__toggle-icon--expanded" : ""}`}
                    aria-hidden="true"
                  />
                </button>

                {isExpanded ? (
                  <div id={`date-card-body-${group.trade_date}`} className="date-card__body">
                    <dl className="date-card__stats">
                      {statItems.map((item) => {
                        const tooltipSymbols = item.tooltipSymbols;
                        const hasTooltip = tooltipSymbols !== undefined;
                        const tooltipTitle = item.tooltipTitle ?? `${item.label}标的`;
                        const tooltipLabel = tooltipSymbols && tooltipSymbols.length > 0
                          ? tooltipSymbols.join(", ")
                          : "暂无标的";

                        return (
                          <div
                            key={item.label}
                            className={`date-card__stat ${item.toneClassName}${hasTooltip ? " date-card__stat--tooltip" : ""}`}
                            tabIndex={hasTooltip ? 0 : undefined}
                            aria-label={hasTooltip ? `${tooltipTitle}: ${tooltipLabel}` : undefined}
                            onMouseEnter={
                              hasTooltip
                                ? (event) => showTooltip(event.currentTarget, tooltipTitle, tooltipSymbols)
                                : undefined
                            }
                            onMouseLeave={hasTooltip ? () => setActiveTooltip(null) : undefined}
                            onFocus={
                              hasTooltip
                                ? (event) => showTooltip(event.currentTarget, tooltipTitle, tooltipSymbols)
                                : undefined
                            }
                            onBlur={hasTooltip ? () => setActiveTooltip(null) : undefined}
                          >
                            <dt>{item.label}</dt>
                            <dd>{item.value}</dd>
                          </div>
                        );
                      })}
                    </dl>

                    <div className="date-card__actions">
                      <button
                        className="button button--icon"
                        type="button"
                        onClick={() => onSelectDate(group.trade_date)}
                        aria-label={`查看 ${group.trade_date}`}
                        title={`查看 ${group.trade_date}`}
                      >
                        <EyeIcon aria-hidden="true" />
                      </button>
                      <button
                        className="button button--ghost button--danger button--icon"
                        type="button"
                        onClick={() => {
                          void handleDeleteDate(group.trade_date);
                        }}
                        disabled={deletingTradeDate !== null}
                        aria-label={isDeleting ? `正在删除 ${group.trade_date}` : `删除 ${group.trade_date}`}
                        title={isDeleting ? `正在删除 ${group.trade_date}` : `删除 ${group.trade_date}`}
                      >
                        <TrashIcon aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </div>

      {activeTooltip && typeof document !== "undefined"
        ? createPortal(
          <div
            className={`floating-symbol-tooltip floating-symbol-tooltip--${activeTooltip.placement}`}
            role="tooltip"
            style={{
              left: `${activeTooltip.x}px`,
              top: `${activeTooltip.y}px`,
            }}
          >
            <div className="floating-symbol-tooltip__header">
              <span className="floating-symbol-tooltip__dot" aria-hidden="true" />
              <strong>{activeTooltip.title}</strong>
            </div>
            <p>{activeTooltip.symbols.length > 0 ? activeTooltip.symbols.join(" · ") : "暂无标的"}</p>
          </div>,
          document.body,
        )
        : null}
    </>
  );
}
