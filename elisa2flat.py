#!/usr/bin/env python3
import argparse
import gzip
import sys

from lxml import etree as ET  # pip install lxml


def parse(infile, segment, fields):
    infile = gzip.open(infile.name, 'rb') if infile.name.endswith(".gz") else infile
    assert type(segment) is str
    assert type(fields) is list
    ctxt = ET.iterparse(infile, events=("end", "start"))
    # don't delete when in the middle of an element you want to investigate
    lock = False
    for event, element in ctxt:
        if event == "start" and element.tag == segment:
            lock = True
        if event == "end" and element.tag == segment:
            outfields = []
            for fieldopts in fields:
                wrotesomething = False
                fieldopts = fieldopts.split(":")
                while len(fieldopts) > 0:
                    field = fieldopts.pop(0)
                    subfields = field.split(".")
                    matches = [element, ] if subfields[0] == segment else element.findall(".//" + subfields[0])
                    for match in matches:
                        value = match.get(subfields[1]) if len(subfields) > 1 else match.text
                        value = value.replace('\n', ' ') if value is not None else None
                        value = value.replace('\t', ' ') if value is not None else None
                        if value is not None:
                            outfields.append(value)
                            wrotesomething = True
                    del matches
                    if wrotesomething:
                        break
                if not wrotesomething:
                    outfields.append("")
            yield outfields
            lock = False
        # recover memory
        if event == "end" and not lock:
            element.clear()
            for ancestor in element.xpath('ancestor-or-self::*'):
                while ancestor.getprevious() is not None and ancestor.getparent() is not None\
                        and ancestor.getparent()[0] is not None:
                    del ancestor.getparent()[0]
    del ctxt

def main():
    parser = argparse.ArgumentParser(
        description="Given a compressed elisa xml file and list of attributes, print them out, tab separated",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--infile", "-i", nargs='?', type=argparse.FileType('rb'), default=sys.stdin, help="input file")
    parser.add_argument("--fields", "-f", nargs='+', required=True,
                        help="list of fields to extract text from. if attribute is desired, use field.attribute."
                             " Separate fallback fields with :")
    parser.add_argument("--segment", "-s", default="SEGMENT",
                        help="segment name. pre v4, PARALLEL for x-eng, SEGMENT for monolingual. Otherwise SEGMENT. "
                             "More than one match per segment will be concatenated")
    parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout,
                        help="output file")
    args = parser.parse_args()

    recs = parse(args.infile, args.segment, args.fields)

    out = args.outfile
    close_out = False
    if out.name.endswith(".gz"):
        close_out = True
        out = gzip.open(out.name, "wt")
    for rec in recs:
        out.write('\t'.join(rec))
        out.write('\n')

    if close_out:
        out.close()


if __name__ == '__main__':
    main()
