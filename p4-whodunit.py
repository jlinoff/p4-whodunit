#!/bin/env python
'''
This script (p4-whodunit.py) will analyze a perforce depot file to
determine and report who changed each line of code. It is useful for
tracking down recent changes that might have caused a problem.

See the interactive help (-h) for details.

LICENSE (MIT Open Source)

Copyright (c) 2015 Joe Linoff

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
import datetime
import inspect
import math
import os
import re
import subprocess
import sys
import threading
import time


VERSION = '1.0'
VERBOSE = 0


def _msg(msg, prefix, level=2, ofp=sys.stdout):
    '''
    Display a simple information message with context information.
    '''
    frame = inspect.stack()[level]
    file_name = os.path.basename(frame[1])
    lineno = frame[2]
    now = datetime.datetime.now()
    fnl = '%s:%d' % (file_name, lineno)
    xprefix = '%s: %s %-12s ' % (prefix, now.strftime('%Y-%m-%d %H:%M:%S'), fnl)
    ofp.write(xprefix + str(msg) + '\n')


def info(msg, level=1, ofp=sys.stdout):
    '''
    Display a simple information message with context information.
    '''
    _msg(prefix='INFO', msg=msg, level=level+1, ofp=ofp)


def vinfo(msg, level=1, ofp=sys.stdout):
    '''
    Display a simple information message with context information.
    '''
    if VERBOSE:
        _msg(prefix='INFO', msg=msg, level=level+1, ofp=ofp)


def v2info(msg, level=1, ofp=sys.stdout):
    '''
    Display a simple information message with context information.
    '''
    if VERBOSE > 1:
        _msg(prefix='INFO', msg=msg, level=level+1, ofp=ofp)


def err(msg, level=1, ofp=sys.stdout, exitcode=1):
    '''
    Display a simple information message with context information.
    '''
    _msg(prefix='ERROR', msg=msg, level=level+1, ofp=ofp)
    sys.exit(exitcode)


def _system(cmd):
    '''
    Execute a system command and return the output and status.
    '''
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            shell=True)
    stdout, _ = proc.communicate()
    return proc.returncode, stdout  # pylint: disable=E1101


def system(cmd):
    '''
    Execute a system command and return the output and status.
    '''
    ret, out = _system(cmd)
    if ret != 0:
        err('command failed: "%s"' % (cmd))
    return ret, out


def _help():
    '''
    help
    '''
    prog = os.path.basename(sys.argv[0])
    sys.stdout.write('''
USAGE
    %s [OPTIONS] <file> [<file>]*

DESCRIPTION
    Display the name(s) of people who changed each line of code in a
    file or a perforce path.

    The format of the output is each line of the file. The first column
    is the line number. The second column is the changelist and person
    (<cl>@<name>) that created the line. The third column is an ellipse
    (...) if there is a fourth column. The fourth column is the
    changelist and name of who deleted the line. The fifth column is
    the separator ("|" line is present, "-" line was deleted). The
    sixth column is the text of the line.

    Here is an example:

      $ %s //depot/dev/proj1/lib1/src/file1.cc
      .
      .
      275 11547@bigbob                      |    auto up1 = make_unique(Thing);
        - 11547@bigbob ... 363442@jlinoff   - 
      ^   ^     ^      ^   ^                ^    ^
      |   |     |      |   |                |    +--- col 6 - source line
      |   |     |      |   |                +-------- col 5 - separator (|, -)
      |   |     |      |   +------------------------- col 4 - who deleted it
      |   |     |      +----------------------------- col 3 - ellipses
      |   +------------------------------------------ col 2 - who deleted it
      +---------------------------------------------- col 1 - line number or dash (deleted)

    The first line is one that is currently present. The second line
    was created by mtennant and deleted by jlinoff.

    Note that you if you are in a sandbox you can simply specify the
    file as follows:

      $ %s proj1/lib1/src/file1.cc

OPTIONS
    -h, --help          This help message.

    -v, --verbose       Increase the level of verbosity.

    -V, --version       Print the version number and exit.

EXAMPLES
    $ %s -h
    $ %s //depot/dev/proj1/lib1/src/file1.cc
    $ %s //depot/dev/proj1/lib1/src/file1.cc | grep -B 2 -A 5 make_unique

VERSION
  v%s

''' % (prog, prog, prog, prog, prog, prog, VERSION))
    sys.exit(0)


def getopts():
    '''
    get options
    '''
    opts = {'files': []}
    i = 1
    while i < len(sys.argv):
        opt = sys.argv[i]
        i += 1
        if opt in ['-h', '--help']:
            _help()  # help is built in
        elif opt in ['-v', '--verbose']:
            global VERBOSE  # pylint: disable=W0603
            VERBOSE += 1
        elif opt in ['-V', '--version']:
            info('v' + VERSION)
            sys.exit(0)
        else:
            opts['files'].append(opt)
    return opts


def get_owner(cln):
    '''
    get the owner by change list number
    '''
    cmd = 'p4 describe -s ' + str(cln)
    _, out = system(cmd)
    lines = out.split('\n');
    change = 0
    owner = None
    for line in lines:
        match = re.search(r'Change (\d+) by ([^@]+)@', line)
        if match:
            change = int(match.group(1))
            owner = match.group(2)
            break
    if change != cln:
        err('p4 describe record not found for %d' % (int(cln)))
    if owner is None:
        err('p4 describe record not found for %d' % (int(cln)))
    return owner


def process(ifn):
    '''
    process a file
    '''
    cmd = 'p4 -s annotate -a -i -I ' + ifn
    _, out = system(cmd)
    lines = out.split('\n');
    vinfo('file: ' + str(ifn))
    vinfo('num lines = %d' % (len(lines)))
    line = lines[0].rstrip()  # get the first line

    # Format:
    #  info: <file>#<version> - edit change <CL> (text)
    #  text: <CL>-<CL>:<code>
    #  text: <CL>-<CL>:<code>
    #  .
    #  .
    #  text: <CL>-<CL>:<code>
    #  exit: 
    #
    if lines[0].find('info:') < 0:
        err('cannot find info: record in ' + ifn)

    # There may be a trailing blank line.
    last = -1
    if lines[-1].find('exit:') < 0:
        last = -2
        if lines[-2].find('exit:') < 0:
            err('cannot find exit: record in ' + ifn)

    latest = 0
    match = re.search(r'change\s+(\d+)', lines[0])
    if match:
        latest = int(match.group(1))
    else:
        err('cannot find the latest change list number for %s\n\t%s' % (ifn, lines[0]))

    vinfo('latest change list: %d' % (latest))

    # Walk over all of the text records.
    data = []
    cl_owner = {}
    cl_to_max_digits = 1
    cl_from_max_digits = 1
    cl_to_owner_max_len = 0
    cl_from_owner_max_len = 0
    lineno = 0

    def get_cl_owner(cln):
        # get the cl owner
        if cln not in cl_owner:
            cl_owner[cln] = get_owner(cln)
        return cl_owner[cln]

    for line in lines[1:last]:
        line = line.strip()
        match = re.search(r'text:\s+(\d+)-(\d+):(.*)$', line)
        if match:
            cl_from = int(match.group(1))
            cl_to = int(match.group(2))
            text = match.group(3)

            cl_from_owner = get_cl_owner(cl_from)
            cl_to_owner = get_cl_owner(cl_to)

            rtype = 'unknown'
            owner = ''
            sep = ''

            if cl_from == latest or cl_to == latest:
                # present
                lineno += 1
                rtype = 'present'
                sep = '|'
            else:
                rtype = 'deleted'
                # who created it and who deleted it
                sep = '-'

            rec = {
                'from': cl_from,
                'from_owner': cl_from_owner,
                'lineno': lineno,
                'sep' : sep,
                'text': text,
                'to': cl_to,
                'to_owner': cl_to_owner,
                'type': rtype,
                }
            
            cl_to_max_digits = max(cl_to_max_digits, math.log10(cl_to) + 1)
            cl_from_max_digits = max(cl_from_max_digits, math.log10(cl_from) + 1)
            cl_to_owner_max_len = max(cl_to_owner_max_len, len(cl_to_owner))
            cl_from_owner_max_len = max(cl_from_owner_max_len, len(cl_from_owner))

            data.append(rec)
        else:
            err('unrecognized line in %s\n\t%s' % (ifn, line))

    print(lines[0].strip())
    lineno_digits = math.log10(lineno) + 1
    clr_len = int(cl_to_max_digits) + cl_to_owner_max_len + 1
    clr_len += int(cl_from_max_digits) + cl_from_owner_max_len + 1
    clr_len += 5
    for rec in data:
        cl_from      = rec['from']
        cl_from_name = rec['from_owner']
        cl_to        = rec['to']
        cl_to_name   = rec['to_owner']
        text         = rec['text']
        lineno       = rec['lineno']
        rtype        = rec['type']
        sep          = rec['sep']

        frec = '%d@%s' % (cl_from, cl_from_name)
        trec = '%d@%s' % (cl_to, cl_to_name)

        if rtype == 'present':
            lnum = '%*d' % (int(lineno_digits), lineno)
            clr = frec
        else:
            lnum = '%*s' % (int(lineno_digits), '-')
            clr = frec + ' ... ' + trec
        
        print('%s %-*s %s %s' % (lnum, clr_len, clr, sep, text))

    print(lines[0].strip())


def main():
    '''
    main
    '''
    opts = getopts()
    for ifn in opts['files']:
        process(ifn)


if __name__ == '__main__':
    main()
