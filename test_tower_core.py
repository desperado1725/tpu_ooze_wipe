import unittest
from tpu_ooze_wipe import full_prime_bounds
class CoreTests(unittest.TestCase):
 def shape(self,vertical):
  lines=['; prime_tower_rib_wall = 1','G90','M83','; CHANGE_LAYER','; FEATURE: Prime tower','G1 X0 Y0 Z1']
  for n in (10,15,20):
   a,b=((n,30),(n,50)) if vertical else ((30,n),(50,n))
   lines += [f'G1 X{a[0]} Y{a[1]}',f'G1 X{b[0]} Y{b[1]} E1']
  # A protruding rib must not enlarge the wipe core.
  lines+=['G1 X60 Y60','G1 X61 Y61 E1']
  return '\n'.join(lines)
 def test_horizontal(self):self.assertEqual(full_prime_bounds(self.shape(False))[1],[30,10,50,20])
 def test_vertical(self):self.assertEqual(full_prime_bounds(self.shape(True))[1],[10,30,20,50])
 def test_unknown_rejected(self):
  with self.assertRaises(ValueError):full_prime_bounds(self.shape(True).replace('G1 X20 Y50 E1','G1 X20 Y50'))
if __name__=='__main__':unittest.main()
