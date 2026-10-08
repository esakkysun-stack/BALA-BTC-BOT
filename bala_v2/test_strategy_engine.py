import unittest
from strategy_engine import BALAConfig, MarketFeatures, RiskState, evaluate_signal

class TestBalaV2(unittest.TestCase):
    def base(self):
        return MarketFeatures(
            trend_15m=1, orb_15m=1, liquidity_sweep=1, bos_choch=1,
            displacement_5m=1, fvg_ob_retest=1, vwap=1, frvp=0,
            volume_rvol=1, premium_zone=0,
            planned_entry=100.0, planned_sl=90.0, planned_tp=120.0
        )

    def test_7_of_10_approves(self):
        r = evaluate_signal(self.base(), RiskState())
        self.assertTrue(r["approved"])
        self.assertEqual(r["action"], "LONG")
        self.assertGreaterEqual(r["score"], 7)

    def test_below_7_rejects(self):
        f = self.base()
        f.volume_rvol = 0
        f.vwap = 0
        r = evaluate_signal(f, RiskState())
        self.assertFalse(r["approved"])
        self.assertEqual(r["action"], "NO_TRADE")

    def test_rr_rejects(self):
        f = self.base()
        f.planned_tp = 110.0
        r = evaluate_signal(f, RiskState())
        self.assertFalse(r["approved"])

    def test_daily_loss_rejects(self):
        r = evaluate_signal(self.base(), RiskState(daily_pnl_r=-2.0))
        self.assertFalse(r["approved"])

    def test_conflict_rejects(self):
        f = self.base()
        f.hard_conflict = True
        r = evaluate_signal(f, RiskState())
        self.assertFalse(r["approved"])

if __name__ == "__main__":
    unittest.main()
