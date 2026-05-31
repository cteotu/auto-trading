import React, { useState, useEffect, useRef, useMemo } from "react";
import * as echarts from "echarts";
import { api } from "../api";
import type { FrontendMarket, MarketTickData } from "../api";

const PAGE_SIZE = 10;

interface Props {
  markets: FrontendMarket[];
}

export default function MarketDataPage({ markets }: Props) {
  const [selected, setSelected] = useState(0);
  const [page, setPage] = useState(1);
  const [tickData, setTickData] = useState<MarketTickData | null>(null);
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  const totalPages = Math.ceil(markets.length / PAGE_SIZE);
  const pageData = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return markets.slice(start, start + PAGE_SIZE);
  }, [markets, page]);

  const market = markets[selected];

  // Fetch real tick data when market changes
  useEffect(() => {
    if (!market?.slug) return;
    setLoading(true);
    setTickData(null);
    api.marketTickData(market.slug).then((data) => {
      setTickData(data);
      setLoading(false);
    });
  }, [market?.slug]);

  // Render chart
  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, "dark");
    }
    const chart = chartInstance.current;

    if (!tickData || !tickData.ticks.length) {
      chart.setOption({
        backgroundColor: "transparent",
        title: { text: "暂无数据", left: "center", top: "center", textStyle: { color: "#6b7a9e", fontSize: 14 } },
        series: [],
      });
      return;
    }

    const openPrice = tickData.open_price;
    const priceData: [number, number | null][] = [];
    const upData: [number, number | null][] = [];
    const downData: [number, number | null][] = [];
    const gapData: [number, number | null][] = [];
    const volumeData: [number, number][] = [];

    tickData.ticks.forEach((t) => {
      priceData.push([t.ts * 1000, t.price]);
      upData.push([t.ts * 1000, t.up_prob]);
      downData.push([t.ts * 1000, t.down_prob]);
      gapData.push([t.ts * 1000, t.gap]);
      volumeData.push([t.ts * 1000, t.volume]);
    });

    chart.setOption({
      backgroundColor: "transparent",
      animation: false,
      color: ["#ff9b54", "#2f8cff", "#2ac769", "#ff4d4f", "#f59e0b"],
      legend: { textStyle: { color: "#9aa7b7" }, top: 0 },
      grid: { left: 58, right: 58, top: 48, bottom: 64 },
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
      dataZoom: [
        { type: "inside", xAxisIndex: [0] },
        { type: "slider", xAxisIndex: [0], bottom: 18, height: 22 },
      ],
      xAxis: { type: "time", axisLabel: { color: "#8797aa" }, splitLine: { lineStyle: { color: "#1f2b38" } } },
      yAxis: [
        { type: "value", name: "BTC", scale: true, axisLabel: { color: "#8797aa" }, splitLine: { lineStyle: { color: "#1f2b38" } } },
        { type: "value", name: "概率", min: 0, max: 1, axisLabel: { color: "#8797aa" }, splitLine: { show: false } },
        { type: "value", name: "价差", scale: true, axisLabel: { color: "#8797aa" }, splitLine: { show: false } },
        { type: "value", name: "成交量", scale: true, axisLabel: { color: "#8797aa" }, splitLine: { show: false } },
      ],
      series: [
        { name: "BTC价格", type: "line", yAxisIndex: 0, showSymbol: false, data: priceData },
        { name: "Up概率", type: "line", yAxisIndex: 1, showSymbol: false, data: upData },
        { name: "Down概率", type: "line", yAxisIndex: 1, showSymbol: false, data: downData },
        { name: "价差", type: "line", yAxisIndex: 2, showSymbol: false, data: gapData, lineStyle: { type: "dashed" } },
        { name: "成交量", type: "bar", yAxisIndex: 3, data: volumeData, barWidth: 2, itemStyle: { opacity: 0.5 } },
      ],
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
      chartInstance.current = null;
    };
  }, [tickData]);

  const rowClass = (status: string) => {
    if (status === "won") return "row-won";
    if (status === "lost") return "row-lost";
    return "";
  };

  if (!markets.length) {
    return <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>加载中...</div>;
  }

  return (
    <div style={{ display: "flex", gap: 10, height: "100%" }}>
      <div className="card" style={{ width: 340, display: "flex", flexDirection: "column" }}>
        <div className="card-header">
          <div className="card-title">市场列表</div>
          <span style={{ fontSize: 10, color: "var(--muted)" }}>{markets.length}条</span>
        </div>
        <div className="card-body" style={{ padding: 0, flex: 1, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>结果</th>
                <th>价差</th>
                <th>标记</th>
              </tr>
            </thead>
            <tbody>
              {pageData.map((m, i) => {
                const idx = (page - 1) * PAGE_SIZE + i;
                return (
                  <tr key={m.slug} className={idx === selected ? "row-selected" : ""}
                    style={{ cursor: "pointer" }} onClick={() => setSelected(idx)}>
                    <td style={{ fontSize: 11 }}>{m.market_time}</td>
                    <td>{m.winner !== "--" ? <span className={`badge ${m.winner === "Up" ? "up" : "down"}`}>{m.winner}</span> : <span style={{ color: "var(--muted)" }}>--</span>}</td>
                    <td style={{ fontFamily: "JetBrains Mono", fontSize: 11 }} className={(m.final_gap ?? 0) >= 0 ? "good" : "bad"}>
                      {m.final_gap == null ? <span style={{ color: "var(--muted)" }}>待确认</span> : `${m.final_gap >= 0 ? "+" : ""}${m.final_gap.toFixed(2)}`}
                    </td>
                    <td>
                      {m.reversal && <span className="badge" style={{ color: "var(--warn)", borderColor: "rgba(245,158,11,.3)", background: "rgba(245,158,11,.08)" }}>反转</span>}
                      {m.has_trade && <span className={`badge ${m.trade_status === "lost" ? "lost" : "won"}`}>交易</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <button className="page-btn" onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}>‹</button>
          <span style={{ fontSize: 10, color: "var(--muted)", margin: "0 8px" }}>{page}/{totalPages}</span>
          <button className="page-btn" onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}>›</button>
        </div>
      </div>
      <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <div className="card-header">
          <div className="card-title">市场回放 — {market?.slug || "--"}</div>
          {loading && <span style={{ fontSize: 10, color: "var(--muted)" }}>加载中...</span>}
        </div>
        <div className="card-body" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
            <div className="param"><div className="k">开盘价</div><div className="v">{tickData?.open_price ? `$${tickData.open_price.toFixed(2)}` : "待确认"}</div></div>
            <div className="param"><div className="k">结算价</div><div className="v">{tickData?.final_price ? `$${tickData.final_price.toFixed(2)}` : "--"}</div></div>
            <div className="param"><div className="k">结算差</div><div className="v">{tickData?.final_price && tickData?.open_price ? (tickData.final_price - tickData.open_price).toFixed(2) : "--"}</div></div>
            <div className="param"><div className="k">数据点</div><div className="v">{tickData?.ticks?.length ?? 0}</div></div>
            <div className="param"><div className="k">价格/盘口</div><div className="v">{tickData?.data_points ? `${tickData.data_points.price}/${Math.max(tickData.data_points.orderbook_up, tickData.data_points.orderbook_down)}` : "--"}</div></div>
          </div>
          <div ref={chartRef} style={{ flex: 1, minHeight: 300 }} />
        </div>
      </div>
    </div>
  );
}
