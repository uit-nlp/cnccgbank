# Chinese CCGbank conversion
# ==========================
# (c) 2008-2012 Daniel Tse <cncandc@gmail.com>
# University of Sydney

# Use of this software is governed by the attached "Chinese CCGbank converter Licence Agreement"
# supplied in the Chinese CCGbank conversion distribution. If the LICENCE file is missing, please
# notify the maintainer Daniel Tse <cncandc@gmail.com>.

from functools import update_wrapper, wraps

def cast_to(*types):
    '''A function decorator which takes a tuple of 1-arg constructor functions, modifying the decorated function
to cast each of its arguments with the corresponding constructor function before it is invoked. If the number of
formal arguments is fewer than the number of constructor functions, a RuntimeError is raised.

@cast_to(int, int)
def g(x, y):
    return x + y
    
g("2", "3") # => 5'''
    # TODO: The resulting function _f_ doesn't have the same arity as the original function
    def f(func):
        tl = len(types)
        def _f(*args, **kwargs):
            if tl != len(args): raise RuntimeError("%d args expected, %d args received" % (tl, len(args)))
            return func(*(
                type(arg) if type is not None else arg
                for (type, arg) in zip(types, args)), **kwargs)
        return update_wrapper(_f, func)
    return f
    
import os
def filelike(f):
    '''Constructor which returns a file instance given a filename. If the given argument does not correspond to a file,
an exception is raised.'''
    if isinstance(f, basestring) and os.path.exists(f) and os.path.isfile(f):
        return file(f, 'r+')
    raise IOError('Argument %s is not a file.' % f)
    
def comma_list(f):
    return f.split(',')

def threshold(f):
    v = float(f)
    if 0.0 <= v <= 1.0:
        return v
    else:
        raise TypeError('Threshold must be in the range [0, 1].')

def enum(**map):
    def _enum(f):
        return map.get(f, None)
    return _enum
    
def is_iterable(s):
    return hasattr(s, '__iter__')
def seq_or_splat(f):
    '''Given function _f_, returns _f*_, defined as:
f*([x, y, z, ...]) = f(x, y, z, ...) when x is a sequence
f* = f otherwise
'''
    def _f(*args):
        if len(args) == 1:
            if is_iterable(args[0]):
                return f(*list(args[0]))
        else:
            return f(*args)
    return _f

# From http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize    
class memoised(object):
   """Decorator that caches a function's return value each time it is called.
   If called later with the same arguments, the cached value is returned, and
   not re-evaluated.
   """
   def __init__(self, func):
      self.func = func
      self.cache = {}
   def __call__(self, *args):
      try:
         return self.cache[args]
      except KeyError:
         self.cache[args] = value = self.func(*args)
         return value
      except TypeError:
         # uncachable -- for instance, passing a list as an argument.
         # Better to not cache than to blow up entirely.
         return self.func(*args)
   def __repr__(self):
      """Return the function's docstring."""
      return self.func.__doc__

def predicated(f):
    '''Functions decorated with _predicated_ optionally accept a keyword
argument _when_, which acts as a guard on the function call. If _when_
is not provided, the function call occurs unconditionally.'''
    @wraps(f)
    def _f(*args, **kwargs):
        when = kwargs.pop('when', True)
        if not when: return
        return f(*args, **kwargs)
    return _f
    
if __name__ == '__main__':
    @cast_to(int, int)
    def g(x,y):
        print x+y
        
    g("3", "4")
    g(3.5, "4")
    #g(3,4,5)
    
    @cast_to(enum(A=1, B=2))
    def h(x):
        print x

    h('A')
    h('B')
    h('C')
