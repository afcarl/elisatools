#!/usr/bin/env python3

import argparse
import sys
import codecs

from collections import defaultdict as dd
import re
import os.path
from lputil import Step, make_action, dirfind, mkdir_p
from subprocess import check_output, check_call, CalledProcessError
scriptdir = os.path.dirname(os.path.abspath(__file__))

def addonoffarg(parser, arg, dest=None, default=True, help="TODO"):
  ''' add the switches --arg and --no-arg that set parser.arg to true/false, respectively'''
  group = parser.add_mutually_exclusive_group()
  dest = arg if dest is None else dest
  group.add_argument('--%s' % arg, dest=dest, action='store_true', default=default, help=help)
  group.add_argument('--no-%s' % arg, dest=dest, action='store_false', default=default, help="See --%s" % arg)


def main():
  steps = []
  # Put additional steps in here. Arguments, stdin/stdout, etc. get set below

  # unpack_lrlp.sh
  steps.append(Step('unpack_lrlp.sh', call=check_output,
                    help="untars lrlp into position for further processing"))

  # gather_ephemera.py
  steps.append(Step('gather_ephemera.py',
                    help="relocates assorted bits from lrlp"))

  # extract_lexicon.py
  steps.append(Step('extract_lexicon.py',
                    help="get flat form of bilingual lexicon",
                    abortOnFail=False))

  # clean_lexicon
  steps.append(Step('clean.sh',
                    name="clean_lexicon",
                    help="wildeclean/nfkc lexicon file",
                    abortOnFail=False))

  # normalize_lexicon.py
  steps.append(Step('normalize_lexicon_tg.py', name="normalize_lexicon.py",
                    help="heuristically convert lexicon into something more machine readable",
                    abortOnFail=False))

  # relocate lexicon
  steps.append(Step('cp', progpath='/bin',
                    name="relocate_lexicon",
                    help="move the lexicon stuff into ephemera",
                    abortOnFail=False))

  # get_tweet_by_id.rb
  steps.append(Step('get_tweet_by_id.rb',
                    help="download tweets. must have twitter gem installed " \
                    "and full internet",
                    abortOnFail=False))

  steps.append(Step('ldc_tok.py',
                    help="run ldc tokenizer on tweets ",
                    abortOnFail=False))

  # extract_psm_annotation.py
  steps.append(Step('extract_psm_annotation.py',
                    help="get annotations from psm files into psm.ann",
                    abortOnFail=False))

  # extract_entity_annotation.py
  steps.append(Step('extract_entity_annotation.py',
                    help="get entity and other annotations into entity.ann",
                    abortOnFail=False))

  # extract_parallel.py
  steps.append(Step('extract_parallel.py',
                    help="get flat form parallel data"))

  steps.append(Step('filter_parallel.py',
                    help="filter parallel data to remove likely mismatches"))

  # extract_mono.py
  steps.append(Step('extract_mono.py',
                    help="get flat form mono data"))

  # extract_comparable.py
  steps.append(Step('extract_comparable.py',
                    help="get flat form comparable data"))

  stepsbyname = {}
  for step in steps:
    stepsbyname[step.name] = step

  parser = argparse.ArgumentParser(description="Process a LRLP into flat format",
                                   formatter_class= \
                                   argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--tarball", "-t", nargs='+', required=True,
                      help='path to gzipped tars for processing (all tars considered to be part of the same package). Ex: lrlp.tar.gz')
  parser.add_argument("--language", "-l", required=True,
                      help='three letter code of language. example "uzb"')
  parser.add_argument("--lexversion", "-L", default='1.5',
                      help='version of lexicon to extract (may need to create a new one)')

  parser.add_argument("--key", "-k", default=None,
                      help='decryption key for encrypted il')
  parser.add_argument("--set", "-S", default=None,
                      help='decryption set for encrypted il')
  addonoffarg(parser, "mono", help="extract mono data", default=True)
  parser.add_argument("--previous", default=None,
                      help='path to previous extraction (equivalent to one level down from root)')

  parser.add_argument("--root", "-r", default='/home/nlg-02/LORELEI/ELISA/data',
                      help='path to where the extraction will take place')
  parser.add_argument("--evalil", "-E", action='store_true', default=False, 
                      help='this is an eval il. makes expdir set0 aware')
  parser.add_argument("--expdir", "-e",
                      help='path to where the extraction is (equivalent to root/lang/expanded/lrlp). If starting at ' \
                      'step 0 this is ignored')
  parser.add_argument("--start", "-s", type=int, default=0,
                      help='step to start at')
  parser.add_argument("--stop", "-p", type=int, default=len(steps)-1,
                      help='step to stop at (inclusive)')
  parser.add_argument("--liststeps", "-x", nargs=0, action=make_action(steps),
                      help='print step list and exit')
  parser.add_argument("--ruby", default="ruby", help='path to ruby (2.1 or higher)')
  addonoffarg(parser, "swap", help="swap source/target in found data (e.g. il3)", default=False)
  try:
    args = parser.parse_args()
  except IOError as msg:
    parser.error(str(msg))
    sys.exit(2)

  if args.expdir is not None and args.start <= 0:
    sys.stderr.write \
      ("Warning: expdir is set but will be ignored and determined dynamically")
  if args.expdir is None and args.start > 0:
    sys.stderr.write \
      ("Error: must explicitly set expdir if not starting at step 0")
    sys.exit(1)

  rootdir = args.root
  language = args.language
  start = args.start
  stop = args.stop + 1
  if (args.key is None) ^ (args.set is None):
    sys.stderr.write("key (-k) and set (-S) must both be set or unset\n")
    sys.exit(1)
  # Patchups for step 0
  argstring = "-k %s -s %s" % (args.key, args.set) if args.key is not None else ""
  argstring += " -l %s -r %s %s" % (language, rootdir, ' '.join(args.tarball))
  sys.stderr.write("args for unpack lrlp are {}\n".format(argstring))
  stepsbyname["unpack_lrlp.sh"].argstring=argstring

  if start == 0:
    expdir = steps[0].run().strip().decode("utf-8")
    if args.evalil:
      expdir = os.path.join(expdir, 'set0')
    start += 1
  else:
    expdir = args.expdir
  monodir=os.path.join(expdir, 'data', 'monolingual_text')
  # what are the mono files? (needed for later)
  if args.mono and args.previous is None:
    monoindirs = dirfind(monodir, "ltf.zip")
  else:
    monoindirs = []
  # Patchups for the rest
  if stop > 0:
    # TWEET
    tweetintab = os.path.join(expdir, 'docs', 'twitter_info.tab')
    tweetdir = os.path.join(rootdir, language, 'tweet', 'rsd')
    if not os.path.exists(tweetintab):
      stepsbyname["get_tweet_by_id.rb"].disable()
      stepsbyname["ldc_tok.py"].disable()
    else:
      tweetprogpaths = []
      #for toolroot in (expdir, scriptdir): # bad ldc tools for eval
      for toolroot in (scriptdir,):
        tweetprogpaths = dirfind(os.path.join(toolroot, 'tools'), 'get_tweet_by_id.rb')
        if len(tweetprogpaths) > 0:
          break
      if len(tweetprogpaths) == 0:
        sys.stderr.write("Can't find get_tweet_by_id.rb\n")
        sys.exit(1)
      else:
        tweetprogpath = os.path.dirname(tweetprogpaths[0])
      mkdir_p(tweetdir)
      tweeterr = os.path.join(rootdir, language, 'extract_tweet.err')
      stepsbyname["get_tweet_by_id.rb"].stderr = tweeterr

      # just copy from previous or skip if no mono
      if not args.mono:
        if args.previous is None:
          stepsbyname["get_tweet_by_id.rb"].disable()
        else:
          oldtweetdir = os.path.join(args.previous, 'tweet', 'rsd') #WARNING: old versions of data won't have this structure
          stepsbyname["get_tweet_by_id.rb"].progpath = "/bin"
          stepsbyname["get_tweet_by_id.rb"].prog = "cp"
          stepsbyname["get_tweet_by_id.rb"].argstring = "-r {} {}".format(oldtweetdir, tweetdir)
      else:
        stepsbyname["get_tweet_by_id.rb"].progpath = tweetprogpath
        stepsbyname["get_tweet_by_id.rb"].argstring = tweetdir+" -l "+language
        stepsbyname["get_tweet_by_id.rb"].scriptbin = args.ruby
        if os.path.exists(tweetintab):
          stepsbyname["get_tweet_by_id.rb"].stdin = tweetintab
        else:
          stepsbyname["get_tweet_by_id.rb"].disable()

      # TOKENIZE AND RELOCATE TWEETS
      # find rb location, params file
      toxexecpaths = []
      thetoolroot = None
      for toolroot in (expdir, scriptdir):
        tokexecpaths = dirfind(os.path.join(toolroot, 'tools'), 'token_parse.rb')
        if len(tokexecpaths) > 0:
          thetoolroot = toolroot
          break
      if len(tokexecpaths) == 0:
        sys.stderr.write("Can't find token_parse.rb\n")
        sys.exit(1)
      tokexec = tokexecpaths[0]
      tokparamopts = dirfind(os.path.join(thetoolroot, 'tools'), 'yaml')
      tokparam = "--param {}".format(tokparamopts[0]) if len(tokparamopts) > 0 else ""
      lrlpdir=os.path.join(expdir, 'data', 'translation', 'from_{}'.format(language), language, 'ltf')
      # ugly: the base of the file monodir/mononame.zip; need to add it to monoindirs and just pass that base so it gets constructed
      mononame = "tweets.ltf"
      monoindirs.append(os.path.join(monodir, mononame+".zip"))
      stepsbyname["ldc_tok.py"].argstring = "--mononame {mononame} -m {monodir} --ruby {ruby} --dldir {tweetdir} --lrlpdir {lrlpdir} --exec {tokexec} {tokparam} --outfile {outfile}".format(
        monodir=monodir,
        mononame=mononame,
        ruby=args.ruby,
        tweetdir=tweetdir,
        lrlpdir=lrlpdir,
        tokexec=tokexec,
        tokparam=tokparam,
        outfile=os.path.join(rootdir, language, 'ldc_tok.stats'))
      stepsbyname["ldc_tok.py"].stderr = os.path.join(rootdir, language, 'ldc_tok.err')

    # EPHEMERA
    ephemdir = os.path.join(rootdir, language, 'ephemera')
    ephemarg = "-s {} -t {}".format(expdir, ephemdir)
    if args.previous is not None:
      ephemarg += " -o {}".format(os.path.join(args.previous, 'ephemera'))
    stepsbyname['gather_ephemera.py'].argstring = ephemarg
    ephemerr = os.path.join(rootdir, language, 'gather_ephemera.err')
    stepsbyname['gather_ephemera.py'].stderr = ephemerr

    # # LTF2RSD
    # l2rindir = os.path.join(expdir, 'data', 'translation', 'from_'+language,
    #                         'eng') # Only converts from_SRC_tweet subdir
    # stepsbyname["ltf2rsd.perl"].argstring = l2rindir
    # # l2rprogpath = os.path.join(expdir, 'tools', 'ltf2txt')
    # # stepsbyname["ltf2rsd.perl"].progpath = l2rprogpath
    # l2rerr = os.path.join(rootdir, language, 'ltf2rsd.err')
    # stepsbyname["ltf2rsd.perl"].stderr = l2rerr

    # LEXICON
    #
    # IL CHANGE
    if args.evalil:
      lexiconinfile = os.path.join(expdir, 'docs', 'categoryI_dictionary', '*.xml')
      if args.lexversion == "il6":
        lexiconinfile = os.path.join(expdir, 'docs', 'categoryI_dictionary', '*.zip')
      elif args.lexversion == "il5":
        lexiconinfile = os.path.join(expdir, 'docs', 'categoryI_dictionary', '*.txt')
    else:
      lexiconinfile = os.path.join(expdir, 'data', 'lexicon', '*.xml')
    lexiconoutdir = os.path.join(rootdir, language, 'lexicon')
    lexiconrawoutfile = os.path.join(lexiconoutdir, 'lexicon.raw')
    lexiconoutfile = os.path.join(lexiconoutdir, 'lexicon')
    lexiconnormoutfile = os.path.join(lexiconoutdir, 'lexicon.norm')

    lexiconerr = os.path.join(rootdir, language, 'extract_lexicon.err')
    lexiconcleanerr = os.path.join(rootdir, language, 'clean_lexicon.err')
    lexiconnormerr = os.path.join(rootdir, language, 'normalize_lexicon.err')
    # lexicon v1.5 for y2
    stepsbyname["extract_lexicon.py"].argstring = " -v {} -i {} -o {}".format(args.lexversion, lexiconinfile, lexiconrawoutfile)
    stepsbyname["extract_lexicon.py"].stderr = lexiconerr

    stepsbyname["clean_lexicon"].argstring = "{} {}".format(lexiconrawoutfile, lexiconoutfile)
    stepsbyname["clean_lexicon"].stderr = lexiconcleanerr

    stepsbyname["normalize_lexicon.py"].argstring = "-i %s -o %s" % \
                                                  (lexiconoutfile, lexiconnormoutfile)
    stepsbyname["normalize_lexicon.py"].stderr = lexiconnormerr


    stepsbyname["relocate_lexicon"].argstring = "-r %s %s" % (lexiconoutdir, ephemdir)

    # PSM
    # just copy from previous or skip if no mono
    psmerr = os.path.join(rootdir, language, 'extract_psm_annotation.err')
    stepsbyname["extract_psm_annotation.py"].stderr = psmerr
    psmoutpath = os.path.join(rootdir, language, 'psm.ann')
    if not args.mono:
      if args.previous is None:
        stepsbyname["extract_psm_annotation.py"].disable()
      else:
        oldpsm = os.path.join(args.previous, 'psm.ann')
        stepsbyname["extract_psm_annotation.py"].progpath = "/bin"
        stepsbyname["extract_psm_annotation.py"].prog = "cp"
        stepsbyname["extract_psm_annotation.py"].argstring = "{} {}".format(oldpsm, psmoutpath)
    else:
      psmindir = os.path.join(monodir, 'zipped', '*.psm.zip')
      stepsbyname["extract_psm_annotation.py"].argstring = "-i %s -o %s" % \
                                                           (psmindir, psmoutpath)


    # ENTITY
    entityoutpath = os.path.join(rootdir, language, 'entity.ann')
    entityerr = os.path.join(rootdir, language, 'extract_entity_annotation.err')
    stepsbyname["extract_entity_annotation.py"].argstring="-r %s -o %s -et %s" \
      % (expdir, entityoutpath, tweetdir)
    stepsbyname["extract_entity_annotation.py"].stderr = entityerr

    # PARALLEL
    paralleloutdir = os.path.join(rootdir, language, 'parallel', 'extracted')
    parallelerr = os.path.join(rootdir, language, 'extract_parallel.err')
    stepsbyname["extract_parallel.py"].argstring="--no-cdec -r %s -o %s -s %s" % \
      (expdir, paralleloutdir, language)
    stepsbyname["extract_parallel.py"].stderr = parallelerr
    if args.swap:
      stepsbyname["extract_parallel.py"].argstring += " --swap"

    filteroutdir = os.path.join(rootdir, language, 'parallel', 'filtered')
    rejectoutdir = os.path.join(rootdir, language, 'parallel', 'rejected')
    filtererr = os.path.join(rootdir, language, 'filter_parallel.err')
    stepsbyname["filter_parallel.py"].argstring="-s 2 -l %s -i %s -f %s -r %s" % \
      (language, paralleloutdir, filteroutdir, rejectoutdir)
    stepsbyname["filter_parallel.py"].stderr = filtererr

    # MONO
    # just copy from previous or skip if no mono
    monoerr = os.path.join(rootdir, language, 'extract_mono.err')
    stepsbyname["extract_mono.py"].stderr = monoerr
    if not args.mono:
      if args.previous is None:
        stepsbyname["extract_mono.py"].disable()
      else:
        oldmonodir = os.path.join(args.previous, 'mono')
        monooutdir = os.path.join(rootdir, language, 'mono')
        stepsbyname["extract_mono.py"].progpath = "/bin"
        stepsbyname["extract_mono.py"].prog = "cp"
        stepsbyname["extract_mono.py"].argstring = "-r {} {}".format(oldmonodir, monooutdir)
    else:
      monooutdir = os.path.join(rootdir, language, 'mono', 'extracted')
      stepsbyname["extract_mono.py"].argstring = "--no-cdec -i %s -o %s" % \
                                                 (' '.join(monoindirs), monooutdir)


    # COMPARABLE
    if os.path.exists(os.path.join(expdir, 'data', 'translation', 'comparable')):
      compoutdir = os.path.join(rootdir, language, 'comparable', 'extracted')
      comperr = os.path.join(rootdir, language, 'extract_comparable.err')
      stepsbyname["extract_comparable.py"].argstring = "-r %s -o %s -s %s" % \
                                                       (expdir, compoutdir, language)
      stepsbyname["extract_comparable.py"].stderr = comperr
    else:
      stepsbyname["extract_comparable.py"].disable()
    
    for step in steps[start:stop]:
      step.run()


  print("Done.\nExpdir is %s" % expdir)

if __name__ == '__main__':
  main()
