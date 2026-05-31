import React from "react";

interface Props {
  summary?: {
    total?: number;
    won?: number;
    lost?: number;
    skipped?: number;
    win_rate?: number;
    total_pnl?: number;
    total_amount?: number;
    sim_bankroll?: number;
    live_bankroll?: number;
    sim_win_rate?: number;
    live_win_rate?: number;
    daily_summary?: Array<{
      date: string;
      trades: number;
      pnl: number;
      wins: number;
      losses: number;
      skipped: number;
      volume: number;
    }>;
  } | null;
  fundTrend?: {
    data: Array<{ time: string; bankroll: number; pnl: number; slug: string }>;
    initial: number;
  };
  marketStats?: {
    total_expected: number;
    total_actual: number;
    total_missing: number;
    today_expected: number;
    today_actual: number;
    today_missing: number;
  } | null;
}

export default function KPIRow({ summary, fundTrend, marketStats }: Props) {
  const s = summary || {};
  const simBankroll = s.sim_bankroll ?? (s as any).stats_sim_bankroll ?? 0;
  const liveBankroll = s.live_bankroll ?? (s as any).stats_live_bankroll ?? 0;
  const simReturn = simBankroll > 0 ? ((simBankroll - 1) * 100).toFixed(1) : "0";
  const today = s.daily_summary?.[0];
  const todayPnl = today?.pnl ?? 0;
  const todayWins = today?.wins ?? 0;
  const todayLosses = today?.losses ?? 0;
  const todayTrades = today?.trades ?? 0;
  const todaySkipped = today?.skipped ?? 0;
  const totalMarkets = marketStats?.total_actual ?? 0;
  const expectedMarkets = marketStats?.total_expected ?? 0;
  const missingMarkets = marketStats?.total_missing ?? 0;
  const todayMarkets = marketStats?.today_actual ?? 0;
  const todayExpected = marketStats?.today_expected ?? 0;
  const todayMissing = marketStats?.today_missing ?? 0;

  return (
    <div className="kpi-row">
      {/* 1. 总市场 */}
      <div className="kpi purple">
        <div className="label">总市场</div>
        <div className="value">{totalMarkets || "--"}</div>
        <div className="sub">预期 {expectedMarkets || "--"} · 缺失 {missingMarkets}</div>
      </div>
      {/* 2. 今日市场 */}
      <div className="kpi orange">
        <div className="label">今日市场</div>
        <div className="value">{todayMarkets || "--"}</div>
        <div className="sub">预期 {todayExpected || "--"} · 缺失 {todayMissing}</div>
      </div>
      {/* 3. 今日成交 */}
      <div className="kpi cyan">
        <div className="label">今日成交</div>
        <div className="split-row">
          <div className="split-item"><div className="sl">盈利</div><div className="sv good">{todayWins}</div></div>
          <div className="split-item"><div className="sl">亏损</div><div className="sv bad">{todayLosses}</div></div>
          <div className="split-item"><div className="sl">跳过</div><div className="sv" style={{ color: "var(--muted)" }}>{todaySkipped}</div></div>
        </div>
      </div>
      {/* 4. 今日盈亏 */}
      <div className="kpi green">
        <div className="label">今日盈亏</div>
        <div className="split-row">
          <div className="split-item">
            <div className="sl">模拟</div>
            <div className={`sv ${todayPnl >= 0 ? "good" : "bad"}`}>{todayPnl >= 0 ? "+" : ""}${todayPnl.toFixed(2)}</div>
            <div className="sl">{todayTrades}笔</div>
          </div>
          <div className="split-item">
            <div className="sl">实盘</div>
            <div className="sv">$0.00</div>
            <div className="sl">0笔</div>
          </div>
        </div>
      </div>
      {/* 5. 胜率 */}
      <div className="kpi blue">
        <div className="label">胜率</div>
        <div className="split-row">
          <div className="split-item"><div className="sl">总</div><div className="sv">{(s.win_rate ?? 0).toFixed(1)}%</div></div>
          <div className="split-item"><div className="sl">模拟</div><div className="sv">{(s.sim_win_rate ?? 0).toFixed(1)}%</div></div>
          <div className="split-item"><div className="sl">实盘</div><div className="sv">{(s.live_win_rate ?? 0).toFixed(1)}%</div></div>
        </div>
      </div>
      {/* 6. 资金概览 */}
      <div className="kpi purple">
        <div className="label">资金概览</div>
        <div className="split-row">
          <div className="split-item"><div className="sl">模拟</div><div className="sv">${simBankroll.toFixed(2)}</div></div>
          <div className="split-item"><div className="sl">实盘</div><div className="sv">${liveBankroll.toFixed(2)}</div></div>
        </div>
        <div className={`sub ${Number(simReturn) >= 0 ? "good" : "bad"}`}>模拟{Number(simReturn) >= 0 ? "+" : ""}{simReturn}%</div>
      </div>
      {/* 7. 总盈亏 */}
      <div className="kpi red">
        <div className="label">总盈亏</div>
        <div className="split-row">
          <div className="split-item"><div className="sl">总PnL</div><div className={`sv ${(s.total_pnl ?? 0) >= 0 ? "good" : "bad"}`}>{(s.total_pnl ?? 0) >= 0 ? "+" : ""}${(s.total_pnl ?? 0).toFixed(2)}</div></div>
          <div className="split-item"><div className="sl">总投入</div><div className="sv">${(s.total_amount ?? 0).toFixed(2)}</div></div>
        </div>
      </div>
    </div>
  );
}
