import type { DirectionFilter, SortOption } from "../../types/dashboard";
import { RefreshIcon } from "../Icons/Icons";


type FilterBarProps = {
  availableDates: string[];
  selectedDate: string;
  latestDate: string;
  searchTerm: string;
  directionFilter: DirectionFilter;
  sortBy: SortOption;
  visibleCount: number;
  onDateChange: (tradeDate: string) => void;
  onSearchChange: (value: string) => void;
  onDirectionChange: (value: DirectionFilter) => void;
  onSortChange: (value: SortOption) => void;
  onClear: () => void;
};


export function FilterBar(props: FilterBarProps) {
  const currentDate = props.selectedDate || props.latestDate || props.availableDates[0] || "";

  return (
    <section className="filter-bar">
      <div className="filter-bar__intro">
        <div className="filter-bar__topline">
          <p className="eyebrow">筛选条件</p>
          <button
            className="button button--ghost button--icon filter-bar__icon-button"
            type="button"
            onClick={props.onClear}
            aria-label="刷新数据"
            title="刷新数据"
          >
            <RefreshIcon aria-hidden="true" />
          </button>
        </div>
        <p className="filter-bar__summary">
          当前日期 {currentDate || "暂无"} · 当前显示 {props.visibleCount} 个标的
        </p>
      </div>

      <div className="filter-bar__controls">
        <label className="field">
          <span>日期</span>
          <select
            className="field__control"
            value={currentDate}
            onChange={(event) => props.onDateChange(event.target.value)}
          >
            {props.availableDates.map((tradeDate) => (
              <option key={tradeDate} value={tradeDate}>
                {tradeDate}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>标的代码</span>
          <input
            className="field__control"
            type="search"
            placeholder="输入代码，如 AAPL / NVDA / ETF"
            value={props.searchTerm}
            onChange={(event) => props.onSearchChange(event.target.value)}
          />
        </label>

        <label className="field">
          <span>方向</span>
          <select
            className="field__control"
            value={props.directionFilter}
            onChange={(event) => props.onDirectionChange(event.target.value as DirectionFilter)}
          >
            <option value="all">全部</option>
            <option value="bullish">看涨</option>
            <option value="bearish">看跌</option>
            <option value="watchlist">观察列表</option>
          </select>
        </label>

        <label className="field">
          <span>排序</span>
          <select
            className="field__control"
            value={props.sortBy}
            onChange={(event) => props.onSortChange(event.target.value as SortOption)}
          >
            <option value="confidence">按置信度</option>
            <option value="persistence">按持续性</option>
            <option value="symbol">按代码</option>
          </select>
        </label>
      </div>
    </section>
  );
}
