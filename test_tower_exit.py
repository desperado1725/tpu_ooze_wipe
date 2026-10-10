import unittest,re
from tpu_ooze_wipe import clear_tower_lifts,transform_wipes
SAMPLE = '; printer_model = Bambu Lab H2D\n; enable_prime_tower = 1\n; print_sequence = by layer\n; filament_type = PLA;TPU\n; filament_map = 1,2\n; physical_extruder_map = 1,0\n; enable_arc_fitting = 0\n; printable_area = 0x0,350x0,350x320,0x320\n; extruder_printable_area = 0x0,325x0,325x320,0x320#25x0,350x0,350x320,25x320\n; bed_exclude_area = \n; printable_height = 325\n; filament_diameter = 1.75,1.75\n; filament_flow_ratio = 0.98,0.79695\n; nozzle_temperature = 220,242\n; filament_max_volumetric_speed = 12,8\n; nozzle_diameter = 0.6,0.6\n; travel_speed = 1000,1000\n; travel_acceleration = 10000,10000\n; initial_layer_travel_acceleration = 6000,6000\n; initial_layer_speed = 50,50\n; retraction_length = 1.4,1.4\n; retraction_speed = 30,30\n; deretraction_speed = 30,20\nG90\nM83\nM220 S100\nT1 H-1\nM104 T0 S242 N0\nM204 S5000\n; CHANGE_LAYER\n; Z_HEIGHT: 0.3\n; LAYER_HEIGHT: 0.3\n; LINE_WIDTH: 0.6\nT0\nG1 X90 Y100 Z0.3 F6000\n; FEATURE: Support\nG1 X91 Y100 E1 F1200\n; FEATURE: Prime tower\nG1 X92 Y100 E1 F1200\nT1 H-1\nG1 X100 Y100 Z0.3 F6000\n; FEATURE: Support\nG1 X110 Y100 E1 F1200\nM400\nM104 T0 S130 N0 ;Multi extruder pre cooling\nG1 E-2 F2700\nM620 S0A H-1\nT0 H-1\n'
BASE=SAMPLE.replace('G1 X92 Y100 E1 F1200','G1 X110 Y100 E1 F1200\nG1 X110 Y120 E1\nG1 X90 Y120 E1\nG1 X90 Y100 E1')
class TowerExitTests(unittest.TestCase):
 def test_linear_and_spiral_lifts(self):
  for command in ('G1 Z2 F1200','G3 Z2 I.6 J0 P1 F5400','G1 X130 Y110 Z2 F1200'):
   source=BASE+'G1 X100 Y110 Z.3 F6000\n'+command+'\n'
   out,r=clear_tower_lifts(source)
   self.assertGreater(r['changed'],0)
   e=r['events'][-1];x,y=e['lift_xy'];b=r['envelope']
   self.assertTrue(x<=b[0]-3 or x>=b[2]+3 or y<=b[1]-3 or y>=b[3]+3)
   self.assertEqual(e['to'][2],2)
   self.assertEqual(clear_tower_lifts(out)[0],out)
 def test_extruding_lift_rejected(self):
  with self.assertRaises(ValueError):clear_tower_lifts(BASE+'G1 X100 Y110 Z.3\n; FEATURE: Support\nG1 Z2 E.1\n')
 def test_material_wipe_durations(self):
  out,r=transform_wipes(BASE)
  self.assertEqual([e['nominal_seconds'] for e in r['events']],[2,15])
  self.assertEqual([e['material'] for e in r['events']],['PLA','TPU'])
if __name__=='__main__':unittest.main()
