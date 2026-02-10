import datetime
import numpy as np

def SineTestFunction(amplitude=1.0, y_offset=0.0, period=1.0):
    t = datetime.datetime.now()
    return amplitude * np.sin(2 * np.pi * t.timestamp() / period) + y_offset