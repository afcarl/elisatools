#!/usr/bin/env python3
import argparse
import sys
import codecs
if sys.version_info[0] == 2:
  from itertools import izip
else:
  izip = zip
from collections import defaultdict as dd
import re
import os.path
import gzip
from lxml import etree as ET # pip install lxml
scriptdir = os.path.dirname(os.path.abspath(__file__))


reader = codecs.getreader('utf8')
writer = codecs.getwriter('utf8')


def prepfile(fh, code):
  ret = gzip.open(fh.name, code if code.endswith("t") else code+"t") if fh.name.endswith(".gz") else fh
  if sys.version_info[0] == 2:
    if code.startswith('r'):
      ret = reader(fh)
    elif code.startswith('w'):
      ret = writer(fh)
    else:
      sys.stderr.write("I didn't understand code "+code+"\n")
      sys.exit(1)
  return ret



def main():
  parser = argparse.ArgumentParser(description="Remove segments based on source id startswith",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--infile", "-i", help="input file; this is filtered down")
  parser.add_argument("--segment", default="SEGMENT", help="segment object; these are included or not")
  parser.add_argument("--document", default="DOCUMENT", help="document object; these are included if they have children")
  parser.add_argument("--keyfield", default="SOURCE", help="what to match (via id) segments on")
  parser.add_argument("--startswith", "-s", default="CMN_SN", help="seg ids that start with this will be eliminated")
  parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file")



  try:
    args = parser.parse_args()
  except IOError as msg:
    parser.error(str(msg))

  outfile = prepfile(args.outfile, 'w')

  inode = ET.parse(args.infile)
  docrmcount=0
  segrmcount=0
  for doc in inode.findall('.//%s' % args.document):
    for seg in doc.findall('.//%s' % args.segment):
      id = seg.find('.//%s' % args.keyfield).get('id')
      if id.startswith(args.startswith):
        doc.remove(seg)
        segrmcount+=1
    if len(doc.findall('.//%s' % args.segment)) == 0:
      doc.getparent().remove(doc)
      docrmcount+=1
  xmlstr = ET.tostring(inode, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')
  outfile.write(xmlstr+"\n")
  sys.stderr.write("%d segs removed, %d docs removed\n" % (segrmcount, docrmcount))
if __name__ == '__main__':
  main()

