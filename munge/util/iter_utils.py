from itertools import izip, islice, tee
from copy import copy

def each_pair(seq):
    '''Given an iterator (i0, i1, i2, ...), returns an iterator ((i0, i1), (i1, i2), ...).'''
    s1, s2 = tee(seq)
    return izip(s1, islice(s2, 1, None))