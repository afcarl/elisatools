#! /usr/bin/env python
import argparse
import sys
import codecs
from collections import defaultdict as dd
import lxml.etree as ET
import gzip
import re
import os.path
import hashlib
from itertools import izip
#from xml.dom import minidom
scriptdir = os.path.dirname(os.path.abspath(__file__))

# TODO: option to build gzip file

def main():
  parser = argparse.ArgumentParser(description="Create xml from extracted and transformed monolingual data",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--rootdir", "-r", default=".", help="root lrlp dir")
  parser.add_argument("--corpora", "-c", nargs='+', help="prefixes that have at minimum a manifest and original/ file")
  parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file")
  parser.add_argument("--psmfile", "-p", nargs='?', type=argparse.FileType('r'), default=None, help="psm annotation file")
  parser.add_argument("--annfile", "-a", nargs='?', type=argparse.FileType('r'), default=None, help="entity annotation file")

  try:
    args = parser.parse_args()
  except IOError, msg:
    parser.error(str(msg))

  reader = codecs.getreader('utf-8')
  writer = codecs.getwriter('utf-8')
  outfile = args.outfile
#  outfile = writer(args.outfile)

  # for every document, for every position, a list of (pointers to) annotations
  # then for every segment, retrieve the sublist and create the set of annotations relevant to the annotation

  # needs to be two-pass so we create the proper list size
  # TODO: no it doesn't
  psmtemp = dd(list)
  
  # data is kind (headline/post) id start length then if 'post', author timestamp

  # spans of length 0 are discarded (these seem to be multiply occurring authors/datetimes/ids
  # TODO: what's with these bad entries?? There's a lot of them. sometimes they make my window hang but sometimes they look totally normal

  if args.psmfile is not None:
    psmdiscardcount = 0
    for ln, line in enumerate(reader(args.psmfile)):
      try:
        toks = line.strip().split('\t')
        if len(toks) < 4:
          sys.stderr.write("Skipping line %d of psmfile; bad data (%d toks)\n" % (ln, len(toks)))
          continue;
        if int(toks[3]) == 0:
          psmdiscardcount+=1
          continue
        doc = toks[1]
        psmtemp[doc].append(toks)
      except:
        print ln
        raise
    sys.stderr.write("Discarded %d psm entries\n" % psmdiscardcount)
  # will fill on demand
  psms = dd(lambda: dd(list))
  # entities: document/start/kind/data

  # data is kind (NE/FE/SSA) id start end menid span, then
  # if NE, type
  # if FE, class (mention/head), subtype (NAM/NOM/TTL/?/None), entid, type
  # if SSA, pred/arg agent/patient/act/location/state, pred reference (check readme)
  # anns = dd(lambda: dd(lambda: dd(list)))
  anntemp = dd(list)
  if args.annfile is not None:
    anndiscardcount = 0
    for ln, line in enumerate(reader(args.annfile)):
      try:
        toks = line.strip().split('\t')
        if len(toks) < 6:
          sys.stderr.write("Skipping line %d of annfile; bad data (%d toks)\n" % (ln, len(toks)))
          continue;
        if int(toks[3])-int(toks[2]) == 0:
          anndiscardcount+=1
          continue
        anntemp[toks[1]].append(toks)
      except:
        print ln
        raise
    sys.stderr.write("Discarded %d ann entries\n" % anndiscardcount)
  # will fill on demand
  anns = dd(lambda: dd(list))

  # each segment is a legit xml block. the corpus/language/document are faked
  # TODO: corpus/document
  # TODO: make this more generalizable!
  for corpus in args.corpora:
    manifest = reader(open(os.path.join(args.rootdir, "%s.manifest" % corpus)))
    origfile = reader(open(os.path.join(args.rootdir, "original", "%s.flat" % corpus)))
    tokfile = reader(open(os.path.join(args.rootdir, "tokenized", "%s.flat" % corpus)))
    cdectokfile = reader(open(os.path.join(args.rootdir, "cdec-tokenized", "%s.flat" % corpus)))
    cdectoklcfile = reader(open(os.path.join(args.rootdir, "cdec-tokenized", "%s.flat.lc" % corpus)))
    morphtokfile = reader(open(os.path.join(args.rootdir, "morph-tokenized", "%s.flat" % corpus)))
    morphfile = reader(open(os.path.join(args.rootdir, "morph", "%s.flat" % corpus)))
    for manline, origline, tokline, cdectokline, cdectoklcline, morphtokline, morphline in izip(manifest, origfile, tokfile, cdectokfile, cdectoklcfile, morphtokfile, morphfile):
      origline = origline.strip()
      tokline = tokline.strip()
      cdectokline =   cdectokline.strip()
      cdectoklcline = cdectoklcline.strip()
      morphtokline =   morphtokline.strip()
      morphline =   morphline.strip()
      man = manline.strip().split('\t')
      fullid = man[1]
      fields = fullid.split('_') # genre, provenance, lang, id, date
      xroot = ET.Element('SEGMENT')
      subelements = []
      subelements.extend(zip(['GENRE', 'PROVENANCE', 'LANGUAGE', 'INDEX_ID', 'DATE'], man[1].split('_')))
      subelements.extend(zip(['SEGMENT_ID', 'START_CHAR', 'END_CHAR'], man[2:]))
      subelements.append(("FULL_ID", man[1]))
      subelements.append(("ORIG_RAW_SOURCE", origline))
      subelements.append(("MD5_HASH", hashlib.md5(origline.encode('utf-8')).hexdigest()))
      subelements.append(("LRLP_TOKENIZED_SOURCE", tokline))
      subelements.append(("CDEC_TOKENIZED_SOURCE", cdectokline))
      subelements.append(("CDEC_TOKENIZED_LC_SOURCE", cdectoklcline))
      subelements.append(("LRLP_MORPH_TOKENIZED_SOURCE", morphtokline))
      subelements.append(("LRLP_MORPH_SOURCE", morphline))


      # on-demand fill of psms and anns hashes that assumes it will be used contiguously
      if fullid in psmtemp:
        psms.clear()
        data = psmtemp.pop(fullid)
        for tup in data:
          start = int(tup[2])
          end = start+int(tup[3])
          for i in xrange(start, end):
            psms[fullid][i].append(tup)

      if fullid in psms:
        # collect the annotations
        psmcoll = set()
        startchar = int(man[3])
        endchar = int(man[4])
        if endchar > len(psms[fullid]):
          endchar = None
        for i in xrange(startchar, endchar):
          slot = psms[fullid][i]
          psmcoll.update(map(tuple, slot))
        for psmitem in psmcoll:
          if psmitem[0]=='headline':
            subelements.append(("IS_HEADLINE","1"))
            continue
          if psmitem[0]=='post':
            if len(psmitem) >= 5:
              subelements.append(("AUTHOR", psmitem[4]))
              if len(psmitem) >= 6:
                subelements.append(("POST_DATE_TIME", psmitem[5]))
          else:
            sys.stderr.write("Not sure what to do with item that starts "+psmitem[0]+"\n")
            continue

      if fullid in anntemp:
        anns.clear()
        data = anntemp.pop(fullid)
        for tup in data:
          start = int(tup[2])
          end = int(tup[3])
          for i in xrange(start, end):
            anns[fullid][i].append(tup)

      if fullid in anns:

        # collect the annotations
        anncoll = set()
        startchar = int(man[3])
        endchar = min(len(anns[fullid]), int(man[4]))
        for i in xrange(startchar, endchar):
          slot = anns[fullid][i]
          anncoll.update(map(tuple, slot))
        if len(anncoll) > 0:
          ae = ET.SubElement(xroot, "ANNOTATIONS")
        for annitem in anncoll:
          se = ET.SubElement(ae, "ANNOTATION", {'task':annitem[0], 'annotation_id': annitem[4], 'start_char':annitem[2], 'end_char':annitem[3]})
          se.text=annitem[5]
          subsubs = []
          if annitem[0]=='NE':
            subsubs.append(("ENTITY_TYPE", annitem[6]))
          elif annitem[0]=='FE':
            subsubs.append(("ENTITY_TYPE", annitem[9]))
            subsubs.append(("ANNOTATION_KIND", annitem[6]))
            subsubs.append(("MENTION_TYPE", annitem[7]))
            subsubs.append(("ENTITY_ID", annitem[8]))
          elif annitem[1]=='SSA':
            se.set('pred_or_arg', annitem[6])
            subsubs.append(("ROLE", annitem[7]))
            if annitem[6] == "argument":
              subsubs.append(("PREDICATE", annitem[8]))
          else:
            sys.stderr.write("Not sure what to do with item that starts "+annitem[0]+"\n")
            continue
          for key, text in subsubs:
            sse = ET.SubElement(se, key)
            sse.text = text
      # TODO: more tokenizations, etc.
      for key, text in subelements:
        se = ET.SubElement(xroot, key)
        se.text = text
      # entity/semantic annotations in their own block
      #if fullid in anns


        
      xmlstr = ET.tostring(xroot, pretty_print=True, encoding='utf-8', xml_declaration=False)
      outfile.write(xmlstr)
  # TODO /corpus/document
  # TODO: verify empty psm
  for key in psmtemp.keys():
    print "Unvisited psm: "+key
  for key in anntemp.keys():
    print "Unvisited ann: "+key
if __name__ == '__main__':
  main()
