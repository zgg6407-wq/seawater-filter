"""Offline CLI; external networking only in the explicitly selected API server."""
import hashlib
import argparse
import json
import sys
from .data import synthetic_bars, read_csv
from .lines import discover_lines, mature_labels
from .learning import train_quality_model
from .backtest import run_backtest, PublicBaseline, LineBounceStrategy
from .reporting import write_report

def run_research(bars, output, horizon=24, evidence_source="SYNTHETIC", split_fraction=.65):
    if not .5 <= split_fraction <= .8:
        raise ValueError("Split fraction must be between .5 and .8")
    lines=discover_lines(bars);records=mature_labels(bars,lines,horizon=horizon)
    split=int(len(bars)*split_fraction)
    model=train_quality_model(records,split)
    strategy=LineBounceStrategy(line_lifetime=horizon)
    dataset_id=hashlib.sha256(bars.to_csv(index=False).encode()).hexdigest()
    report={"schema_version":1,"framework_version":"0.1.0","feature_version":"public-pivot-pair-v1",
        "dataset_id":dataset_id,"model":"standard_scaler+logistic_regression / ridge",
        "policy":{"split_fraction":split_fraction,"pivot_left":3,"pivot_right":3,"max_pairs":3,"tolerance_atr":.5},"evidence_source":evidence_source,"bars":len(bars),
        "split_index":split,"label_horizon":horizon,"candidate_count":len(lines),"mature_count":len(records),
        "model":model.evaluate(records),"backtests":{
            "baseline":run_backtest(bars,lines,PublicBaseline(),split,strategy),
            "ml":run_backtest(bars,lines,model,split,strategy)}}
    report['holdout_predictions']=[{"line_id":r['line'].line_id,"discovered_at":r['feature_at'],
        "survival_score":model.score(r['line']),"capped_duration_estimate":model.duration_estimate(r['line']),
        "label_available_at":r['label_available_at']} for r in records if r['feature_at']>=split]
    write_report(output,report,bars,lines)
    return report

def main(argv=None):
    parser=argparse.ArgumentParser(description="Public market-structure research; no private classifier or trading")
    sub=parser.add_subparsers(dest="command",required=True)
    demo=sub.add_parser("demo",help="Run deterministic synthetic offline demonstration")
    demo.add_argument("--bars",type=int,default=1200);demo.add_argument("--seed",type=int,default=7)
    demo.add_argument("--output",default="outputs/demo")
    csv=sub.add_parser("research",help="Research your own CLOSED-bar CSV")
    csv.add_argument("--csv",required=True);csv.add_argument("--output",default="outputs/research")
    csv.add_argument("--horizon",type=int,default=24)
    serve=sub.add_parser("serve",help="Loopback authenticated research tools; never executes tasks or orders")
    serve.add_argument("--port",type=int,default=8765);serve.add_argument("--output",default="outputs/demo")
    args=parser.parse_args(argv)
    try:
        if args.command=="serve":
            from .api import serve
            serve(args.output,args.port)
            return 0
        bars=synthetic_bars(args.bars,args.seed) if args.command=="demo" else read_csv(args.csv)
        report=run_research(bars,args.output,horizon=getattr(args,"horizon",24),
            evidence_source="SYNTHETIC" if args.command=="demo" else "LOCAL_CSV_UNVERIFIED")
        print(json.dumps({"output":args.output,"evidence_source":report['evidence_source'],
            "training_samples":report['model']['train_count'],"holdout_samples":report['model']['holdout_count'],
            "baseline_trades":report['backtests']['baseline']['trade_count'],"ml_trades":report['backtests']['ml']['trade_count']}))
        return 0
    except ValueError as error:
        print(str(error),file=sys.stderr);return 2

if __name__=="__main__":
    raise SystemExit(main())
