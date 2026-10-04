import unittest
import numpy as np
import pandas as pd
from market_state_filter.data import synthetic_bars, validate_bars
from market_state_filter.lines import discover_lines, mature_labels, CandidateLine
from market_state_filter.learning import train_quality_model
from market_state_filter.backtest import run_backtest, PublicBaseline, LineBounceStrategy

class CausalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars=synthetic_bars();cls.lines=discover_lines(cls.bars)
        cls.records=mature_labels(cls.bars,cls.lines)

    def test_future_changes_cannot_rewrite_discovered_lines(self):
        prefix=discover_lines(self.bars.iloc[:600])
        expected=[l.record() for l in self.lines if l.discovered_at<600]
        self.assertEqual([l.record() for l in prefix],expected)
        changed=self.bars.copy()
        changed.loc[600:,'high']*=2;changed.loc[600:,'low']*=.5
        altered=discover_lines(changed)
        self.assertEqual(expected,[l.record() for l in altered if l.discovered_at<600])

    def test_pivots_available_only_after_right_window(self):
        self.assertTrue(self.lines)
        self.assertTrue(all(l.discovered_at==l.anchor2+3 for l in self.lines))

    def test_immature_samples_excluded(self):
        self.assertTrue(all(r['label_available_at']<len(self.bars) for r in self.records))
        eligible={r['line'].line_id for r in self.records}
        self.assertTrue(all(l.line_id not in eligible for l in self.lines if l.discovered_at+24>=len(self.bars)))

    def test_training_purges_overlap_and_refuses_retrospective_score(self):
        model=train_quality_model(self.records,780)
        self.assertLess(model.last_training_label_at,780)
        with self.assertRaises(ValueError):model.score(self.lines[0])
        self.assertTrue(all(0<=model.score(r['line'])<=1 for r in self.records if r['feature_at']>=780))

    def test_future_training_labels_do_not_change_fitted_predictions(self):
        model=train_quality_model(self.records,780)
        changed=[dict(r,survived_horizon=1-r['survived_horizon'],effective_bars=1) if r['label_available_at']>=780 else dict(r) for r in self.records]
        second=train_quality_model(changed,780)
        sample=next(r['line'] for r in self.records if r['feature_at']>=780)
        self.assertEqual(model.score(sample),second.score(sample))
        self.assertEqual(model.duration_estimate(sample),second.duration_estimate(sample))

    def test_invalid_data_rejected(self):
        frame=self.bars.copy();frame.loc[5,'timestamp']=frame.loc[4,'timestamp']
        with self.assertRaises(ValueError):validate_bars(frame)
        frame=self.bars.copy();frame=frame.drop(index=5)
        with self.assertRaises(ValueError):validate_bars(frame)
        frame=self.bars.copy();frame.loc[5,'low']=frame.loc[5,'high']+1
        with self.assertRaises(ValueError):validate_bars(frame)

class ExecutionTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame({'open':[100.]*10,'high':[101.]*10,'low':[99.]*10,'close':[100.]*10})

    def test_next_open_entry_and_costs(self):
        line=CandidateLine('example','support',0,1,90.,90.,3,1.,(0,1,2,0,1,0))
        class Once(LineBounceStrategy):
            def signal(self,bars,index,lines,scorer):
                return (1.,line,90.) if index==3 else None
        result=run_backtest(self.fixture(),[line],PublicBaseline(),0,Once(max_hold=1))
        trade=result['trades'][0]
        self.assertEqual(trade['signal_at'],3);self.assertEqual(trade['entry_at'],4)
        self.assertLess(trade['net_pnl'],0)
        self.assertAlmostEqual(result['final_cash'],10000+trade['net_pnl'])

    def test_intrabar_ambiguity_prefers_stop(self):
        bars=self.fixture();bars.loc[4,['high','low']]=[125.,85.]
        line=CandidateLine('example','support',0,1,90.,90.,3,1.,(0,1,2,0,1,0))
        class Once(LineBounceStrategy):
            def signal(self,bars,index,lines,scorer):return (1.,line,90.) if index==3 else None
        result=run_backtest(bars,[line],PublicBaseline(),0,Once(),fee=0,slippage=0)
        self.assertEqual(result['trades'][0]['reason'],'stop')
        self.assertEqual(result['trades'][0]['exit'],90.)

    def test_invalid_costs_rejected(self):
        with self.assertRaises(ValueError):run_backtest(self.fixture(),[],PublicBaseline(),0,fee=-1)

if __name__=='__main__':unittest.main()
