#!/usr/bin/env python3

import argparse
import os.path
import sys
from itertools import cycle
import logging as log


log.basicConfig(level=log.DEBUG)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Given word counts and preferred order and distributions, assign documents to categories",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wcfile", "-w", nargs='?', type=argparse.FileType('r'), help="word count file (docid count)")
    parser.add_argument("--filelist", "-f", nargs='?', type=argparse.FileType('r'),
                        help="documents in order of distribution, possibly with other information")
    parser.add_argument("--sizes", "-s", nargs='+', type=int, help="list of sizes desired in each category")
    parser.add_argument("--categories", "-c", nargs='+', help="list of categories. Must match sizes")
    parser.add_argument("--remainder", "-r", default="train", help="remainder category. Should be a new category")
    parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout,
                        help="docid category")
    parser.add_argument("--devlstfile", "-d", default=None,
                        help="file of desired documents for dev (subject to length constraints,"
                             " must be a set called 'dev')")
    parser.add_argument("--setElstfile", "-E", default=None,
                        help="file of desired documents for setE (subject to length constraints,"
                             " must be a set called 'setE')")
    try:
        return parser.parse_args()
    except IOError as msg:
        parser.error(str(msg))


def main(filelist, wcfile, outfile, sizes, categories, **args):
    # NOTE: always round robins into remainder. Should there be an option to not do this?

    assert len(sizes) == len(categories), "Sizes and categories must be same dimension"

    devlst = list()
    if args['devlstfile']:
        assert 'dev' in categories
        devlst = open(args['devlstfile']).read().split()

    counts = {}
    for line in wcfile:
        word, count = line.strip().split('\t')
        counts[word] = int(count)
    tot_count = sum(counts.values())
    assert sum(args['sizes']) < tot_count, f'Splits of sizes {sizes} not possible; total words= {tot_count}'
    files = []
    for line in filelist:
        files.append(line.strip().split()[0])

    data = {}
    for cat, size in zip(categories, sizes):
        data[cat] = {"LEFT": size, "SET": []}
    data[args['remainder']] = {"LEFT": float("inf"), "SET": []}

    # select specified dev docids
    added_devlst = list()
    if 'dev' in categories and devlst:
        for doc in devlst:
            if doc in files:
                if data['dev']["LEFT"] >= counts[doc]:
                    data[cat]["SET"].append(doc)
                    data[cat]["LEFT"] -= counts[doc]
                    files.remove(doc)
                    added_devlst.append(doc)
        if len(added_devlst) < len(devlst):
            sys.stderr.write("The word limit of '%s' is reached," \
                             " %d documents are added to the dev set.\n" \
                             "The remaining documents from the dev list are not handled specially.\n"
                             % (os.path.basename(outfile.name), len(added_devlst)))
        else:
            sys.stderr.write("The word limit of '%s' is not reached," \
                             " %d documents are added to the dev set.\n" \
                             "Regular procedure is used to bring the dev set up to the specified limit.\n"
                             % (os.path.basename(outfile.name), len(added_devlst)))
    sys.stderr.write("Added doc ids:\n")
    for doc in added_devlst:
        sys.stderr.write("  %s\n" % doc)

    for cat in cycle(list(data.keys())):
        if len(files) == 0:
            break
        if data[cat]["LEFT"] >= counts[files[0]]:
            doc = files.pop(0)
            data[cat]["SET"].append(doc)
            data[cat]["LEFT"] -= counts[doc]

    for cat in list(data.keys()):
        sys.stderr.write("%s %f\n" % (cat, data[cat]["LEFT"]))
        for doc in data[cat]["SET"]:
            outfile.write("%s\t%s\n" % (doc, cat))


if __name__ == '__main__':
    args = vars(parse_args())
    main(**args)
