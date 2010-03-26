# coding=utf-8
import re

from copy import copy

from apps.cn.catlab import ptb_to_cat

from apps.util.echo import echo

from munge.proc.filter import Filter
from munge.proc.tgrep.tgrep import tgrep, find_first, find_all
from munge.penn.aug_nodes import Node

from munge.trees.pprint import pprint, aug_node_repr
from munge.util.tgrep_utils import get_first
from munge.cats.cat_defs import *
from munge.cats.trace import analyse
from munge.cats.nodes import FORWARD, BACKWARD
from munge.trees.traverse import lrp_repr

from munge.util.err_utils import warn, debug

from apps.cn.output import OutputCCGbankDerivation
from apps.cn.fix import Fix
from apps.cn.fix_utils import *

from apps.identify_lrhca import base_tag

def get_trace_index_from_tag(tag):
    bits = base_tag(tag, strip_cptb_tag=False).rsplit('-', 1)
    if len(bits) != 2:
        return ""
    else:
        return "-" + bits[1]

class FixExtraction(Fix):
    def pattern(self):
        return list((
        # /VP/ < { /VP:c/ < /V[PVEC]|VRD|VSB|VCD/ < /NP/=NP < /QP/=QP } < { /VP:c/ < /NP/ < /QP/ ! < /V[PVEC]|VRD|VSB|VCD/ }
            # must come before object extraction
            (r'*=TOP $ /-SBJ-d+/a=N < { * < /LB/=BEI } << { /NP-(?:TPC|OBJ)/ < ^/\*/ $ /V[PV]|VRD|VSB|VCD/=PRED }', self.fix_reduced_long_bei_gap),
            (r'*=TOP                < { * < /LB/=BEI } << { /NP-(?:TPC|OBJ)/ < ^/\*/ $ /V[PV]|VRD|VSB|VCD/=PRED }', self.fix_reduced_long_bei_gap),
            
            # doesn't work for 1:34(8) where an additional PP adjunct intervenes
            (r'*=TOP < { /PP-LGS/ < /P/=BEI } << { /NP-(?:TPC|OBJ)/ < ^/\*/ $ /V[PV]|VRD|VSB|VCD/=PRED }', self.fix_reduced_long_bei_gap),

            (r'/SB/=BEI $ { *=PP < { *=P < { /NP-SBJ/=T < ^/\*-\d+$/ $ *=S } } }', self.fix_short_bei_subj_gap), #0:11(4)
            (r'{ /SB/=BEI $ { /VP/=P << { /NP-OBJ/=T < ^/\*-\d+$/ $ *=S } } } > *=PP', self.fix_short_bei_obj_gap), #1:54(3)
            (r'{ /SB/=BEI $ { /VP/=BEIS << { /VP/=P < { /NP-IO/=T < ^/\*-\d+$/ $ *=S } > *=PP } } }', self.fix_short_bei_io_gap), # 31:2(3)

            # TODO: needs to be tested with (!NP)-TPC
            (r'/(IP|CP-CND)/=P < {/-TPC-\d+:t$/a=T $ /(IP|CP-CND)/=S}', self.fix_topicalisation_with_gap),
            (r'/(IP|CP-CND)/=P < {/-TPC:T$/a=T $ /(IP|CP-CND)/=S }', self.fix_topicalisation_without_gap),

            # Adds a unary rule when there is a clash between the modifier type (eg PP-PRD -> PP)
            # and what is expected (eg S/S)
            # This should come first, otherwise we get incorrect results in cases like 0:5(7).
            (r'*=P <1 {/:m$/a=T $ *=S}', self.fix_modification),

               # long bei-construction admits deletion of the object inside the S complement when it co-refers to the subject of bei.
            #   (r'', self.fix_long_bei_gap),

            # The node [CI]P will be CP for the normal relative clause construction (CP < IP DEC), and
            # IP for the null relativiser construction.
            # TODO: unary rule S[dcl]|NP -> N/N is only to apply in the null relativiser case.
            (r'^/\*RNR\*/ >> { * < /:c$/a }=G', self.fix_rnr),
            (r'''/VP/ 
                    < { /VP:c/=PP
                        < { /V[PVECA]|VRD|VSB|VCD/=P < { /NP/=S $ *=T } } 
                        < /QP/ } 
                    < { /VP/ 
                        < { /(PU|CC)/ 
                        $ { /VP:c/ 
                            ! < /V[PVECA]|VRD|VSB|VCD/ 
                            < /NP/ 
                            < /QP/ } } }''', self.clusterfix),

            # A few derivations annotate the structure of 他是去年开始的 as VP(VC NP-PRD(CP))
            (r'^/\*T\*/ > { /NP-SBJ/ >> { /[CI]P/ $ /WHNP(-\d+)?/=W > { /(CP|NP-PRD)/ > *=N } } }', self.fix_subject_extraction),
            (r'^/\*T\*/ > { /NP-SBJ/ >>                               { /CP/ > *=N } }', self.fix_reduced(self.fix_subject_extraction)),
            
            (r'^/\*T\*/ > { /NP-OBJ/ >> { /[CI]P/ $ /WHNP(-\d+)?/=W > { /(CP|NP-PRD)/ > *=N } } }', self.fix_object_extraction),
            (r'^/\*T\*/ > { /NP-OBJ/ >>                               { /CP/ > *=N } }', self.fix_reduced(self.fix_object_extraction)),

            # [ICV]P is in the expression because, if a *PRO* subject gap exists and is removed by catlab, we will not find a full IP in that position but a VP
            (r'^/\*T\*/ > { /[NPQ]P(?:-(?:TPC|LOC|EXT|ADV|DIR|IO|LGS|MNR|PN|PRP|TMP|TTL))?(?!-\d+)/=K >> { /[ICV]P/ $ {/WH[NP]P(-\d+)?/ > { /CP/ > *=N } } } }', self.fix_nongap_extraction),

            (r'* < { /IP-APP/=A $ /N[NRT]/=S }', self.fix_ip_app),

            # ba-construction object gap
            (r'*=TOP < { /BA/=BA $ { * << ^/\*-/ }=C }', self.fix_ba_object_gap),

            # Removes the prodrop trace *pro*
            (r'*=PP < { *=P < ^"*pro*" }', self.fix_prodrop),

            # Removes wayward WHNP traces without a coindex (e.g. 0:86(5), 11:9(9))
            (r'* < { * < /WHNP(?!-)/ }', self.remove_null_element),
            # Removes undischarged topicalisation traces
            (r'*=PP < { *=P < { /-TPC/a=T << ^/\*T\*/ $ *=S } }', self.remove_tpc_trace),
        ))

    def __init__(self, outdir):
        Fix.__init__(self, outdir)
        
    def clusterfix(self, top, pp, p, s, t):
        debug("Fixing argument cluster coordination: %s", pprint(top))
        debug('T: %s', t)
        # 1. Shrink the verb (node T)
        self.fix_object_gap(pp, p, t, s)
        # 2. Reattach the verb above the TOP node
        new_node = Node(top.category, 'TAG', top.kids)
        top.kids = [t, new_node]
        # (Reattaching parent pointers)
        for kid in new_node: kid.parent = new_node
        
        # 3. Relabel argument clusters
        # 3a. Find argument clusters
        for node, ctx in find_all(top, r'/VP/=VP < /NP/=NP < /QP/=QP', with_context=True):
            vp, np, qp = ctx.vp, ctx.np, ctx.qp
            # Now, VP should have category ((S[dcl]\NP)/QP)/NP
            SbNP = t.category.left.left
            QP, NP = qp.category, np.category
            # NP should have category ((S[dcl]\NP)/QP)\(((S[dcl]\NP)/QP)/NP)
            np.category = (SbNP/QP)|((SbNP/QP)/NP)
            # QP should have category ((S[dcl]\NP)\((S[dcl]\NP)/QP))
            qp.category = (SbNP)|((SbNP)/QP)
            
            self.fix_categories_starting_from(np, top)

    def remove_tpc_trace(self, _, pp, p, t, s):
        replace_kid(pp, p, s)

    def fix_rnr(self, rnr, g):
        debug("Fixing RNR: %s", pprint(g))
        index = get_trace_index_from_tag(rnr.lex) # -i
        debug("index: %s", index)
        expr = r'*=PP < { *=P < { *=T < ^/\*RNR\*%s/ $ *=S } }' % index
        for node, ctx in find_all(g, expr, with_context=True):
            inherit_tag(ctx['S'], ctx['P'])
            self.fix_object_gap(ctx['PP'], ctx['P'], ctx['T'], ctx['S'])
            self.fix_categories_starting_from(ctx['S'], g)
        
        debug("post deletion: %s", pprint(g))

        expr = r'*=PP < { *=P < { /%s/a=T $ *=S } }' % index
        node, ctx = get_first(g, expr, with_context=True)

        argument = ctx['T']
        self.fix_object_gap(ctx['PP'], ctx['P'], ctx['T'], ctx['S'])
        
        debug("T(argument): %s", lrp_repr(argument))
        debug("G: %s", lrp_repr(g))
        debug('PP: %s, P: %s, T: %s, S: %s', *map(lrp_repr, (ctx['PP'],ctx['P'],ctx['T'],ctx['S'])))

        new_g = Node(g.category, g.tag, [g, argument])

        replace_kid(g.parent, g, new_g)
        argument.parent = new_g # argument was previously disconnected

        new_g.category = ctx['S'].category.left

        self.fix_categories_starting_from(argument, new_g)

        debug("Done: %s", pprint(g))
        # print pprint(g.parent)

    def fix_short_bei_subj_gap(self, node, bei, pp, p, t, s):
        debug("fixing short bei subject gap: %s", lrp_repr(pp))
        # take the VP sibling of SB
        # replace T with S
        # this analysis isn't entirely correct
        replace_kid(pp, p, s)

    def fix_short_bei_obj_gap(self, node, pp, bei, t, p, s):
        debug("fixing short bei object gap: pp:%s\np:%s\ns:%s", lrp_repr(pp), lrp_repr(p), lrp_repr(s))
        
        replace_kid(pp, p, s)
        bei.category = bei.category.clone_with(right=s.category)
        
    def fix_short_bei_io_gap(self, node, pp, bei, beis, t, p, s):
        debug("fixing short bei io gap: pp:%s\np:%s\ns:%s", lrp_repr(pp), lrp_repr(p), lrp_repr(s))
        
        replace_kid(pp, p, s)
        self.fix_categories_starting_from(s, until=pp)
        bei.category = bei.category.clone_with(right=beis.category)

    def remove_null_element(self, node):
        # Remove the null element WHNP and its trace -NONE- '*OP*' and shrink tree
        pp, context = get_first(node, r'*=PP < { *=P < { /WH[NP]P/=T $ *=S } }', with_context=True)
        p, t, s = context['P'], context['T'], context['S']

        replace_kid(pp, p, s)

    def relabel_relativiser(self, node):
        # Relabel the relativiser category (NP/NP)\S to (NP/NP)\(S|NP)
        
        result = get_first(node, r'*=S $ /(DEC|SP)/=REL', with_context=True, left_to_right=True)

        if result is not None:
            _, context = result
            s, relativiser = context['S'], context['REL']

            relativiser.category = relativiser.category.clone_with(right=s.category)
            debug("New rel category: %s", relativiser.category)

            return True
        else:
            warn("Couldn't find relativiser under %s", node)
            return False

    @staticmethod
    def is_topicalisation(cat):
        # T/(T/X)
        return (cat.is_complex() and cat.right.is_complex()
                and cat.left == cat.right.left
                and cat.direction == FORWARD and cat.right.direction == FORWARD)

    def fix_categories_starting_from(self, node, until):
#        debug("fix from\n%s to\n%s", pprint(node), pprint(until))

        while node is not until:
            if (not node.parent) or node.parent.count() < 2: break

            l, r, p = node.parent[0], node.parent[1], node.parent
            L, R, P = (n.category for n in (l, r, p))
            debug("L: %s R: %s P: %s", L, R, P)

            applied_rule = analyse(L, R, P)
            debug("[ %s'%s' %s'%s' -> %s'%s' ] %s",
                L, ''.join(l.text()),
                R, ''.join(r.text()),
                P, ''.join(p.text()),
                applied_rule)

            if applied_rule is None:
                debug("invalid rule %s %s -> %s", L, R, P)

                # conj R -> P
                # Make P into R[conj]
                # L cannot be the comma category (,), otherwise we get a mis-analysis
                # in 2:22(5)
                if str(L) in ('conj', 'LCM'):
                    p.category = R.clone_adding_feature('conj')
                    debug("New category: %s", p.category)

                # L R[conj] -> P
                #
                elif R.has_feature('conj'):
                    new_L = L.clone()
#                    new_L.features = []

                    r.category = new_L.clone_adding_feature('conj')
                    p.category = new_L

                    debug("New category: %s", new_L)

                elif L.is_leaf():
                    if P.has_feature('conj') and l.tag in ('PU', 'CC'): # treat as partial coordination
                        debug("Fixing coordination: %s" % P)
                        p.category = r.category.clone_adding_feature('conj')
                        debug("new parent category: %s" % p.category)
                        
                    elif l.tag == "PU" and not P.has_feature('conj'): # treat as absorption
                        debug("Fixing left absorption: %s" % P)
                        p.category = r.category

                    elif R.is_complex() and R.left.is_complex() and L == R.left.right:
                        T = R.left.left
                        new_category = typeraise(L, T, TR_FORWARD)#T/(T|L)
                        node.parent[0] = Node(new_category, l.tag, [l])

                        new_parent_category = fcomp(new_category, R)
                        if new_parent_category:
                            debug("new parent category: %s", new_parent_category)
                            p.category = new_parent_category

                        debug("New category: %s", new_category)

                elif R.is_leaf():
                    if r.tag == "PU": # treat as absorption
                        debug("Fixing right absorption: %s" % P)
                        p.category = l.category

                    elif L.is_complex() and L.left.is_complex() and R == L.left.right:
                        T = L.left.left
                        new_category = typeraise(R, T, TR_BACKWARD)#T|(T/R)
                        node.parent[1] = Node(new_category, r.tag, [r])

                        new_parent_category = bxcomp(L, new_category)
                        if new_parent_category:
                            debug("new parent category: %s", new_parent_category)
                            p.category = new_parent_category

                        debug("New category: %s", new_category)

                else:
                    # try typeraising fix
                    # T/(T/X) (T\A)/X -> T can be fixed:
                    # (T\A)/((T\A)/X) (T\A)/X -> T\A
                    if self.is_topicalisation(L) and (
                        L.right.right == R.right and
                        P == L.left and P == R.left.left):
                        T_A = R.left
                        X = R.right

                        l.category = T_A/(T_A/X)
                        new_parent_category = T_A
                    else:
                        new_parent_category = fcomp(L, R) or bcomp(L, R) or bxcomp(L, R) or fxcomp(L, R)

                    if new_parent_category:
                        debug("new parent category: %s", new_parent_category)
                        p.category = new_parent_category
                    else:
                        debug("couldn't fix, skipping")

            node = node.parent
            debug('')

    #@echo
    def fix_subject_extraction(self, _, n, w=None, reduced=False):
        debug("%s", reduced)
        node = n
        debug("Fixing subject extraction: %s", lrp_repr(node))
        if not reduced:
            self.remove_null_element(node)

        if w:
            index = get_trace_index_from_tag(w.tag)
        else:
            index = ''
            
        expr = r'*=PP < { *=P < { /NP-SBJ/=T << ^/\*T\*%s/ $ *=S } }' % index

        for trace_NP, context in find_all(node, expr, with_context=True):
            pp, p, t, s = (context[n] for n in "PP P T S".split())

            self.fix_object_gap(pp, p, t, s)
            self.fix_categories_starting_from(s, until=node)

            if not self.relabel_relativiser(node):
                # TOP is the shrunk VP
                # after shrinking, we can get VV or VA here
                top, context = get_first(node, r'/([ICV]P|V[VA]|VRD|VSB|VCD)/=TOP $ *=SS', with_context=True)
                ss = context["SS"]

                debug("Creating null relativiser unary category: %s", ss.category/ss.category)
                replace_kid(top.parent, top, Node(ss.category/ss.category, "NN", [top]))

        debug(pprint(node))

    #@echo
    def fix_nongap_extraction(self, _, n, k):
        node = n
        debug("Fixing nongap extraction: %s", pprint(node))
        debug("k %s", pprint(k))
        self.remove_null_element(node)

        index = get_trace_index_from_tag(k.tag)
        expr = r'*=PP < { *=P < { /[NPQ]P(?:-(?:TPC|LOC|EXT|ADV|DIR|IO|LGS|MNR|PN|PRP|TMP|TTL))?%s/=T << ^/\*T\*/ $ *=S } }' % index

        # we use "<<" in the expression, because fix_*_topicalisation comes
        # before fix_nongap_extraction, and this can introduce an extra layer between
        # the phrasal tag and the trace
        for trace_NP, context in find_all(node, expr, with_context=True):
            pp, p, t, s = (context[n] for n in "PP P T S".split())

            # remove T from P
            # replace P with S
            self.fix_object_gap(pp, p, t, s)

            if not self.relabel_relativiser(node):
                top, context = get_first(node, r'/[ICV]P/=TOP $ *=SS', with_context=True)
                ss = context["SS"]

                debug("Creating null relativiser unary category: %s", ss.category/ss.category)
                replace_kid(top.parent, top, Node(ss.category/ss.category, "NN", [top]))

    def fix_ip_app(self, p, a, s):
        debug("Fixing IP-APP NX: %s", lrp_repr(p))
        new_kid = copy(a)
        new_kid.tag = base_tag(new_kid.tag) # relabel to stop infinite matching
        replace_kid(p, a, Node(s.category/s.category, "NN", [new_kid]))

    def fix_object_extraction(self, _, n, w=None, reduced=False):
        node = n
        debug("Fixing object extraction: %s", lrp_repr(node))
        if not reduced:
            self.remove_null_element(node)
        
        if w:
            index = get_trace_index_from_tag(w.tag)
        else:
            index = ''
            
        expr = r'/IP/=TOP << { *=PP < { *=P < { /NP-OBJ/=T << ^/\*T\*%s/ $ *=S } } }' % index

        for trace_NP, context in find_all(node, expr, with_context=True):
            top, pp, p, t, s = (context[n] for n in "TOP PP P T S".split())

            self.fix_object_gap(pp, p, t, s)

            self.fix_categories_starting_from(s, until=top)

            # If we couldn't find the DEC node, this is the null relativiser case
            if not self.relabel_relativiser(node):
                # TOP is the S node
                # null relativiser category comes from sibling of TOP
                # if TOP has no sibling, then we're likely inside a NP-PRD < CP reduced relative (cf 1:2(9))
                result = get_first(top, r'* $ *=SS', with_context=True, nonrecursive=True)
                if result:
                    _, ctx = result; ss = ctx['SS']
                    debug("Creating null relativiser unary category: %s", ss.category/ss.category)
                    replace_kid(top.parent, top, Node(ss.category/ss.category, "NN", [top]))

    def relabel_bei_category(self, top, pred):
        bei, context = get_first(top, r'*=S [ $ /LB/=BEI | $ ^"由"=BEI ]', with_context=True)
        s = context['S']
        bei = context['BEI']

        bei.category = bei.category.clone_with(right=s.category)
        bei.category.left._right = pred.category
        
        bei.parent.category = bei.category.left
        
        debug("new bei category: %s", bei.category)
        return bei
        
    def relabel_ba_category(self, top, ba):
        ba, context = get_first(top, r'*=S [ $ /BA/=BA ]', with_context=True)
        s, ba = context['S'], context['BA']

        ba.category = ba.category.clone_with(right=s.category)
        
        debug("new ba category: %s", ba.category)
        return ba

    def fix_reduced_long_bei_gap(self, node, *args, **kwargs):
        debug("Fixing reduced long bei gap: %s", lrp_repr(node))

        kwargs.update(reduced=True)
        return self.fix_long_bei_gap(node, *args, **kwargs)
        
    def fix_reduced(self, f):
        def _f(node, *args, **kwargs):
            kwargs.update(reduced=True)
            return f(node, *args, **kwargs)
        return _f

    def fix_long_bei_gap(self, node, bei, pred, top, n=None, reduced=False):
        debug("Fixing long bei gap: %s", lrp_repr(node))

        if not reduced:
            self.remove_null_element(top)
            
        if n:
            index = get_trace_index_from_tag(n.tag)
        else:
            index = r'\*'

        # FIXME: this matches only once (because it's TOP being matched, not T)
        # \*(?!T) to avoid matching *T* traces
        expr = r'*=PP < { *=P < { /NP-(?:TPC|OBJ)/=T < ^/%s/a $ *=S } }' % index
        trace_NP, context = get_first(top, expr, with_context=True)

        pp, p, t, s = (context[n] for n in "PP P T S".split())
        # remove T from P
        # replace P with S
        self.fix_object_gap(pp, p, t, s)

        self.fix_categories_starting_from(s, until=top)
        self.relabel_bei_category(top, pred)
        
        top.category = top[0].category.left

        debug("done %s", pprint(top))

    def fix_ba_object_gap(self, node, top, c, ba):
        debug("Fixing ba-construction object gap: %s" % lrp_repr(node))

        for trace_NP, context in find_all(top, r'*=PP < {*=P < { /NP-OBJ/=T < ^/\*-/ $ *=S } }', with_context=True):
            debug("Found %s", trace_NP)
            pp, p, t, s = (context[n] for n in "PP P T S".split())

            self.fix_object_gap(pp, p, t, s)
            self.fix_categories_starting_from(s, until=c)
            
        self.relabel_ba_category(top, ba)

    @staticmethod
    def fix_object_gap(pp, p, t, s):
        '''Given a trace _t_, its sibling _s_, its parent _p_ and its grandparent _pp_, replaces _p_ with its sibling.'''
        p.kids.remove(t)
        replace_kid(pp, p, s)

    def fix_topicalisation_with_gap(self, node, p, s, t):
        debug("Fixing topicalisation with gap:\nnode=%s\ns=%s\nt=%s", lrp_repr(node), pprint(s), pprint(t))

        # stop this method from matching again (in case there's absorption on the top node, cf 2:22(5))
        t.tag = base_tag(t.tag, strip_cptb_tag=False)
        # create topicalised category based on the tag of T
        typeraise_t_category = ptb_to_cat(t)
        # insert a node with the topicalised category
        replace_kid(p, t, Node(
            typeraise(typeraise_t_category, S, TR_TOPICALISATION),
            base_tag(t.tag, strip_cptb_tag=False),
            [t]))

        index = get_trace_index_from_tag(t.tag)

        # attested gaps:
        # 575 IP-TPC:t
        # 134 NP-TPC:t
        #  10 IP-Q-TPC:t
        #   8 CP-TPC:t
        #   4 NP-PN-TPC:t
        #   2 QP-TPC:t
        #   2 NP-TTL-TPC:t
        #   1 PP-TPC:t
        #   1 IP-IJ-TPC:t
        #   1 INTJ-TPC:t
        #   1 CP-Q-TPC:t
        #   1 CP-CND-TPC:t
        expr = r'/IP/=TOP << { *=PP < { *=P < { /[NICQP]P-(?:SBJ|OBJ)/=T < ^/\*T\*%s/ $ *=S } } }' % index

        for top, ctx in find_all(s, expr, with_context=True):
            self.fix_object_gap(*(ctx[n] for n in "PP P T S".split()))

            self.fix_categories_starting_from(ctx['S'], until=top)

    def fix_topicalisation_without_gap(self, node, p, s, t):
        debug("Fixing topicalisation without gap: %s", pprint(node))

        new_kid = copy(t)
        new_kid.tag = base_tag(new_kid.tag, strip_cptb_tag=False)

        new_category = featureless(p.category)/featureless(s.category)
        replace_kid(p, t, Node(new_category, t.tag, [new_kid]))

    def fix_prodrop(self, node, pp, p):
        #      X=PP
        #      |
        #      NP=P
        #      |
        #    -NONE- '*pro*'
        pp.kids.remove(p)

        # this step happens after fix_rc, and object extraction with subject pro-drop can
        # lead to a pro-dropped node like:
        #        X
        #        |
        #     S/(S\NP)=PP
        #        |
        #       NP=P
        #        |
        #   -NONE- '*pro*'
        # In this case, we want to remove the whole structure
        if (not pp.kids) and pp.parent:
            ppp = pp.parent
            ppp.kids.remove(pp)

    def fix_modification(self, node, p, s, t):
        debug("Fixing modification: %s", lrp_repr(node))
        S, P = s.category, p.category

        # If you don't strip the tag :m from the newly created child (new_kid),
        # the fix_modification pattern will match infinitely when tgrep visits new_kid
        new_kid = copy(t)
        new_kid.tag = base_tag(new_kid.tag, strip_cptb_tag=False)

        new_category = featureless(P) / featureless(S)
        debug("Creating category %s", new_category)
        replace_kid(p, t, Node(new_category, t.tag, [new_kid]))

