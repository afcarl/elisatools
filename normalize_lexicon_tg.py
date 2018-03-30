#!/usr/bin/env python3
# Author = TG
# Date = Mar 30, 2018
# This script normalizes lexicons

import argparse
import os.path
import re
import sys
from collections import defaultdict as ddict

scriptdir = os.path.dirname(os.path.abspath(__file__))

def read_lexicons(inpfile):
    yield from (line.strip().split('\t') for line in inpfile)


def clean_text(text):
    text = re.sub(r'\(.*\)', '', text)  # harsh parenthetical stripping
    return re.sub(r'e\.g\..*', '', text)  # e.g. comes before garbage

def split_field(text):
    return [x.strip() for x in re.split(r'[;,/]| or ', clean_text(text))]    # splitting

def normalize_lexicon(rec, split_words=True):
    assert len(rec) == 3
    src, pos, tgt = (x.strip() for x in rec)
    src, tgt = src.lower(), tgt.lower()
    if split_words:
        srcs, tgts = split_field(src), split_field(tgt)
    else:
        srcs, tgts = [clean_text(src)], [clean_text(tgt)]
    return srcs, tgts


def normalize(lexicons, stats, args):
    for rec in lexicons:
        if len(rec) != 3:
            stats['BAD_REC'] += 1
            continue
        pos = rec[1]
        srcs, tgts = normalize_lexicon(rec, split_words=not args.nosplit)

        for tgt in tgts:
            # OTHER HEURISTICS...
            # eliminate initial "to" (to walk -> walk)
            if tgt.lower().startswith('to '):
                trg = tgt[3:].strip()
            if not tgt:
                stats['TGT_NIL'] += 1
                continue
            if len(tgt.split()) > args.targetlimit:
                stats['TGT_BIG'] += 1
                continue
            for src in srcs:
                yield src, pos, tgt

def write_out(recs, out):
    count = 0
    for rec in recs:
        count += 1
        out.write('\t'.join(rec))
        out.write('\n')
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Given LRLP lexicon flat representation attempt to normalize it to short phrase form",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--infile", "-i", nargs='?', type=argparse.FileType('r'), default=sys.stdin,
                        help="input lexicon file")
    parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout,
                        help="output instruction file")
    parser.add_argument("--nosplit", "-n", action='store_true', default=False,
                        help="don't split target on commas/semicolons/or/slash")
    parser.add_argument("--targetlimit", "-l", type=int, default=10,
                        help="maximum length of target entry after splitting")
    parser.add_argument("--earlytargetlimit", "-L", type=int, default=20,
                        help="maximum length of target entry before splitting")

    args = parser.parse_args()

    stats = ddict(int)
    lexicons = read_lexicons(args.infile)
    lexicons = normalize(lexicons, stats, args)
    stats['OUT_RECS'] = write_out(lexicons, args.outfile)

    sys.stderr.write("Stats: %s\n" % str(['%s: %s' % r for r in stats.items()]))
