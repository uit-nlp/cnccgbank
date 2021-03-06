# Chinese CCGbank conversion
# ==========================
# (c) 2008-2012 Daniel Tse <cncandc@gmail.com>
# University of Sydney

# Use of this software is governed by the attached "Chinese CCGbank converter Licence Agreement"
# supplied in the Chinese CCGbank conversion distribution. If the LICENCE file is missing, please
# notify the maintainer Daniel Tse <cncandc@gmail.com>.

from munge.proc.filter import Filter
from munge.cats.trace import analyse
from munge.trees.traverse import *
from munge.proc.tgrep.tgrep import tgrep, initialise, find_all

from collections import defaultdict

from munge.util.list_utils import *
from apps.cn.tag import is_np_internal_structure, ValidNPInternalTags
from itertools import imap
from apps.identify_pos import *

initialise()

def next_leaf(cur_leaf):
    while cur_leaf.parent and cur_leaf.parent.kids[-1] is cur_leaf:
        cur_leaf = cur_leaf.parent
        
    if not cur_leaf.parent: return None
    
    i = cur_leaf.parent.kids.index(cur_leaf)
    cur = cur_leaf.parent.kids[i+1]
    
    while (not cur.is_leaf()):
        cur = cur[0]
        
    return cur

def bin_lengths(l):
    if l <= 2: return l
    else: return 2

def make(filter_expression, node_filter_function=lambda _: True):
    class _(Filter):
        def __init__(self):
            self.sigs = defaultdict(lambda: [0, FixedSizeRandomList(20)])
        
        def accept_derivation(self, bundle):
            root = bundle.derivation
            length = lambda s: bin_lengths(len(s))
        
            for node, ctx in find_all(root, filter_expression, with_context=True):
                if node_filter_function(node):
                    L, R = ctx['L'].lex.decode('u8'), ctx['R'].lex.decode('u8')
                    self.sigs[ (length(L), length(R)) ][0] += 1
                    self.sigs[ (length(L), length(R)) ][1].append( ' '.join((L, R)).encode('u8') )
            
        def output(self):
            for k, (freq, examples) in sorted(self.sigs.iteritems(), key=lambda e: e[1], reverse=True):
                print '% 15s | %s' % (freq, k)
                print '%s | %s' % (' ' * 15, '; '.join(examples))
                
    return _
           
from munge.cats.trace import analyse     
def filter_fn(node):
    comb = analyse(node[0].category, node[1].category, node.category)
    return comb not in ('l_punct_absorb', 'r_punct_absorb', 'funny_conj')
    
NP = make('@N <1 { *=L ! < * } <2 { *=R ! < * }', filter_fn)
#VO = make('VP < /VV/ < /NP/')
