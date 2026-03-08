import type {
  ApiErrorPayload,
  ApiResponse,
  ChartPoint,
  DateGroupSummary,
  DeleteDateGroupResult,
  FiltersPayload,
  SignalRecord,
  SymbolHistoryResponse,
  TrendConsistencySummary,
} from "../types/dashboard";


const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:18000").replace(/\/$/, "");


export class ApiClientError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown>;

  constructor(message: string, options: { code: string; status: number; details?: Record<string, unknown> }) {
    super(message);
    this.name = "ApiClientError";
    this.code = options.code;
    this.status = options.status;
    this.details = options.details;
  }
}


async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  let payload: ApiResponse<T> | null = null;
  try {
    payload = (await response.json()) as ApiResponse<T>;
  } catch {
    throw new ApiClientError("API 返回了无法解析的响应。", {
      code: "invalid_response",
      status: response.status,
    });
  }

  if (!response.ok || payload.error) {
    const error = payload.error ?? fallbackError(response.status);
    throw new ApiClientError(error.message, {
      code: error.code,
      status: response.status,
      details: error.details,
    });
  }

  if (payload.data === null) {
    throw new ApiClientError("API 返回了空数据。", {
      code: "empty_payload",
      status: response.status,
    });
  }

  return payload.data;
}


function fallbackError(status: number): ApiErrorPayload {
  return {
    code: "http_error",
    message: `请求失败，状态码 ${status}。`,
  };
}


export function fetchFilters(): Promise<FiltersPayload> {
  return request<FiltersPayload>("/api/v1/filters");
}


export function fetchDateGroups(limit: number): Promise<DateGroupSummary[]> {
  return request<DateGroupSummary[]>(`/api/v1/date-groups?limit=${limit}`);
}


export function fetchChartPoints(tradeDate: string): Promise<ChartPoint[]> {
  return request<ChartPoint[]>(`/api/v1/chart-points?trade_date=${tradeDate}`);
}


export function fetchTrendConsistency(tradeDate: string, limit = 6): Promise<TrendConsistencySummary> {
  return request<TrendConsistencySummary>(
    `/api/v1/trend-consistency?trade_date=${tradeDate}&limit=${limit}`,
  );
}


export function fetchSignal(symbol: string, tradeDate: string): Promise<SignalRecord> {
  return request<SignalRecord>(`/api/v1/signals/${encodeURIComponent(symbol)}?trade_date=${tradeDate}`);
}


export function fetchSymbolHistory(symbol: string, lookbackDays: number): Promise<SymbolHistoryResponse> {
  return request<SymbolHistoryResponse>(
    `/api/v1/symbol-history/${encodeURIComponent(symbol)}?lookback_days=${lookbackDays}`,
  );
}


export function deleteDateGroup(tradeDate: string): Promise<DeleteDateGroupResult> {
  return request<DeleteDateGroupResult>(`/api/v1/date-groups/${encodeURIComponent(tradeDate)}`, {
    method: "DELETE",
  });
}
