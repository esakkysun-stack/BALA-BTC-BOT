import unittest
from breaker_strategy import evaluate, paper_step


def candle(o, h, l, c):
    return {"open":o,"high":h,"low":l,"close":c,"volume":100}


class BreakerStrategyTests(unittest.TestCase):
    def test_neutral_without_confirmed_breakout(self):
        c15=[candle(100,110,90,105), candle(105,111,91,106)]
        c5=[candle(104,109,103,108), candle(108,109,102,107)]
        c1=[candle(100,102,99,101) for _ in range(5)]
        signal=evaluate(c15,c5,c1)
        self.assertEqual(signal["state"],"NEUTRAL")
        self.assertEqual(signal["side"],"WAIT")
        self.assertIsNone(signal["entry"])

    def test_requires_closed_candle_inputs(self):
        with self.assertRaises(ValueError):
            evaluate([],[],[])

    def test_paper_step_only_creates_virtual_position(self):
        state={"mode":"PAPER_ONLY","open_trade":None,"trades":[]}
        signal={"side":"BUY","entry":100.0,"stop":80.0,"target":122.0,"timestamp":1}
        result=paper_step(state,signal,100.0)
        self.assertEqual(result["mode"],"PAPER_ONLY")
        self.assertEqual(result["open_trade"]["entry"],100.0)
        self.assertEqual(result["trades"],[])


if __name__ == "__main__":
    unittest.main()
