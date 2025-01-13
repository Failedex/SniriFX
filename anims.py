
# check out https://easings.net for more animation functions

import math

ease_out_expo = lambda t: 1 if t == 1 else 1 - math.pow(2, -10*t)
ease_out_quad = lambda t: 1 - (1-t)*(1-t)

def ease_out_bounce(x): 
    n1 = 7.5625
    d1 = 2.75

    if x < 1 / d1:
        return n1 * x * x;
    elif x < 2 / d1:
        x -= 1.5/d1
        return n1 * x * x + 0.75
    elif x < 2.5 / d1:
        x -= 2.25 / d1
        return n1 * x * x + 0.9375
    else:
        x -= 2.625 / d1
        return n1 * x * x + 0.984375

def ease_in_out_bounce(t): 
    if t < 0.5:
        return (1-ease_out_bounce(1-2*t)) / 2
    else:
        return (1+ease_out_bounce(2*t-1)) / 2

def ease_out_elastic(t):
    c4 = (2*math.pi) / 3 
    return 0 if t == 0 else 1 if t == 1 else math.pow(2, -10*t) * math.sin((10*t - 0.75) * c4) + 1

def ease_in_out_elastic(t): 
    c5 = (2*math.pi)/4.5

    if t == 0:
        return 0
    elif t == 1:
        return 1
    elif t < 0.5:
        return -(math.pow(2, 20*t - 10) * math.sin((20*t - 11.125) * c5)) / 2
    else:
        return (math.pow(2, -20*t + 10) * math.sin((20*t - 11.125) * c5)) / 2 + 1

def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1

    return 1+c3*math.pow(t-1, 3) + c1*math.pow(t-1, 2)

def ease_in_out_back(t): 
    c1 = 1.70158
    c2 = c1 * 1.525

    if t < 0.5: 
        return (math.pow(2*t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
    else:
        return (math.pow(2*t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2

def linear(t): 
    return t
