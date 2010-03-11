from munge.proc.filter import Filter
from munge.cats.trace import analyse
from munge.util.dict_utils import CountDict, sorted_by_value_desc
from munge.trees.traverse import nodes
from munge.util.err_utils import *

from collections import defaultdict

class CountRules(Filter):
    def __init__(self):
        Filter.__init__(self)
        self.counts = CountDict()
        
    def accept_derivation(self, bundle):
        for node in nodes(bundle.derivation):
            if node.is_leaf(): continue
                    
            l, p = node[0].cat, node.cat
            r = node[1].cat if node.count() > 1 else None
            
            self.counts[ tuple(n for n in (l, r, p)) ] += 1
    
    def output(self):
        for (l, r, p), freq in sorted_by_value_desc(self.counts):
            print "%8d | %15s  %-15s -> %-15s [%s]" % (freq, l, r, p, analyse(l, r, p))
            
class ListAtoms(Filter):
    def __init__(self):
        Filter.__init__(self)
        self.atoms = set()
                
    def get_atoms(self, cat):
        result = set()
        for sub in cat:
            if not sub.is_complex():
                # remove any features
                sub = sub.clone()
                sub.features = []
                result.add(sub)
            else: result.update(self.get_atoms(sub))
        for new in result - self.atoms:
            print new

        return result
        
    def accept_derivation(self, bundle):
        for node in nodes(bundle.derivation):
            self.atoms.update(self.get_atoms(node.cat))
        
    def output(self):
        for atom in sorted(map(str, self.atoms)):
            print atom
            
class CountWords(Filter):
    def __init__(self):
        Filter.__init__(self)
        self.n = 0

    def accept_leaf(self, leaf):
        self.n += 1

    def output(self):
        print self.n

class CountStructures(Filter):
    def __init__(self):
        Filter.__init__(self)

        self.counts = defaultdict(lambda: 0)
        self.adjunction_kinds = defaultdict(lambda: 0)
        self.predication_kinds = defaultdict(lambda: 0)
        self.apposition_kinds = defaultdict(lambda: 0)
        self.modification_kinds = defaultdict(lambda: 0)
        self.coordination_kinds = defaultdict(lambda: 0)

    def accept_derivation(self, bundle):
        for node in nodes(bundle.derivation):
            if not node.is_leaf():
                self.counts['total'] += 1
                kid_tags = ' '.join(kid.tag for kid in node)

                if is_predication(node):
                    self.counts['predication'] += 1
                    self.predication_kinds[kid_tags] += 1

                elif is_coordination(node): # coordination
                    self.counts['coordination'] += 1
                    self.coordination_kinds[kid_tags] += 1

                elif is_internal_structure(node):
                    self.counts['structure'] += 1

                elif node[0].is_leaf(): # head initial complementation
                    self.counts['head-initial'] += 1

                elif node[-1].is_leaf(): # head final complementation
                    self.counts['head-final'] += 1

                elif is_apposition(node):
                    self.counts['apposition'] += 1
                    self.apposition_kinds[kid_tags] += 1

                elif is_modification(node):
                    self.counts['modification'] += 1
                    self.modification_kinds[kid_tags] += 1

                else: # adjunction
                    self.counts['adjunction'] += 1
                    self.adjunction_kinds[kid_tags] += 1


    def output(self):
        for node_type, count in sorted_by_value_desc(self.counts):
            if node_type == 'total': continue
            print "% 15s | %d" % (node_type, count)
        print "% 15s | %d" % ('total', self.counts['total'])
        print

        for dict_name in ('predication', 'apposition', 'modification', 'adjunction', 'coordination'):
            print dict_name
            for tag_string, count in sorted_by_value_desc(getattr(self, dict_name + '_kinds')):
                print "% 6d | (% 2d) %s" % (count, len(tag_string.split(' ')), tag_string)
            print

