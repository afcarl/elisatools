#!/usr/bin/env python3

import argparse
import os.path
import re
import sys

from lputil import Step, make_action

script_dir = os.path.dirname(os.path.abspath(__file__))


def addonoffarg(parser, arg, dest=None, default=True, help="TODO"):
    ''' add the switches --arg and --no-arg that set parser.arg to true/false, respectively'''
    group = parser.add_mutually_exclusive_group()
    dest = arg if dest is None else dest
    group.add_argument('--%s' % arg, dest=dest, action='store_true', default=default, help=help)
    group.add_argument('--no-%s' % arg, dest=dest, action='store_false', default=default, help="See --%s" % arg)


def make_steps():
    steps = []
    # make_mono_release.py
    steps.append(Step('make_mono_release.py', help="package mono flat data"))

    # package up audio and ephemera
    steps.append(Step('make_tarball.py', name="tar-ephemera", help="package ephemera"))

    # make_parallel_release.py
    for i in ('train', 'dev', 'test', 'syscomb', 'setE', 'rejected'):
        steps.append(Step('make_parallel_release.py', name="parallel-{}".format(i),
                          help="package parallel flat %s data" % i, disabled=True))

    # using make_mono to do comparable
    steps.append(Step('make_mono_release.py', name="comparable-src", help="package src side of comparable data"))

    steps.append(Step('make_mono_release.py', name="comparable-trg", help="package trg side of comparable data"))

    # package up everything
    steps.append(Step('make_tarball.py', name="tar-all", help="final package"))

    steps_by_name = dict((s.name, s) for s in steps)
    return steps, steps_by_name


def parse_args(steps):
    parser = argparse.ArgumentParser(description="Process a flattened LRLP into xml tarballed release format",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--language", "-l", default='uzb', help='three letter code of language')
    parser.add_argument("--version", "-v", type=int, default=1, help='version name of release')
    parser.add_argument("--year", "-yr", type=int, default=1, help='year of release')
    parser.add_argument("--part", "-pt", type=int, default=1, help='part of release')
    parser.add_argument("--splits", default='splits', help='where to look for prepared train/dev/test splits')
    parser.add_argument("--sets", "-S", nargs='+', default=['syscomb', 'test', 'dev'], type=str,
                        help="list of sets to make (in addition to train, rejected)")
    addonoffarg(parser, "mono", help="include mono data", default=True)
    parser.add_argument("--root", "-r", help='path to where the flat extraction is/output belongs')
    parser.add_argument("--start", "-s", type=int, default=0, help='step to start at')
    parser.add_argument("--stop", "-p", type=int, default=len(steps) - 1, help='step to stop at (inclusive)')
    parser.add_argument("--liststeps", "-x", nargs=0, action=make_action(steps), help='print step list and exit')
    try:
        return parser.parse_args()
    except IOError as msg:
        parser.error(str(msg))
        sys.exit(1)


def main():
    steps, stepsbyname = make_steps()
    args = parse_args(steps)
    root_dir = args.root
    language = args.language
    start = args.start
    stop = args.stop + 1

    final_items = [os.path.join(script_dir, "README.format")    # READMES
                   ]

    # MONO RELEASE
    psmoutpath = os.path.join(root_dir, 'psm.ann')
    entityoutpath = os.path.join(root_dir, 'entity.ann')
    if args.mono:
        monooutdir = os.path.join(root_dir, 'mono', 'extracted')
        monoxml = os.path.join(root_dir, 'elisa.%s.y%dr%d.v%d.xml.gz' %
                               (language, args.year, args.part, args.version))
        monostatsfile = os.path.join(root_dir, 'elisa.%s.y%dr%d.v%d.stats' %
                                     (language, args.year, args.part, args.version))
        final_items.append(monoxml)
        final_items.append(monostatsfile)

        paradir = os.path.join(root_dir, 'parallel')
        manarg = ' '.join([re.sub('.manifest', '', f)
                           for f in os.listdir(monooutdir) if re.match('(.+)\.manifest', f)])
        monoerr = os.path.join(root_dir, 'make_mono_release.err')
        stepsbyname["make_mono_release.py"].argstring = " --no-ext -r %s -l %s -c %s -s %s" % \
                                                        (monooutdir, language, manarg, monostatsfile)
        if os.path.exists(entityoutpath):
            stepsbyname["make_mono_release.py"].argstring += (" -a " + entityoutpath)
        if os.path.exists(psmoutpath):
            stepsbyname["make_mono_release.py"].argstring += (" -p " + psmoutpath)
        stepsbyname["make_mono_release.py"].argstring += (" --paradir %s | gzip > %s" % (paradir, monoxml))
        stepsbyname["make_mono_release.py"].stderr = monoerr
    else:
        stepsbyname["make_mono_release.py"].disable()

    # EPHEMERA PACKAGE
    ephemerapack = os.path.join(root_dir, 'elisa.%s.additional.y%dr%d.v%d.tgz' %
                                (language, args.year, args.part, args.version))
    final_items.append(ephemerapack)
    stepsbyname["tar-ephemera"].argstring = "-p additional -i %s -o %s" %\
                                            (os.path.join(root_dir, 'ephemera', '*'), ephemerapack)
    stepsbyname["tar-ephemera"].stderr = os.path.join(root_dir, 'tar_ephemera.err')

    # PARALLEL RELEASES
    sets = ['train', 'rejected'] + args.sets
    for i in sets:
        stepsbyname["parallel-%s" % i].enable()
        if i == "rejected":
            paralleloutdir = os.path.join(root_dir, 'parallel', i)
        else:
            paralleloutdir = os.path.join(root_dir, 'parallel', args.splits, i)
        parallelxml = os.path.join(root_dir, 'elisa.%s-eng.%s.y%dr%d.v%d.xml.gz' %
                                   (language, i, args.year, args.part, args.version))
        statsfile = os.path.join(root_dir, 'elisa.%s-eng.%s.y%dr%d.v%d.stats' %
                                 (language, i, args.year, args.part, args.version))
        final_items.append(statsfile)
        if i != "setE":
            final_items.append(parallelxml)
        parallelerr = os.path.join(root_dir, 'make_parallel_release_%s.err' % i)
        pmanarg = ' '.join([re.sub('.eng.manifest', '', f)
                            for f in os.listdir(paralleloutdir) if re.match('(.+)\.eng.manifest', f)])
        extra = "-e" if i == "setE" else ""
        stepsbyname["parallel-%s" % i].argstring =\
            "-r %s -l %s -c %s -s %s" % (paralleloutdir, language, pmanarg, statsfile)
        if os.path.exists(entityoutpath):
            stepsbyname["parallel-%s" % i].argstring += (" -a " + entityoutpath)
        if os.path.exists(psmoutpath):
            stepsbyname["parallel-%s" % i].argstring += (" -p " + psmoutpath)
        stepsbyname["parallel-%s" % i] \
            .argstring += (" %s | gzip > %s" % (extra, parallelxml))
        stepsbyname["parallel-%s" % i].stderr = parallelerr

    # COMPARABLE RELEASES
    cmpoutdir = os.path.join(root_dir, 'comparable', 'extracted')
    if os.path.exists(cmpoutdir):
        cmpsrcxml = os.path.join(root_dir, 'elisa.comparable.%s.y%dr%d.v%d.xml.gz' %
                                 (language, args.year, args.part, args.version))
        cmpsrcstatsfile = os.path.join(root_dir, 'elisa.comparable.%s.y%dr%d.v%d.stats' %
                                       (language, args.year, args.part, args.version))
        cmptrgxml = os.path.join(root_dir, 'elisa.comparable.eng.y%dr%d.v%d.xml.gz' %
                                 (args.year, args.part, args.version))
        cmptrgstatsfile = os.path.join(root_dir, 'elisa.comparable.eng.y%dr%d.v%d.stats' %
                                       (args.year, args.part, args.version))
        final_items.extend([cmpsrcxml, cmptrgxml, cmpsrcstatsfile, cmptrgstatsfile])
        stepsbyname["comparable-src"].argstring =\
            "--direction comparable --no-ext -r %s -l %s -c %s -s %s | gzip > %s" %\
            (cmpoutdir, language, language, cmpsrcstatsfile, cmpsrcxml)
        stepsbyname["comparable-src"].stderr = os.path.join(root_dir, 'make_comparable_%s_release.err' % language)
        stepsbyname["comparable-trg"].argstring = "--direction comparable --exttokdir agile-tokenized " \
                                                  "--exttokprefix AGILE -r %s -l eng -c eng -s %s | gzip > %s" % \
                                                  (cmpoutdir, cmptrgstatsfile, cmptrgxml)
        stepsbyname["comparable-trg"].stderr = os.path.join(root_dir, 'make_comparable_eng_release.err')
        # TODO: psm/entity info in comparable?
    else:
        stepsbyname["comparable-src"].disable()
        stepsbyname["comparable-trg"].disable()
    # FINAL PACKAGE
    finalpack = os.path.join(root_dir, 'elisa.%s.package.y%dr%d.v%d' % \
                             (language, args.year, args.part, args.version))
    if not args.mono:
        finalpack += ".nomono"
    finalpack += ".tgz"

    finalpackprefix = os.path.basename(finalpack)[:-4]
    stepsbyname["tar-all"].argstring = "-p %s -i %s -o %s" % \
                                       (finalpackprefix, ' '.join(final_items), finalpack)

    for step in steps[start:stop]:
        print("running {}, {}, {}, {}, {}".format(step.prog, step.name, step.scriptbin, step.progpath, step.call))
        step.run()

    print("Done")


if __name__ == '__main__':
    main()
