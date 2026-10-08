import unittest
from integration_bridge import build_decision, should_place_paper_order, order_payload

class TestIntegrationBridge(unittest.TestCase):
    def features(self):
        return dict(trend_15m=1,orb_15m=1,liquidity_sweep=1,bos_choch=1,
                    displacement_5m=1,fvg_ob_retest=1,vwap=1,frvp=0,
                    volume_rvol=1,premium_zone=0,hard_conflict=False,chop=False,
                    high_impact_news=False,duplicate_signal=False,
                    planned_entry=100,planned_sl=90,planned_tp=120)
    def test_paper_order_allowed(self):
        d=build_decision(self.features(),dict(), "LONG")
        self.assertTrue(should_place_paper_order(d))
        self.assertEqual(order_payload(d)["action"],"LONG")
    def test_no_trade_is_blocked(self):
        f=self.features(); f["trend_15m"]=0; f["orb_15m"]=0; f["vwap"]=0
        d=build_decision(f,dict(),"LONG")
        self.assertFalse(should_place_paper_order(d))
        self.assertEqual(order_payload(d)["action"],"NO_TRADE")
if __name__=="__main__":
    unittest.main()
