#!/usr/bin/env python3
"""
Author = Thamme Gowda
Date = Mar 30, 2018
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))
from elisa2flat import parse
from collections import defaultdict, OrderedDict

def make_headers(paths):
    headers = []
    for path in paths:
        headers.append(path.split('/')[-1].split('.')[0].upper())
    assert len(headers) == len(paths)
    return headers


def read_docs(paths, ref_path):
    """
    reads and groups docs from multiple elisa xml files
    :param paths: elisa xml files for each MT output
    :param ref_path: the file from which references and source sentences are to be read from
    :return: yields documents
    """
    headers = make_headers(paths)
    docs = defaultdict(OrderedDict)
    for i, path in enumerate(paths):
        with open(path) as fp:
            for _id, text in parse(fp, 'SEGMENT', ['SOURCE.id', 'TEXT']):
               docs[_id][headers[i]] = text

    # read source and reference
    with open(ref_path) as fptr:
        for _id, src, ref in parse(fptr, 'SEGMENT', ['SOURCE.id', 'ORIG_SOURCE', 'ORIG_TARGET']):
            rec = [
                ('ID', _id),
                ('SOURCE', src),
                ('REF0', ref)
            ]
            rec.extend(docs[_id].items())
            yield rec


def format_viz(doc, pad_len):
    lines = ('%s:: %s' % (e[0].ljust(pad_len), e[1]) for e in doc)
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Creates visualizations of elisa output')
    parser.add_argument('-f', '--files', help='ELISA XML files', nargs='+', required=True)
    parser.add_argument('-o', '--out', help='OUTPUT file', default=sys.stdout, type=argparse.FileType('w'))
    args = parser.parse_args()

    paths = args.files
    for p in paths:
        assert os.path.exists(p), 'Path %s should exist' % p
    pad_len = None
    for doc in read_docs(paths, paths[0]):
        if pad_len is None:
            pad_len = max(len(e[0])for e in doc)
        args.out.write(format_viz(doc, pad_len))
        args.out.write('\n\n')
