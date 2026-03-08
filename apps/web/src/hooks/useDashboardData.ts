import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteDateGroup,
  fetchChartPoints,
  fetchDateGroups,
  fetchFilters,
  fetchSignal,
  fetchSymbolHistory,
  fetchTrendConsistency,
} from "../services/api";
import type {
  ChartPoint,
  DateGroupSummary,
  DirectionFilter,
  FiltersPayload,
  SignalRecord,
  SortOption,
  SymbolHistoryResponse,
  TrendConsistencySummary,
} from "../types/dashboard";


type DashboardDataState = {
  filters: FiltersPayload | undefined;
  dateGroups: DateGroupSummary[];
  selectedDate: string;
  selectedSymbol: string;
  chartPoints: ChartPoint[];
  trendConsistency: TrendConsistencySummary | undefined;
  activeSignal: SignalRecord | undefined;
  symbolHistory: SymbolHistoryResponse | undefined;
  searchTerm: string;
  directionFilter: DirectionFilter;
  sortBy: SortOption;
  isBootstrapping: boolean;
  isFiltersLoading: boolean;
  isDateGroupsLoading: boolean;
  isChartLoading: boolean;
  isTrendConsistencyLoading: boolean;
  isDetailLoading: boolean;
  filtersError: Error | null;
  dateGroupsError: Error | null;
  chartError: Error | null;
  trendConsistencyError: Error | null;
  detailError: Error | null;
  setSelectedDate: (tradeDate: string) => void;
  setSelectedSymbol: (symbol: string) => void;
  setSearchTerm: (value: string) => void;
  setDirectionFilter: (value: DirectionFilter) => void;
  setSortBy: (value: SortOption) => void;
  deleteTradeDate: (tradeDate: string) => Promise<void>;
  deletingTradeDate: string | null;
  clearFilters: () => void;
};


export function useDashboardData(): DashboardDataState {
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDateState] = useState("");
  const [selectedSymbol, setSelectedSymbolState] = useState("");
  const [searchTerm, setSearchTermState] = useState("");
  const [directionFilter, setDirectionFilterState] = useState<DirectionFilter>("all");
  const [sortBy, setSortByState] = useState<SortOption>("confidence");
  const deleteDateMutation = useMutation({
    mutationFn: deleteDateGroup,
  });

  const deferredSearchTerm = useDeferredValue(searchTerm.trim().toUpperCase());

  const filtersQuery = useQuery({
    queryKey: ["dashboard-filters"],
    queryFn: fetchFilters,
    staleTime: 5 * 60 * 1000,
  });

  const dateGroupLimit = filtersQuery.data?.default_date_group_size_days ?? 30;
  const dateGroupsQuery = useQuery({
    queryKey: ["dashboard-date-groups", dateGroupLimit],
    queryFn: () => fetchDateGroups(dateGroupLimit),
    staleTime: 60 * 1000,
  });

  useEffect(() => {
    if (!selectedDate && dateGroupsQuery.data && dateGroupsQuery.data.length > 0) {
      startTransition(() => {
        setSelectedDateState(dateGroupsQuery.data[0].trade_date);
      });
    }
  }, [selectedDate, dateGroupsQuery.data]);

  const chartPointsQuery = useQuery({
    queryKey: ["dashboard-chart-points", selectedDate],
    queryFn: () => fetchChartPoints(selectedDate),
    enabled: selectedDate.length > 0,
    staleTime: 30 * 1000,
  });

  const trendConsistencyQuery = useQuery({
    queryKey: ["dashboard-trend-consistency", selectedDate],
    queryFn: () => fetchTrendConsistency(selectedDate),
    enabled: selectedDate.length > 0,
    staleTime: 30 * 1000,
  });

  const detailSignalQuery = useQuery({
    queryKey: ["dashboard-signal", selectedSymbol, selectedDate],
    queryFn: () => fetchSignal(selectedSymbol, selectedDate),
    enabled: selectedSymbol.length > 0 && selectedDate.length > 0,
    staleTime: 30 * 1000,
  });

  const symbolHistoryQuery = useQuery({
    queryKey: ["dashboard-symbol-history", selectedSymbol],
    queryFn: () => fetchSymbolHistory(selectedSymbol, 10),
    enabled: selectedSymbol.length > 0,
    staleTime: 30 * 1000,
  });

  useEffect(() => {
    if (!selectedSymbol || !chartPointsQuery.data) {
      return;
    }

    const stillVisible = chartPointsQuery.data.some((point) => point.symbol === selectedSymbol);
    if (!stillVisible) {
      startTransition(() => {
        setSelectedSymbolState("");
      });
    }
  }, [selectedSymbol, chartPointsQuery.data]);

  const visibleChartPoints = filterAndSortChartPoints({
    points: chartPointsQuery.data ?? [],
    searchTerm: deferredSearchTerm,
    directionFilter,
    sortBy,
  });
  const deletingTradeDate = deleteDateMutation.isPending ? (deleteDateMutation.variables ?? null) : null;

  return {
    filters: filtersQuery.data,
    dateGroups: dateGroupsQuery.data ?? [],
    selectedDate,
    selectedSymbol,
    chartPoints: visibleChartPoints,
    trendConsistency: trendConsistencyQuery.data,
    activeSignal: detailSignalQuery.data,
    symbolHistory: symbolHistoryQuery.data,
    searchTerm,
    directionFilter,
    sortBy,
    isBootstrapping: !selectedDate && dateGroupsQuery.isLoading,
    isFiltersLoading: filtersQuery.isLoading,
    isDateGroupsLoading: dateGroupsQuery.isLoading,
    isChartLoading: chartPointsQuery.isLoading,
    isTrendConsistencyLoading: trendConsistencyQuery.isLoading,
    isDetailLoading: detailSignalQuery.isLoading || symbolHistoryQuery.isLoading,
    filtersError: (filtersQuery.error as Error | null) ?? null,
    dateGroupsError: (dateGroupsQuery.error as Error | null) ?? null,
    chartError: (chartPointsQuery.error as Error | null) ?? null,
    trendConsistencyError: (trendConsistencyQuery.error as Error | null) ?? null,
    detailError: (detailSignalQuery.error as Error | null) ?? (symbolHistoryQuery.error as Error | null) ?? null,
    setSelectedDate: (tradeDate: string) => {
      startTransition(() => {
        setSelectedDateState(tradeDate);
        setSelectedSymbolState("");
      });
    },
    setSelectedSymbol: (symbol: string) => {
      startTransition(() => {
        setSelectedSymbolState(symbol);
      });
    },
    setSearchTerm: (value: string) => {
      setSearchTermState(value);
    },
    setDirectionFilter: (value: DirectionFilter) => {
      setDirectionFilterState(value);
    },
    setSortBy: (value: SortOption) => {
      setSortByState(value);
    },
    deleteTradeDate: async (tradeDate: string) => {
      await deleteDateMutation.mutateAsync(tradeDate);
      const refreshedGroups = (await dateGroupsQuery.refetch()).data ?? [];

      if (selectedDate !== tradeDate) {
        return;
      }

      startTransition(() => {
        setSelectedDateState(refreshedGroups[0]?.trade_date ?? "");
        setSelectedSymbolState("");
      });
    },
    deletingTradeDate,
    clearFilters: () => {
      startTransition(() => {
        setSearchTermState("");
        setDirectionFilterState("all");
        setSortByState("confidence");
        setSelectedSymbolState("");
      });

      void queryClient.invalidateQueries({ queryKey: ["dashboard-filters"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-date-groups"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-chart-points"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-trend-consistency"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-signal"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-symbol-history"] });

      void dateGroupsQuery.refetch().then((result) => {
        const latestTradeDate = result.data?.[0]?.trade_date;
        if (!latestTradeDate) {
          return;
        }

        startTransition(() => {
          setSelectedDateState(latestTradeDate);
        });
      });
    },
  };
}


function filterAndSortChartPoints(options: {
  points: ChartPoint[];
  searchTerm: string;
  directionFilter: DirectionFilter;
  sortBy: SortOption;
}): ChartPoint[] {
  const filteredPoints = options.points.filter((point) => {
    if (options.searchTerm && !point.symbol.toUpperCase().includes(options.searchTerm)) {
      return false;
    }

    if (options.directionFilter === "bullish" && point.x_score < 0) {
      return false;
    }
    if (options.directionFilter === "bearish" && point.x_score > 0) {
      return false;
    }
    if (options.directionFilter === "watchlist" && !point.highlight) {
      return false;
    }

    return true;
  });

  return [...filteredPoints].sort((left, right) => {
    if (options.sortBy === "symbol") {
      return left.symbol.localeCompare(right.symbol);
    }
    if (options.sortBy === "persistence") {
      return (right.s_pers ?? 0) - (left.s_pers ?? 0);
    }
    return (right.s_conf ?? 0) - (left.s_conf ?? 0);
  });
}
