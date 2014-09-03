import unittest
import numpy as np

from pele.potentials.heisenberg_spin import HeisenbergModel, make2dVector
from pele.potentials.xyspin import XYModel
from pele.potentials.heisenberg_spin_RA import HeisenbergModelRA

import _base_test

L = 4
coords = np.array([-2.20602929,  0.8625322 ,  1.44530737,  2.77600782, -2.6598941 ,
                    1.77100915, -0.06118008,  2.07398157, -0.52231567,  2.4544477 ,
                    0.85634936,  2.54285063,  0.65450804,  0.94843345, -2.71288882,
                    0.89978525, -0.62800248,  2.60595678, -2.42511571,  1.19724716,
                   -0.40636352,  2.7624946 ,  0.72522156,  0.83734704, -1.70115008,
                    2.07229916, -2.63865479,  2.83741277,  2.74738793,  1.87942836,
                   -2.74022047,  0.75243584])

fields = np.array([[-0.18602174, -0.9495507 ,  0.25248638],
                   [-0.87817801,  0.31645698,  0.35868978],
                   [ 0.94146577,  0.07195891, -0.32933891],
                   [-0.26054072, -0.80618789,  0.53120581],
                   [-0.037894  , -0.48271189,  0.87495901],
                   [ 0.91122468,  0.27396389,  0.30759286],
                   [-0.07055836,  0.51596333,  0.85369981],
                   [-0.40480976, -0.88468861,  0.23120366],
                   [-0.88979914, -0.43690809,  0.1317908 ],
                   [ 0.13500686, -0.82911172,  0.54253747],
                   [-0.63057235,  0.4257786 , -0.64891532],
                   [ 0.70369694,  0.19205106, -0.68405191],
                   [-0.42986668,  0.03773809, -0.90210336],
                   [-0.23677211, -0.29785247,  0.92478261],
                   [ 0.835238  ,  0.52670602, -0.15798183],
                   [ 0.90167764, -0.00222097,  0.43240317]])

phases = {((1, 2), (1, 3)): 1.0, ((2, 0), (1, 0)): 1.0, ((0, 2), (0, 3)): 1.0, 
          ((1, 3), (0, 3)): 1.0, ((1, 2), (2, 2)): 1.0, ((2, 1), (2, 0)): 0.0, 
          ((2, 1), (2, 2)): 1.0, ((3, 0), (3, 1)): 1.0, ((3, 0), (2, 0)): 1.0, 
          ((3, 2), (3, 3)): 1.0, ((0, 1), (1, 1)): 0.0, ((2, 1), (1, 1)): 0.0, 
          ((2, 3), (2, 2)): 1.0, ((1, 0), (1, 1)): 1.0, ((3, 2), (3, 1)): 1.0, 
          ((3, 2), (2, 2)): 0.0, ((3, 3), (2, 3)): 1.0, ((0, 0), (1, 0)): 1.0, 
          ((0, 1), (0, 0)): 1.0, ((1, 2), (0, 2)): 1.0, ((1, 3), (2, 3)): 0.0, 
          ((0, 1), (0, 2)): 0.0, ((3, 1), (2, 1)): 0.0, ((1, 2), (1, 1)): 0.0}


class TestHeisenbergModel(_base_test._TestConfiguration):
    def setUp(self):
        self.pot = HeisenbergModel(dim=[L, L], field_disorder=0.)
        self.x0 = coords
        self.e0 = 1.74084024512

class TestHeisenbergModelDisorder(_base_test._TestConfiguration):
    def setUp(self):
        self.pot = HeisenbergModel(dim=[L, L], fields=fields)
        self.x0 = coords
        self.e0 = 1.7757123154210279

class TestXYModel(_base_test._TestConfiguration):
    def setUp(self):
        self.pot = XYModel(dim=[L, L], phi=0, periodic=False, phases=None)
        self.x0 = coords
        self.e0 = -4.284665254883342

class TestXYModelPeriodic(_base_test._TestConfiguration):
    def setUp(self):
        self.pot = XYModel(dim=[L, L], phi=0, periodic=True)
        self.x0 = coords
        self.e0 = -6.5951281600115115

class TestXYModelDisorder(_base_test._TestConfiguration):
    def setUp(self):
        self.pot = XYModel(dim=[L, L], phi=1., periodic=False, phases=phases)
        self.x0 = coords
        self.e0 = -3.3611543131815984

class TestHeisenbergModelRADisorder(_base_test._TestConfiguration):
    def setUp(self):
        self.pot = HeisenbergModelRA(dim=[L, L], fields=fields)
        self.x0 = coords
        self.e0 = -2.8950083960043336




if __name__ == "__main__":
    unittest.main()
    