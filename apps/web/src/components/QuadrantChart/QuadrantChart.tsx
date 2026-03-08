import { useEffect, useRef } from "react";
import * as echarts from "echarts";

import type { ChartPoint } from "../../types/dashboard";
import { formatQuadrantLabel } from "../../utils/dashboardLabels";


type QuadrantChartProps = {
  points: ChartPoint[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
};


export function QuadrantChart({ points, selectedSymbol, onSelectSymbol }: QuadrantChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(containerRef.current);

    const handleClick = (params: { name?: string | number }) => {
      if (typeof params.name === "string") {
        onSelectSymbol(params.name);
      }
    };

    chart.on("click", handleClick);

    return () => {
      resizeObserver.disconnect();
      chart.off("click", handleClick);
      chart.dispose();
      chartRef.current = null;
    };
  }, [onSelectSymbol]);

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    const displayPoints = sortPointsForCanvas(points, selectedSymbol);

    const option: echarts.EChartsOption = {
      animationDuration: 320,
      backgroundColor: "transparent",
      grid: {
        left: 52,
        right: 36,
        top: 44,
        bottom: 44,
      },
      tooltip: {
        trigger: "item",
        backgroundColor: "#ffffff",
        borderColor: "rgba(226, 232, 240, 0.96)",
        borderWidth: 1,
        padding: 0,
        extraCssText: "box-shadow: 0 10px 24px -6px rgba(0,0,0,.10);",
        textStyle: {
          color: "#1e293b",
        },
        formatter: (params) => {
          if (!("data" in params) || !params.data || typeof params.data !== "object") {
            return "";
          }
          const point = (params.data as { payload: ChartPoint }).payload;
          const color = pointColor(point.quadrant);

          return `
            <div style="padding:10px 14px; min-width:180px; max-width:240px; line-height:1.6;">
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:6px;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${color};"></span>
                <span style="font-size:14px; font-weight:700; letter-spacing:-0.01em;">${point.symbol}</span>
              </div>
              <div style="margin-bottom:6px; padding-bottom:6px; border-bottom:1px solid #e2e8f0; font-size:10px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#94a3b8;">
                ${formatCanvasQuadrantLabel(point.quadrant)}
              </div>
              ${tooltipRow("方向得分", formatScore(point.x_score))}
              ${tooltipRow("波动得分", formatScore(point.y_score))}
              ${tooltipRow("置信度", formatScore(point.s_conf))}
              ${tooltipRow("持续性", formatScore(point.s_pers))}
            </div>
          `;
        },
      },
      xAxis: {
        min: -100,
        max: 100,
        name: "",
        axisTick: {
          show: false,
        },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 10,
        },
        axisLine: {
          lineStyle: {
            color: "#cbd5e1",
            width: 1.5,
          },
        },
        splitLine: {
          lineStyle: {
            color: "#e2e8f0",
          },
        },
      },
      yAxis: {
        min: -100,
        max: 100,
        name: "",
        axisTick: {
          show: false,
        },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 10,
        },
        axisLine: {
          lineStyle: {
            color: "#cbd5e1",
            width: 1.5,
          },
        },
        splitLine: {
          lineStyle: {
            color: "#e2e8f0",
          },
        },
      },
      series: [
        {
          type: "scatter",
          symbol: "rect",
          cursor: "pointer",
          symbolSize: (value) => {
            if (!Array.isArray(value)) {
              return [24, 16];
            }

            return [Number(value[2]) || 24, Number(value[3]) || 16];
          },
          data: displayPoints.map((point) => {
            const fontSize = pointFontSize(point);
            const labelColor = pointTextColor(point.quadrant, selectedSymbol, point.symbol);

            return {
            name: point.symbol,
            value: [point.x_score, point.y_score, pointHitBoxWidth(point, fontSize), pointHitBoxHeight(fontSize)],
            payload: point,
            label: {
              show: true,
              position: "inside",
              formatter: point.symbol,
              color: labelColor,
              fontSize,
              fontFamily: "'Noto Sans SC', 'Inter', sans-serif",
              fontWeight: selectedSymbol === point.symbol ? 700 : point.highlight ? 700 : 600,
              textBorderColor: "rgba(255,255,255,0.96)",
              textBorderWidth: 3,
            },
            itemStyle: {
              color: "rgba(255,255,255,0.001)",
              borderColor: "rgba(255,255,255,0)",
              borderWidth: 0,
            },
            emphasis: {
              label: {
                color: pointTextColor(point.quadrant, "", ""),
                fontWeight: 700,
              },
              itemStyle: {
                color: "rgba(255,255,255,0.001)",
              },
            },
          };
          }),
          emphasis: {
            scale: false,
          },
          markLine: {
            symbol: "none",
            lineStyle: {
              color: "#cbd5e1",
              opacity: 1,
              width: 1.5,
            },
            data: [{ xAxis: 0 }, { yAxis: 0 }],
          },
          markArea: {
            silent: true,
            data: [
              [
                { xAxis: -100, yAxis: 0, itemStyle: { color: "rgba(239, 68, 68, 0.038)" } },
                { xAxis: 0, yAxis: 100 },
              ],
              [
                { xAxis: 0, yAxis: 0, itemStyle: { color: "rgba(34, 197, 94, 0.045)" } },
                { xAxis: 100, yAxis: 100 },
              ],
              [
                { xAxis: -100, yAxis: -100, itemStyle: { color: "rgba(245, 158, 11, 0.032)" } },
                { xAxis: 0, yAxis: 0 },
              ],
              [
                { xAxis: 0, yAxis: -100, itemStyle: { color: "rgba(14, 165, 233, 0.032)" } },
                { xAxis: 100, yAxis: 0 },
              ],
            ],
          },
        },
      ],
    };

    chartRef.current.setOption(option);
  }, [points, selectedSymbol]);

  return (
    <section className="quadrant-chart">

      <div className="quadrant-chart__surface">
        <div className="quadrant-chart__axis-hint quadrant-chart__axis-hint--left">← 偏空</div>
        <div className="quadrant-chart__axis-hint quadrant-chart__axis-hint--right">偏多 </div>
        <div className="quadrant-chart__axis-hint quadrant-chart__axis-hint--top">↑ 买波</div>
        <div className="quadrant-chart__axis-hint quadrant-chart__axis-hint--bottom">↓ 卖波</div>

        <div ref={containerRef} className="quadrant-chart__canvas" />
      </div>
    </section>
  );
}


function pointColor(quadrant: string): string {
  if (quadrant === "bullish_expansion") {
    return "#22c55e";
  }
  if (quadrant === "bullish_compression") {
    return "#0ea5e9";
  }
  if (quadrant === "bearish_expansion") {
    return "#ef4444";
  }
  if (quadrant === "bearish_compression") {
    return "#f59e0b";
  }
  return "#94a3b8";
}


const QUADRANT_LEGEND_ITEMS = [
  { label: "看涨·买波", color: "#22c55e" },
  { label: "看涨·卖波", color: "#0ea5e9" },
  { label: "看跌·买波", color: "#ef4444" },
  { label: "看跌·卖波", color: "#f59e0b" },
  { label: "中性", color: "#94a3b8" },
];


function tooltipRow(label: string, value: string): string {
  return `
    <div style="display:flex; justify-content:space-between; gap:18px; margin-top:3px;">
      <span style="color:#94a3b8; font-size:11px;">${label}</span>
      <span style="font-family:'JetBrains Mono',monospace; font-weight:600; color:#1e293b;">${value}</span>
    </div>
  `;
}


function formatScore(value: number | null): string {
  if (value === null) {
    return "—";
  }

  return value.toFixed(1);
}


function formatCanvasQuadrantLabel(quadrant: string): string {
  const labels: Record<string, string> = {
    bullish_expansion: "看涨 · 买波",
    bullish_compression: "看涨 · 卖波",
    bearish_expansion: "看跌 · 买波",
    bearish_compression: "看跌 · 卖波",
    neutral: "中性",
  };

  return labels[quadrant] ?? formatQuadrantLabel(quadrant);
}


function pointFontSize(point: ChartPoint): number {
  return Math.max(13, Math.min(18, 10 + point.bubble_size * 0.08));
}


function pointHitBoxWidth(point: ChartPoint, fontSize: number): number {
  return Math.max(24, point.symbol.length * fontSize * 0.68 + 8);
}


function pointHitBoxHeight(fontSize: number): number {
  return fontSize + 8;
}


function pointTextColor(quadrant: string, selectedSymbol: string, symbol: string): string {
  const color = pointColor(quadrant);
  if (selectedSymbol && selectedSymbol !== symbol) {
    return withAlpha(color, 0.38);
  }

  return color;
}


function withAlpha(color: string, alpha: number): string {
  if (!color.startsWith("#")) {
    return color;
  }

  const hex = color.slice(1);
  const normalized = hex.length === 3
    ? hex.split("").map((char) => char + char).join("")
    : hex;

  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}


function sortPointsForCanvas(points: ChartPoint[], selectedSymbol: string): ChartPoint[] {
  return [...points].sort((left, right) => {
    if (left.symbol === selectedSymbol) {
      return 1;
    }
    if (right.symbol === selectedSymbol) {
      return -1;
    }
    if (left.quadrant === "neutral" && right.quadrant !== "neutral") {
      return -1;
    }
    if (right.quadrant === "neutral" && left.quadrant !== "neutral") {
      return 1;
    }

    return left.bubble_size - right.bubble_size;
  });
}
