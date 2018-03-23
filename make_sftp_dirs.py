#!/usr/bin/env python
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
from os import symlink
import tempfile
import shutil
import atexit

scriptdir = os.path.dirname(os.path.abspath(__file__))


reader = codecs.getreader('utf8')
writer = codecs.getwriter('utf8')

# http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python
import os, errno
def mkdir_p(path):
  try:
    os.makedirs(path)
  except OSError as exc: # Python >2.5
    if exc.errno == errno.EEXIST and os.path.isdir(path):
      pass
    else: raise

def forcelink(src, dst):
  try:
    os.symlink(src, dst)
  except OSError as exc: # Python >2.5
    if exc.errno == errno.EEXIST and os.path.isdir(dst):
      pass
    else: raise




def addonoffarg(parser, arg, dest=None, default=True, help="make partner-safe sftp dirs, build tarball, "):
  ''' add the switches --arg and --no-arg that set parser.arg to true/false, respectively'''
  group = parser.add_mutually_exclusive_group()
  dest = arg if dest is None else dest
  group.add_argument('--%s' % arg, dest=dest, action='store_true', default=default, help=help)
  group.add_argument('--no-%s' % arg, dest=dest, action='store_false', default=default, help="See --%s" % arg)

def main():
  parser = argparse.ArgumentParser(description="form directories for a dryrun or eval",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  addonoffarg(parser, 'debug', help="debug mode", default=False)
#  parser.add_argument("--infile", "-i", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="input file")
#  parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file")
  parser.add_argument("--tasks", "-t", nargs='+', type=str, default=['asr', 'ie', 'mt', 'sf'], help="which tasks might get done")
  parser.add_argument("--sites", "-s", nargs='+', type=str, default=['isi', 'but', 'nd', 'rpi', 'upenn', 'usc', 'uw'], help="which sites might participate")
  parser.add_argument("--langs", "-l", nargs='+', type=str, required=True, help="list of languages")
  parser.add_argument("--root", "-r", type=str, default='/sftp/guestuser/ELISA',  help="where things go")
  parser.add_argument("--persite", type=str, default='results', help='per-site tree')
  parser.add_argument("--jmist", type=str, default='JMIST', help='loc for data')
  parser.add_argument("--jmistfull", type=str, default='JMIST_FULL', help='loc for elisa team data')
  parser.add_argument("--kind", "-k", type=str, required=True, choices=['dryruns', 'evals'],  help="what kind of task is this")
  parser.add_argument("--name", "-n", type=str, required=True, help="what to call this task")




  try:
    args = parser.parse_args()
  except IOError as msg:
    parser.error(str(msg))

  workdir = tempfile.mkdtemp(prefix=os.path.basename(__file__), dir=os.getenv('TMPDIR', '/tmp'))

  def cleanwork():
    shutil.rmtree(workdir, ignore_errors=True)
  if args.debug:
    print(workdir)
  else:
    atexit.register(cleanwork)


  # make per-site-visible dirs;
  # link them to created per-kind dirs
  # first the JMIST
  for lang in args.langs:
    jmistdir=os.path.join(args.root, args.persite, args.jmist, args.kind, args.name, lang)
    print(jmistdir)
    print("Making {0}".format(jmistdir))
    mkdir_p(jmistdir)
    os.chmod(jmistdir, 0777)
    taskrefpathlist = ['..']*3+[args.persite, args.jmist, args.kind, args.name, lang]
    taskref=os.path.join(*taskrefpathlist)
    kinddir=os.path.join(args.root, args.kind, args.name, lang)
    print("Making {0} to link in {1}".format(kinddir, taskref))
    mkdir_p(kinddir)
    forcelink(taskref, os.path.join(kinddir, args.jmist))
    fulldir=os.path.join(args.root, args.kind, args.name, lang, args.jmistfull)
    print("Making {0}".format(fulldir))
    mkdir_p(fulldir)
    os.chmod(fulldir, 0777)

    # now the work spaces
    for site in args.sites:
      for task in args.tasks:
        taskdir=os.path.join(args.root, args.persite, site, args.kind, args.name, lang, task)
        print("Making {0}".format(taskdir))
        mkdir_p(taskdir)
        os.chmod(taskdir, 0777)
        taskrefpathlist = ['..']*4+[args.persite, site, args.kind, args.name, lang, task]
        taskref=os.path.join(*taskrefpathlist)
        kinddir=os.path.join(args.root, args.kind, args.name, lang, task)
        mkdir_p(kinddir)
        print("Making {0} to link in {1}".format(kinddir, taskref))
        forcelink(taskref, os.path.join(kinddir, site))

if __name__ == '__main__':
  main()
