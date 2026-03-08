export function formatQuadrantLabel(value: string): string {
  const labels: Record<string, string> = {
    bullish_expansion: "看涨买波",
    bullish_compression: "看涨卖波",
    bearish_expansion: "看跌买波",
    bearish_compression: "看跌卖波",
    neutral: "中性",
  };

  return labels[value] ?? value;
}

export function formatSignalLabel(value: string): string {
  const labels: Record<string, string> = {
    directional_bias: "方向偏置",
    volatility_bias: "波动偏置",
    trend_change: "趋势转折",
    neutral: "中性",
  };

  return labels[value] ?? value;
}

export function formatProbabilityTierLabel(value: string): string {
  const labels: Record<string, string> = {
    low: "低概率",
    mid: "中概率",
    medium: "中概率",
    high: "高概率",
  };

  return labels[value] ?? value;
}

export function formatShiftStateLabel(value: string): string {
  const labels: Record<string, string> = {
    none: "无变化",
    pending: "待确认",
    confirmed: "已确认",
  };

  return labels[value] ?? value;
}
