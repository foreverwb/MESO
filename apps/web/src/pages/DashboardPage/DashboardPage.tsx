import { useEffect, useState } from "react";

import { EmptyState } from "../../components/EmptyState/EmptyState";
import { LoadingState } from "../../components/LoadingState/LoadingState";
import { DateAccordion } from "../../components/DateAccordion/DateAccordion";
import { QuadrantChart } from "../../components/QuadrantChart/QuadrantChart";
import { SymbolDetailDrawer } from "../../components/SymbolDetailDrawer/SymbolDetailDrawer";
import { TrendConsistencyDrawer } from "../../components/TrendConsistencyDrawer/TrendConsistencyDrawer";
import { TrendConsistencyStrip, type TrendCategoryKey } from "../../components/TrendConsistencyStrip/TrendConsistencyStrip";
import { useDashboardData } from "../../hooks/useDashboardData";


export default function DashboardPage() {
  const dashboard = useDashboardData();
  const latestDate = dashboard.dateGroups[0]?.trade_date ?? "";
  const [activeTrendCategory, setActiveTrendCategory] = useState<TrendCategoryKey | null>(null);

  useEffect(() => {
    setActiveTrendCategory(null);
  }, [dashboard.selectedDate]);

  const handleToggleTrendCategory = (category: TrendCategoryKey) => {
    setActiveTrendCategory((currentCategory) => currentCategory === category ? null : category);
  };

  const handleSelectSymbol = (symbol: string) => {
    setActiveTrendCategory(null);
    dashboard.setSelectedSymbol(symbol);
  };

  return (
    <main className="dashboard-shell">
      <div className="dashboard-backdrop" aria-hidden="true" />

      <div className="dashboard-workspace">
        <section className="dashboard-main panel">
          <header className="panel-header">
            <div>
              <h2>{dashboard.selectedDate || latestDate || "等待数据"}</h2>
            </div>
            <TrendConsistencyStrip
              summary={dashboard.trendConsistency}
              isLoading={dashboard.isTrendConsistencyLoading}
              error={dashboard.trendConsistencyError}
              activeCategory={activeTrendCategory}
              onToggleCategory={handleToggleTrendCategory}
            />
          </header>

          <div className="dashboard-main__body">
            {dashboard.isBootstrapping || dashboard.isChartLoading ? (
              <LoadingState
                title="正在加载图表"
                note="正在拉取最新日期切片并映射到象限气泡图。"
              />
            ) : null}

            {!dashboard.isBootstrapping && !dashboard.isChartLoading && dashboard.chartError ? (
              <EmptyState
                tone="error"
                title="图表数据加载失败"
                note={dashboard.chartError.message}
              />
            ) : null}

            {!dashboard.isBootstrapping &&
            !dashboard.isChartLoading &&
            !dashboard.chartError &&
            dashboard.chartPoints.length === 0 ? (
              <EmptyState
                title="当前筛选下没有匹配标的"
                note="请调整搜索、方向或日期筛选，重新填充气泡图。"
              />
            ) : null}

            {!dashboard.isBootstrapping &&
            !dashboard.isChartLoading &&
            !dashboard.chartError &&
            dashboard.chartPoints.length > 0 ? (
              <>
                <QuadrantChart
                  points={dashboard.chartPoints}
                  selectedSymbol={dashboard.selectedSymbol}
                  onSelectSymbol={handleSelectSymbol}
                />
                {activeTrendCategory !== null ? (
                  <TrendConsistencyDrawer
                    category={activeTrendCategory}
                    summary={dashboard.trendConsistency}
                    tradeDate={dashboard.selectedDate || latestDate}
                    isLoading={dashboard.isTrendConsistencyLoading}
                    error={dashboard.trendConsistencyError}
                    onClose={() => setActiveTrendCategory(null)}
                    onSelectSymbol={handleSelectSymbol}
                  />
                ) : (
                  <SymbolDetailDrawer
                    selectedSymbol={dashboard.selectedSymbol}
                    signal={dashboard.activeSignal}
                    history={dashboard.symbolHistory}
                    isLoading={dashboard.isDetailLoading}
                    error={dashboard.detailError}
                    onClose={() => dashboard.setSelectedSymbol("")}
                  />
                )}
              </>
            ) : null}
          </div>
        </section>

        <aside className="dashboard-sidebar panel">
          {dashboard.isDateGroupsLoading || dashboard.isFiltersLoading ? (
            <LoadingState
              title="正在加载历史日期"
              note="正在整理右侧面板的近期交易日分组。"
            />
          ) : null}

          {!dashboard.isDateGroupsLoading && dashboard.dateGroupsError ? (
            <EmptyState
              tone="error"
              title="历史日期加载失败"
              note={dashboard.dateGroupsError.message}
            />
          ) : null}

          {!dashboard.isDateGroupsLoading &&
          !dashboard.dateGroupsError &&
          dashboard.dateGroups.length === 0 ? (
            <EmptyState
              title="没有可用的历史日期"
              note="后端当前没有返回可展示的交易日分组数据。"
            />
          ) : null}

          {!dashboard.isDateGroupsLoading &&
          !dashboard.dateGroupsError &&
          dashboard.dateGroups.length > 0 ? (
            <DateAccordion
              groups={dashboard.dateGroups}
              activeDate={dashboard.selectedDate}
              searchTerm={dashboard.searchTerm}
              directionFilter={dashboard.directionFilter}
              sortBy={dashboard.sortBy}
              visibleCount={dashboard.chartPoints.length}
              onSelectDate={dashboard.setSelectedDate}
              onSearchChange={dashboard.setSearchTerm}
              onDirectionChange={dashboard.setDirectionFilter}
              onSortChange={dashboard.setSortBy}
              onDeleteDate={dashboard.deleteTradeDate}
              deletingTradeDate={dashboard.deletingTradeDate}
              onClearFilters={dashboard.clearFilters}
            />
          ) : null}
        </aside>
      </div>
    </main>
  );
}
