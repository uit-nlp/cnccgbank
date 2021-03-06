# Chinese CCGbank conversion
# ==========================
# (c) 2008-2012 Daniel Tse <cncandc@gmail.com>
# University of Sydney

# Use of this software is governed by the attached "Chinese CCGbank converter Licence Agreement"
# supplied in the Chinese CCGbank conversion distribution. If the LICENCE file is missing, please
# notify the maintainer Daniel Tse <cncandc@gmail.com>.
import operator

class CountDict(dict):
    '''Accessing a non-existent key in this dictionary will return the value zero.'''

    def __missing__(self, key):
        return 0
        
class PrefixSet(set):
    '''A set which implicitly contains all string prefixes of items added to it.'''
    def __contains__(self, item):
        return any(candidate.startswith(item) for candidate in self)

def sorted_by_value_desc(dict):
    '''Given a _dict_, returns its (key, value) pairs sorted in descending order.'''
    return sorted(dict.iteritems(), key=operator.itemgetter(1), reverse=True)

def smash_key_case(d):
    '''Given a dictionary _d_, lowercases its keys.'''
    return dict( (k.lower(), v) for (k, v) in d.iteritems() )
    
def update(dict, **kwargs):
    '''Chainable dict update.'''
    dict.update(**kwargs)
    return dict