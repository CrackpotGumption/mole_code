import random
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'python'))
from game import Game, Settings

class GameTest(unittest.TestCase):
    def setUp(self):
        self.commands=[]
        self.g=Game(self.commands.append, Settings(countdown_seconds=0), random.Random(1))
        self.g.initialize(); self.g.start(0); self.g.tick(0)
    def test_token_active_settle_and_single_score(self):
        i,t=self.g.active,self.g.token
        self.g.hit(i,t,.1); self.assertEqual(self.g.score,0)
        self.g.hit((i+1)%5,t,.3); self.assertEqual(self.g.score,0)
        self.g.hit(i,t,.3); self.assertEqual(self.g.score,1)
        self.assertNotEqual(i,self.g.active)
        self.g.hit(i,t,.4); self.assertEqual(self.g.score,1)
    def test_timeout_never_repeats(self):
        for now in range(1,25):
            old=self.g.active; self.g.tick(now)
            self.assertNotEqual(old,self.g.active)
        self.assertEqual(self.g.score,0)
    def test_round_deadline_chase_idle(self):
        self.g.hit(self.g.active,self.g.token,30)
        self.assertEqual(self.g.score,0)
        self.g.tick(30); self.assertEqual(self.g.state,'chase')
        self.assertIn('SAFE STOP',self.commands)
        self.g.tick(32); self.assertEqual(self.g.state,'idle')
        self.assertIsNone(self.g.active)
    def test_repeated_start_ignored(self):
        self.g.start(10); self.assertEqual(self.g.round_deadline,30)
    def test_flash_does_not_hold_next_target(self):
        old=self.g.active
        self.g.hit(old,self.g.token,.3)
        self.assertNotEqual(old,self.g.active)
        self.assertIn(f'MOLE {old} DOWN',self.commands)
        self.assertTrue(any(c.startswith('TARGET') for c in self.commands))
    def test_reinitialize_clears_scoring(self):
        self.g.initialize(); self.g.hit(0,1,2)
        self.assertEqual(self.g.state,'idle'); self.assertEqual(self.g.score,0)

if __name__=='__main__': unittest.main()
