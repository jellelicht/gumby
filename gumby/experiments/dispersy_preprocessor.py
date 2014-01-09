import os
import sys
from random import expovariate, random
from gumby.scenario import ScenarioRunner

class ScenarioPreProcessor(ScenarioRunner):

    def __init__(self, filename, outputfile=sys.stdout, max_tstmp=0):
        self._cur_line = None

        self._callables = {}
        self._callables['churn'] = self.churn

        print >> sys.stderr, "Looking for max_timestamp, max_peer... in %s" % filename,

        max_peer = 0
        for (tstmp, lineno, clb, args, peerspec) in self._parse_scenario(filename):
            max_tstmp = max(tstmp, max_tstmp)
            if peerspec[0]:
                max_peer = max(max_peer, max(peerspec[0]))

        print >> sys.stderr, "\tfound %d and %d" % (max_tstmp, max_peer)

        print >> sys.stderr, "Preprocessing file...",
        for (tstmp, lineno, clb, args, peerspec) in self._parse_scenario(filename):
            if clb in self._callables:
                yes_peers, no_peers = peerspec
                if not yes_peers:
                    yes_peers = set(range(1, max_peer + 1))
                for peer in no_peers:
                    yes_peers.discard(peer)

                for peer in yes_peers:
                    for line in self._callables[clb](tstmp, max_tstmp, *args):
                        print >> outputfile, line, '{%s}' % peer
            else:
                print >> outputfile, self._cur_line
        print >> sys.stderr, "\tdone"

    def _parse_for_this_peer(self, peerspec):
        return True

    def _preprocess_line(self, line):
        self._cur_line = line.strip()
        return line

    def churn(self, tstmp, max_tstmp, churn_type, desired_mean=300, min_online=5.0):
        desired_mean = float(desired_mean)
        min_online = float(min_online)

        def get_delay():
            if churn_type == 'expon':
                return min_online + expovariate(1.0 / (desired_mean - min_online))
            elif churn_type == 'fixed':
                return desired_mean
            else:
                raise NotImplementedError('only expon churn is implemented, got %s' % churn_type)

        go_online = random() < 0.5
        while tstmp < max_tstmp:
            yield "@0:%d %s" % (tstmp, "online" if go_online else "offline")
            tstmp += get_delay()
            go_online = not go_online

def main(inputfile, outputfile, maxtime=0):
    inputfile = os.path.abspath(inputfile)
    if os.path.exists(inputfile):
        f = open(outputfile, 'w')

        ScenarioPreProcessor(inputfile, f, maxtime)

        f.close()
    else:
        print >> sys.stderr, inputfile, "not found"

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print "Usage: %s <input-file> <output-file> (<max-time>)" % (sys.argv[0])
        print >> sys.stderr, sys.argv

        exit(1)

    if len(sys.argv) == 4:
        main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
    else:
        main(sys.argv[1], sys.argv[2])
