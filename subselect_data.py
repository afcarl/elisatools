#! /usr/bin/env python
import argparse
import sys
import codecs
from itertools import izip
from collections import defaultdict as dd
import re
import os.path
from lputil import mkdir_p
from subprocess import check_output, STDOUT, CalledProcessError
scriptdir = os.path.dirname(os.path.abspath(__file__))


def runselection(prefix, idfile, engfile, termfile, categories, remainder, sizes, filetypes, srclang, indir, outdir):
  ''' do a data selection and apply it to a set of files '''
  rankfile = os.path.join(outdir, "%s.ranks" % prefix)
  countfile = os.path.join(outdir, "%s.counts" % prefix)
  catfile = os.path.join(outdir, "%s.cats" % prefix)
  try:
    cmd_output=check_output("%s/rankdocuments.py -i %s -d %s -t %s -o %s" % 
                            (scriptdir, engfile, idfile, termfile, rankfile), stderr=STDOUT, shell=True)
    cmd_output=check_output("%s/countwords.py -i %s -d %s -o %s" % 
                            (scriptdir, engfile, idfile, countfile), stderr=STDOUT, shell=True)
    cmd_output=check_output("%s/roundrobin.py -w %s -f %s -s %s -c %s -r %s -o %s" % 
                            (scriptdir, countfile, rankfile, sizes, categories, remainder, catfile), stderr=STDOUT, shell=True)
    # TODO: also do manifest here!!
    for filetype in filetypes:
      for flang in [srclang, 'eng']:
        cmd_output=check_output("%s/categorize.py -i %s/%s/%s.%s.%s.flat -d %s -c %s -p %s" % 
                                (scriptdir, indir, filetype, prefix, filetype, flang, idfile, catfile, outdir), stderr=STDOUT, shell=True)
  except CalledProcessError as exc:
    print "Status : FAIL", exc.returncode, exc.output
    sys.exit(1)

def main():
  parser = argparse.ArgumentParser(description="Make dataset selections for experimentation",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--indir", "-i", help="location of parallel data")
  parser.add_argument("--language", "-l", help="source language three digit code")
  parser.add_argument("--minimum", "-m", default=100, help="minimum number of words per subselection")
  parser.add_argument("--sizes", "-s", nargs='+', type=int, help="list of sizes desired in each category")
  parser.add_argument("--categories", "-c", nargs='+', help="list of categories. Must match sizes")
  parser.add_argument("--termfile", "-t", help="file of desired terms, one per line")
  parser.add_argument("--remainder", "-r", default="train", help="remainder category. Should be a new category")



  try:
    args = parser.parse_args()
  except IOError, msg:
    parser.error(str(msg))

#  reader = codecs.getreader('utf8')
#  writer = codecs.getwriter('utf8')
#  outfile = writer(args.outfile)

  indir = args.indir
  origsizes = args.sizes
  termfile = args.termfile
  # TODO: find these?
  # doc = keep full docs together  (can detect this by counting number of unique docs)
  docprefixes = ["found.generic", "fromsource.generic", "fromsource.tweet"]
  nodocprefixes = ["fromtarget.elicitation", "fromtarget.phrasebook"]

  # TODO: find these
  filetypes = ["morph", "morph-tokenized", "original", "pos", "tokenized"]

  extractpath = os.path.join(indir, 'extracted')
  origpath = os.path.join(extractpath, 'original')
  outpath = os.path.join(indir, 'splits')
  mkdir_p(outpath)

  # number of words in each file
  fullsizes = {}
  adjsizes = {}
  sizesum = 0.0
  for preflist in [docprefixes, nodocprefixes]:
    for prefix in preflist:
      # don't deal with it more if there's nothing in the manifest
      manfile = os.path.join(extractpath, "%s.eng.manifest" % prefix)
      if (not os.path.exists(manfile)) or os.path.getsize(manfile) == 0:
        preflist.remove(prefix)
  for prefix in docprefixes+nodocprefixes:      
    engfile=os.path.join(origpath, "%s.original.eng.flat" % prefix)
    prefsize = int(check_output("wc -w %s" % engfile, shell=True).split(' ')[0])
    fullsizes[prefix] = prefsize
    sizesum +=prefsize
  # adjust size split by proportion, with minimum
  for prefix in docprefixes+nodocprefixes:
    mult = fullsizes[prefix]/sizesum
    adjsizes[prefix] = map(lambda x: max(args.minimum, int(mult*x)), origsizes)

  # doc-based processing
  catlist = ' '.join(args.categories)
  for prefix in docprefixes:
    idfile = os.path.join(outpath, "%s.ids" % prefix)
    manfile = os.path.join(extractpath, "%s.eng.manifest" % prefix)
    try:
      check_output("cut -f2 %s > %s" % (manfile, idfile), stderr=STDOUT, shell=True)
    except CalledProcessError as exc:
      print "Status : FAIL", exc.returncode, exc.output
    engfile=os.path.join(origpath, "%s.original.eng.flat" % prefix)
    sizelist = ' '.join(map(str, adjsizes[prefix])) 
    runselection(prefix, idfile, engfile, termfile, catlist, args.remainder, sizelist, filetypes, args.language, extractpath, outpath)
if __name__ == '__main__':
  main()
