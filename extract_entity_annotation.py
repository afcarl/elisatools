#!/usr/bin/env python3
#-*- coding: utf-8 -*-
import sys
# utilities for dealing with LRLPs
import argparse
import codecs
import os
import re
import os.path
from zipfile import ZipFile as zf
import xml.etree.ElementTree as ET
import gzip
import os
scriptdir = os.path.dirname(os.path.abspath(__file__))
import datetime
from lputil import funornone, is_sn

# Scrape annotation files for full/simple entities and semantic annotation

# http://stackoverflow.com/questions/2865278/in-python-how-to-find-all-the-files
# -under-a-directory-including-the-files-in-s
def recursive_file_gen(mydir):
  for root, dirs, files in os.walk(mydir):
    for file in files:
      yield os.path.join(root, file)

def main():
  import codecs
  parser = argparse.ArgumentParser(description="Extract and print laf annotat" \
                                   "ion data from LRLP in a form that is amen" \
                                   "able to insertion into future xml",
                                   formatter_class= \
                                   argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--rootdir", "-r", default=".", help="root lrlp dir")
  # parser.add_argument("--outfile", "-o",
  #                     type=argparse.FileType('w'), default=sys.stdout,
  #                     help="where to write extracted semantic info")
  parser.add_argument("--outfile", "-o", help="where to write")
  parser.add_argument("--extwtdir", "-et", default = None, help="extracted tweet rsd files dir")

  try:
    args = parser.parse_args()
  except IOError as msg:
    parser.error(str(msg))

  outfile = open(args.outfile, 'w')
  twtdir = args.extwtdir
  anndir = os.path.join(args.rootdir, 'data', 'annotation')
  if not os.path.exists(anndir):
    sys.stderr.write("No annotation directory found\n")
    sys.exit(0)
  if twtdir is not None and not os.path.exists(twtdir):
    sys.stderr.write("Warning: no {}\n".format(twtdir))
    twtdir = None
  # print anndir
  for annfile in recursive_file_gen(anndir):
    if annfile.endswith("laf.xml") and \
       not os.path.basename(annfile).startswith("."):
      try:
        xobj = ET.parse(annfile)
      except:
        sys.stderr.write("Problem parsing "+annfile+"\n")
        continue

      for xdoc in xobj.findall("DOC"):
        docid = xdoc.get("id")
        if docid.startswith('doc-'): # In NPC annotation, LDC uses "doc-n"
                                     # instead of original docid
            docid = os.path.basename(annfile).replace('.laf.xml', '')
        if is_sn(docid) and twtdir is not None: # No string head for TWT, need rsd file
            if not os.path.isfile('%s/%s.rsd.txt' % (twtdir, docid)):
                continue

        # Store all annotations by id. if they have an extent, spit them out.
        # if no extent, check they are entities; nothing else should be
        # extent-free PREDICATE, ENTITY, and PHRASE are cross references to ids;
        # for ENTITY the core type is copied, for everything else just the cross
        # reference
        annset = {}
        for xann in xdoc.findall("ANNOTATION"):
          annid = xann.get("id")
          if annid.startswith('doc-'):
              annid = re.sub('doc-\d+', docid, annid)
          annset[annid] = xann
          anntask = xann.get("task")
          if xann.find("EXTENT") is None:
            if anntask != "FE" and anntask != "SSA":
              sys.stderr.write("Warning: extent-free non-full annotation in " \
                               +annfile+": "+ET.tostring(xann)+"\n")
            continue
          # map aberrant type
          if anntask == "NPchunk":
            anntask = "NPC"
          xextent = xann.find('EXTENT')
          try:
            if is_sn(docid) and twtdir is not None: # No string head for TWT
              strhead = xextent.text
              tweet = open('%s/%s.rsd.txt' % (twtdir, docid)).read()
              beg = int(xextent.get("start_char"))
              end = int(xextent.get("end_char"))
              # but don't go negative
              if beg < 0 or end > len(tweet):
                sys.stderr.write(annfile+" Bad offsets: can't do %d, %d on %s\n" % (beg, end, docid))
                continue
              strhead = tweet[beg:end+1]
              tup = [anntask, docid, str(int(xextent.get("start_char"))) or "None",
                     xextent.get("end_char") or "None", annid or "None",
                     strhead or "None"]
            else:
              tup = [anntask, docid, str(int(xextent.get("start_char"))) or "None",
                     xextent.get("end_char") or "None", annid or "None",
                     xextent.text or "None"]
          except:
            sys.stderr.write("Trouble at %s in %s should be investigated\n" % (docid,annfile))
            continue

          if anntask == "NE": # Simple ne annotation
            # old style: in attributes. new style: in tag
            if "type" in xann.keys():
              tup.append(xann.get("type"))
            else:
              tup.append(funornone(xann.find("TAG"), lambda x: x.text))
          elif (anntask == "NPC" or anntask=="NPchunk"): # NP chunking
            # old style: in attributes. new style: in tag
            if "type" in xann.keys():
              tup.append(xann.get("type"))
            else:
              tup.append(funornone(xann.find("TAG"), lambda x: x.text))
          else: # Everything else has category/tag style
            try:
              tup.append(funornone(xann.find("CATEGORY"), lambda x: x.text))
              tup.append(funornone(xann.find("TAG"), lambda x: x.text))
              if (anntask == "FE"):
                if xann.find("ENTITY") is not None:
                  eid = xann.find("ENTITY").get("entity_id")
                  tup.append(eid)
                  tup.append(annset[eid].find("TAG").text if \
                             annset[eid].find("TAG") is not None else "NONE")
                elif xann.find("PHRASE") is not None:
                  tup.append(xann.find("PHRASE").get("phrase_id"))
                else:
                  sys.stderr("Expected ENTITY or PHRASE at "\
                             +annfile+"; "+ET.tostring(xann))
                  continue
              elif (anntask == "SSA"):
                if xann.find("PREDICATE") is not None:
                  tup.append(xann.find("PREDICATE").get("predicate_id"))
              else:
                sys.stderr.write(annfile+": Don't know how to process "\
                                 +anntask+"\n")
                continue
            except:
              print(annfile)
              print(ET.tostring(xann))
              raise
          try:
              outfile.write("\t".join(map(str,tup))+"\n")
          except UnicodeDecodeError:
              sys.stderr.write("Warning: Unknown encoding %s:%s-%s\n" % \
                               (tup[4], tup[2], tup[3]))

if __name__ == '__main__':
  main()
