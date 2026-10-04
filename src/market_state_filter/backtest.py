"""Long-only example plugin. Signals at close; fills next open; costs explicit."""
from dataclasses import dataclass
from typing import Protocol

class Scorer(Protocol):
    def score(self, line) -> float: ...

class PublicBaseline:
    def score(self, line):
        touch, breach = line.features[4:6]
        return max(0.0, min(1.0, .55+.5*touch-.75*breach))

@dataclass(frozen=True)
class LineBounceStrategy:
    threshold: float = .55
    reward_risk: float = 1.5
    max_hold: int = 24
    line_lifetime: int = 24

    def signal(self, bars, index, lines, scorer):
        row=bars.iloc[index]
        eligible=[]
        for line in lines:
            if line.side != "support" or not (line.discovered_at <= index < line.discovered_at+self.line_lifetime):
                continue
            level=line.value(index);band=.5*line.atr
            if row.low <= level+band and row.close > level and scorer.score(line) >= self.threshold:
                stop=level-band
                if stop > 0 and row.close > stop:
                    eligible.append((scorer.score(line),line,stop))
        return max(eligible,key=lambda x:(x[0],x[1].discovered_at)) if eligible else None

def run_backtest(bars, lines, scorer, start, strategy=None, fee=.0005, slippage=.0002, initial_cash=10000.0, allocation=.1):
    strategy=strategy or LineBounceStrategy()
    if not 0 < allocation <= 1 or fee < 0 or not 0 <= slippage < 1 or initial_cash <= 0:
        raise ValueError("Invalid cost/capital configuration")
    cash=float(initial_cash);position=None;pending=None;trades=[];equity=[]
    by_time={}
    for line in lines:
        if line.discovered_at >= start:
            by_time.setdefault(line.discovered_at,[]).append(line)
    active=[]
    def close_position(i, raw_price, reason):
        nonlocal cash,position
        price=raw_price*(1-slippage);proceeds=position["qty"]*price*(1-fee)
        pnl=proceeds-position["cost"];cash+=proceeds
        trades.append({"signal_at":position["signal_at"],"entry_at":position["entry_at"],"exit_at":i,
            "line_id":position["line_id"],"entry":position["entry"],"exit":price,"net_pnl":pnl,"reason":reason})
        position=None
    for i in range(start,len(bars)):
        row=bars.iloc[i];active.extend(by_time.get(i,[]))
        active=[l for l in active if i < l.discovered_at+strategy.line_lifetime]
        if pending is not None and position is None:
            _,line,stop=pending["signal"];entry=float(row.open)*(1+slippage)
            if entry > stop:
                budget=cash*allocation;qty=budget/(entry*(1+fee));cash-=budget
                position={"qty":qty,"cost":budget,"entry":entry,"stop":stop,
                    "target":entry+strategy.reward_risk*(entry-stop),"signal_at":pending["at"],
                    "entry_at":i,"line_id":line.line_id}
            pending=None
        if position is not None:
            if row.open <= position["stop"]:
                close_position(i,float(row.open),"gap_stop")
            elif row.low <= position["stop"]:
                close_position(i,position["stop"],"stop")  # conservative if stop and target both touched
            elif row.open >= position["target"]:
                close_position(i,float(row.open),"gap_target")
            elif row.high >= position["target"]:
                close_position(i,position["target"],"target")
            elif i-position["entry_at"] >= strategy.max_hold:
                close_position(i,float(row.close),"time_exit")
        active=[l for l in active if (row.close >= l.value(i)-.5*l.atr if l.side=="support" else row.close <= l.value(i)+.5*l.atr)]
        equity.append(cash+(position["qty"]*float(row.close)*(1-fee) if position else 0))
        if position is None and i < len(bars)-1:
            signal=strategy.signal(bars,i,active,scorer)
            if signal:pending={"signal":signal,"at":i}
    if position is not None:
        close_position(len(bars)-1,float(bars.close.iloc[-1]),"end_of_data")
        equity[-1]=cash
    peak=initial_cash;drawdown=0.0
    for value in equity:
        peak=max(peak,value);drawdown=max(drawdown,(peak-value)/peak)
    return {"net_return":cash/initial_cash-1,"final_cash":cash,"max_drawdown":drawdown,
        "trade_count":len(trades),"win_rate":sum(t["net_pnl"]>0 for t in trades)/len(trades) if trades else None,
        "trades":trades,"equity":equity,"fee_per_side":fee,"slippage_per_side":slippage,
        "allocation":allocation,"strategy":"support_bounce_long_only"}
