
# The MIT License
#
# Copyright (c) 2008 Bob Farrell
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from __future__ import division, with_statement

import os
import sys
import curses
import math
import re
import time
import signal
import struct
import termios
import fcntl
import unicodedata
import errno

from locale import LC_ALL, getpreferredencoding, setlocale
from types import ModuleType

# These are used for syntax hilighting.
from pygments import format
from pygments.formatters import TerminalFormatter
from pygments.lexers import PythonLexer
from pygments.token import Token
from bpython.formatter import BPythonFormatter

# This for completion
from bpython import importcompletion

# This for config
from bpython.config import Struct

# This for keys
from bpython.keys import key_dispatch

from bpython import repl
from bpython.pager import page
import bpython.args


def log(x):
    f = open('/tmp/bpython.log', 'a')
    f.write('%s\n' % (x,))

py3 = sys.version_info[0] == 3
stdscr = None


def calculate_screen_lines(tokens, width, cursor=0):
    """Given a stream of tokens and a screen width plus an optional
    initial cursor position, return the amount of needed lines on the
    screen."""
    lines = 1
    pos = cursor
    for (token, value) in tokens:
        if token is Token.Text and value == '\n':
            lines += 1
        else:
            pos += len(value)
            lines += pos // width
            pos %= width
    return lines


class FakeStdin(object):
    """Provide a fake stdin type for things like raw_input() etc."""

    def __init__(self, interface):
        """Take the curses Repl on init and assume it provides a get_key method
        which, fortunately, it does."""

        self.encoding = getpreferredencoding()
        self.interface = interface
        self.buffer = list()

    def __iter__(self):
        return iter(self.readlines())

    def flush(self):
        """Flush the internal buffer. This is a no-op. Flushing stdin
        doesn't make any sense anyway."""

    def write(self, value):
        # XXX IPython expects sys.stdin.write to exist, there will no doubt be
        # others, so here's a hack to keep them happy
        raise IOError(errno.EBADF, "sys.stdin is read-only")

    def isatty(self):
        return True

    def readline(self, size=-1):
        """I can't think of any reason why anything other than readline would
        be useful in the context of an interactive interpreter so this is the
        only one I've done anything with. The others are just there in case
        someone does something weird to stop it from blowing up."""

        if not size:
            return ''
        elif self.buffer:
            buffer = self.buffer.pop(0)
        else:
            buffer = ''

        curses.raw(True)
        try:
            while not buffer.endswith('\n'):
                key = self.interface.get_key()
                if key in [curses.erasechar(), 'KEY_BACKSPACE']:
                    y, x = self.interface.scr.getyx()
                    if buffer:
                        self.interface.scr.delch(y, x - 1)
                        buffer = buffer[:-1]
                    continue
                elif key == chr(4) and not buffer:
                    # C-d
                    return ''
                elif (key != '\n' and
                    (len(key) > 1 or unicodedata.category(key) == 'Cc')):
                    continue
                sys.stdout.write(key)
# Include the \n in the buffer - raw_input() seems to deal with trailing
# linebreaks and will break if it gets an empty string.
                buffer += key
        finally:
            curses.raw(False)

        if size > 0:
            rest = buffer[size:]
            if rest:
                self.buffer.append(rest)
            buffer = buffer[:size]

        if py3:
            return buffer
        else:
            return buffer.encode(getpreferredencoding())

    def read(self, size=None):
        if size == 0:
            return ''

        data = list()
        while size is None or size > 0:
            line = self.readline(size or -1)
            if not line:
                break
            if size is not None:
                size -= len(line)
            data.append(line)

        return ''.join(data)

    def readlines(self, size=-1):
        return list(iter(self.readline, ''))

DO_RESIZE = False

# TODO:
#
# Tab completion does not work if not at the end of the line.
#
# Numerous optimisations can be made but it seems to do all the lookup stuff
# fast enough on even my crappy server so I'm not too bothered about that
# at the moment.
#
# The popup window that displays the argspecs and completion suggestions
# needs to be an instance of a ListWin class or something so I can wrap
# the addstr stuff to a higher level.
#


def DEBUG(s):
    """This shouldn't ever be called in any release of bpython, so
    beat me up if you find anything calling it."""
    open('/tmp/bpython-debug', 'a').write("%s\n" % (str(s), ))


def get_color(config, name):
    return colors[config.color_scheme[name].lower()]


def get_colpair(config, name):
    return curses.color_pair(get_color(config, name) + 1)


def make_colors(config):
    """Init all the colours in curses and bang them into a dictionary"""

    # blacK, Red, Green, Yellow, Blue, Magenta, Cyan, White, Default:
    c = {
        'k': 0,
        'r': 1,
        'g': 2,
        'y': 3,
        'b': 4,
        'm': 5,
        'c': 6,
        'w': 7,
        'd': -1,
    }
    for i in range(63):
        if i > 7:
            j = i // 8
        else:
            j = c[config.color_scheme['background']]
        curses.init_pair(i + 1, i % 8, j)

    return c


class CLIInteraction(repl.Interaction):
    def __init__(self, config, statusbar=None):
        repl.Interaction.__init__(self, config, statusbar)

    def confirm(self, q):
        """Ask for yes or no and return boolean"""
        try:
            reply = self.statusbar.prompt(q)
        except ValueError:
            return False

        return reply.lower() in ('y', 'yes')


    def notify(self, s, n=10):
        return self.statusbar.message(s, n)

    def file_prompt(self, s):
        return self.statusbar.prompt(s)


class CLIRepl(repl.Repl):

    def __init__(self, scr, interp, statusbar, config, idle=None):
        repl.Repl.__init__(self, interp, config)
        self.interp.writetb = self.writetb
        self.scr = scr
        self.stdout_hist = ''
        self.list_win = newwin(get_colpair(config, 'background'), 1, 1, 1, 1)
        self.cpos = 0
        self.do_exit = False
        self.f_string = ''
        self.idle = idle
        self.in_hist = False
        self.paste_mode = False
        self.last_key_press = time.time()
        self.s = ''
        self.statusbar = statusbar
        self.formatter = BPythonFormatter(config.color_scheme)
        self.interact = CLIInteraction(self.config, statusbar=self.statusbar)

    def addstr(self, s):
        """Add a string to the current input line and figure out
        where it should go, depending on the cursor position."""
        if not self.cpos:
            self.s += s
        else:
            l = len(self.s)
            self.s = self.s[:l - self.cpos] + s + self.s[l - self.cpos:]

        self.complete()

    def atbol(self):
        """Return True or False accordingly if the cursor is at the beginning
        of the line (whitespace is ignored). This exists so that p_key() knows
        how to handle the tab key being pressed - if there is nothing but white
        space before the cursor then process it as a normal tab otherwise
        attempt tab completion."""

        return not self.s.lstrip()

    def bs(self, delete_tabs=True):
        """Process a backspace"""

        y, x = self.scr.getyx()

        if not self.s:
            return

        if x == self.ix and y == self.iy:
            return

        n = 1

        self.clear_wrapped_lines()

        if not self.cpos:
# I know the nested if blocks look nasty. :(
            if self.atbol() and delete_tabs:
                n = len(self.s) % self.config.tab_length
                if not n:
                    n = self.config.tab_length

            self.s = self.s[:-n]
        else:
            self.s = self.s[:-self.cpos - 1] + self.s[-self.cpos:]

        self.print_line(self.s, clr=True)

        return n

    def bs_word(self):
        pos = len(self.s) - self.cpos - 1
# First we delete any space to the left of the cursor.
        while pos >= 0 and self.s[pos] == ' ':
            pos -= self.bs()
# Then we delete a full word.
        while pos >= 0 and self.s[pos] != ' ':
            pos -= self.bs()

    def check(self):
        """Check if paste mode should still be active and, if not, deactivate
        it and force syntax highlighting."""

        if (self.paste_mode
            and time.time() - self.last_key_press > self.config.paste_time):
            self.paste_mode = False
            self.print_line(self.s)

    def clear_current_line(self):
        """Called when a SyntaxError occured in the interpreter. It is
        used to prevent autoindentation from occuring after a
        traceback."""
        repl.Repl.clear_current_line(self)
        self.s = ''

    def clear_wrapped_lines(self):
        """Clear the wrapped lines of the current input."""
        # curses does not handle this on its own. Sad.
        height, width = self.scr.getmaxyx()
        max_y = min(self.iy + (self.ix + len(self.s)) // width + 1, height)
        for y in xrange(self.iy + 1, max_y):
            self.scr.move(y, 0)
            self.scr.clrtoeol()

    def complete(self, tab=False):
        if self.paste_mode and self.list_win_visible:
            self.scr.touchwin()

        if self.paste_mode:
            return

        if self.list_win_visible and not self.config.auto_display_list:
            self.scr.touchwin()
            self.list_win_visible = False
            return

        if self.config.auto_display_list or tab:
            self.list_win_visible = repl.Repl.complete(self, tab)
            if self.list_win_visible:
                try:
                    self.show_list(self.matches, self.argspec)
                except curses.error:
                    # XXX: This is a massive hack, it will go away when I get
                    # cusswords into a good enough state that we can start
                    # using it.
                    self.list_win.border()
                    self.list_win.refresh()
                    self.list_win_visible = False
            if not self.list_win_visible:
                self.scr.redrawwin()
                self.scr.refresh()

    def clrtobol(self):
        """Clear from cursor to beginning of line; usual C-u behaviour"""
        self.clear_wrapped_lines()

        if not self.cpos:
            self.s = ''
        else:
            self.s = self.s[-self.cpos:]

        self.print_line(self.s, clr=True)
        self.scr.redrawwin()
        self.scr.refresh()

    def current_line(self):
        """Return the current line."""
        return self.s

    def cut_to_buffer(self):
        """Clear from cursor to end of line, placing into cut buffer"""
        self.cut_buffer = self.s[-self.cpos:]
        self.s = self.s[:-self.cpos]
        self.cpos = 0
        self.print_line(self.s, clr=True)
        self.scr.redrawwin()
        self.scr.refresh()

    def cw(self):
        """Return the current word, i.e. the (incomplete) word directly to the
        left of the cursor"""

        if self.cpos:
# I don't know if autocomplete should be disabled if the cursor
# isn't at the end of the line, but that's what this does for now.
            return

        l = len(self.s)

        if (not self.s or
            (not self.s[l - 1].isalnum() and
             self.s[l - 1] not in ('.', '_'))):
            return

        i = 1
        while i < l + 1:
            if not self.s[-i].isalnum() and self.s[-i] not in ('.', '_'):
                break
            i += 1
        return self.s[-i + 1:]

    def delete(self):
        """Process a del"""
        if not self.s:
            return

        if self.mvc(-1):
            self.bs(False)

    def echo(self, s, redraw=True):
        """Parse and echo a formatted string with appropriate attributes. It
        uses the formatting method as defined in formatter.py to parse the
        srings. It won't update the screen if it's reevaluating the code (as it
        does with undo)."""
        if not py3 and isinstance(s, unicode):
            s = s.encode(getpreferredencoding())

        a = get_colpair(self.config, 'output')
        if '\x01' in s:
            rx = re.search('\x01([A-Za-z])([A-Za-z]?)', s)
            if rx:
                fg = rx.groups()[0]
                bg = rx.groups()[1]
                col_num = self._C[fg.lower()]
                if bg and bg != 'I':
                    col_num *= self._C[bg.lower()]

                a = curses.color_pair(int(col_num) + 1)
                if bg == 'I':
                    a = a | curses.A_REVERSE
                s = re.sub('\x01[A-Za-z][A-Za-z]?', '', s)
                if fg.isupper():
                    a = a | curses.A_BOLD
        s = s.replace('\x03', '')
        s = s.replace('\x01', '')

        # Replace NUL bytes, as addstr raises an exception otherwise
        s = s.replace('\0', '')
        # Replace \r\n bytes, as addstr remove the current line otherwise
        s = s.replace('\r\n', '\n')

        self.scr.addstr(s, a)

        if redraw and not self.evaluating:
            self.scr.refresh()

    def end(self, refresh=True):
        self.cpos = 0
        h, w = gethw()
        y, x = divmod(len(self.s) + self.ix, w)
        y += self.iy
        self.scr.move(y, x)
        if refresh:
            self.scr.refresh()

        return True

    def hbegin(self):
        """Replace the active line with first line in history and
        increment the index to keep track"""
        self.cpos = 0
        self.clear_wrapped_lines()
        self.rl_history.enter(self.s)
        self.s = self.rl_history.first()
        self.print_line(self.s, clr=True)

    def hend(self):
        """Same as hbegin() but, well, forward"""
        self.cpos = 0
        self.clear_wrapped_lines()
        self.rl_history.enter(self.s)
        self.s = self.rl_history.last()
        self.print_line(self.s, clr=True)

    def back(self):
        """Replace the active line with previous line in history and
        increment the index to keep track"""

        self.cpos = 0
        self.clear_wrapped_lines()
        self.rl_history.enter(self.s)
        self.s = self.rl_history.back()
        self.print_line(self.s, clr=True)

    def fwd(self):
        """Same as back() but, well, forward"""

        self.cpos = 0
        self.clear_wrapped_lines()
        self.rl_history.enter(self.s)
        self.s = self.rl_history.forward()
        self.print_line(self.s, clr=True)

    def get_key(self):
        key = ''
        while True:
            try:
                key += self.scr.getkey()
                if not py3:
                    key = key.decode(getpreferredencoding())
                self.scr.nodelay(False)
            except UnicodeDecodeError:
# Yes, that actually kind of sucks, but I don't see another way to get
# input right
                self.scr.nodelay(True)
            except curses.error:
# I'm quite annoyed with the ambiguity of this exception handler. I previously
# caught "curses.error, x" and accessed x.message and checked that it was "no
# input", which seemed a crappy way of doing it. But then I ran it on a
# different computer and the exception seems to have entirely different
# attributes. So let's hope getkey() doesn't raise any other crazy curses
# exceptions. :)
                self.scr.nodelay(False)
                # XXX What to do here? Raise an exception?
                if key:
                    return key
            else:
                t = time.time()
                self.paste_mode = (
                    t - self.last_key_press <= self.config.paste_time
                )
                self.last_key_press = t
                return key
            finally:
                if self.idle:
                    self.idle(self)

    def get_line(self):
        """Get a line of text and return it
        This function initialises an empty string and gets the
        curses cursor position on the screen and stores it
        for the echo() function to use later (I think).
        Then it waits for key presses and passes them to p_key(),
        which returns None if Enter is pressed (that means "Return",
        idiot)."""

        self.s = ''
        self.rl_history.reset()
        self.iy, self.ix = self.scr.getyx()

        if not self.paste_mode:
            for _ in xrange(self.next_indentation()):
                self.p_key('\t')

        self.cpos = 0

        while True:
            key = self.get_key()
            if self.p_key(key) is None:
                return self.s

    def home(self, refresh=True):
        self.scr.move(self.iy, self.ix)
        self.cpos = len(self.s)
        if refresh:
            self.scr.refresh()
        return True

    def lf(self):
        """Process a linefeed character; it only needs to check the
        cursor position and move appropriately so it doesn't clear
        the current line after the cursor."""
        if self.cpos:
            for _ in range(self.cpos):
                self.mvc(-1)

        # Reprint the line (as there was maybe a highlighted paren in it)
        self.print_line(self.s, newline=True)
        self.echo("\n")

    def mkargspec(self, topline, down):
        """This figures out what to do with the argspec and puts it nicely into
        the list window. It returns the number of lines used to display the
        argspec.  It's also kind of messy due to it having to call so many
        addstr() to get the colouring right, but it seems to be pretty
        sturdy."""

        r = 3
        fn = topline[0]
        args = topline[1][0]
        kwargs = topline[1][3]
        _args = topline[1][1]
        _kwargs = topline[1][2]
        is_bound_method = topline[2]
        in_arg = topline[3]
        if py3:
            kwonly = topline[1][4]
            kwonly_defaults = topline[1][5] or dict()
        max_w = int(self.scr.getmaxyx()[1] * 0.6)
        self.list_win.erase()
        self.list_win.resize(3, max_w)
        h, w = self.list_win.getmaxyx()

        self.list_win.addstr('\n  ')
        self.list_win.addstr(fn,
            get_colpair(self.config, 'name') | curses.A_BOLD)
        self.list_win.addstr(': (', get_colpair(self.config, 'name'))
        maxh = self.scr.getmaxyx()[0]

        if is_bound_method and isinstance(in_arg, int):
            in_arg += 1

        punctuation_colpair = get_colpair(self.config, 'punctuation')

        for k, i in enumerate(args):
            y, x = self.list_win.getyx()
            ln = len(str(i))
            kw = None
            if kwargs and k + 1 > len(args) - len(kwargs):
                kw = str(kwargs[k - (len(args) - len(kwargs))])
                ln += len(kw) + 1

            if ln + x >= w:
                ty = self.list_win.getbegyx()[0]
                if not down and ty > 0:
                    h += 1
                    self.list_win.mvwin(ty - 1, 1)
                    self.list_win.resize(h, w)
                elif down and h + r < maxh - ty:
                    h += 1
                    self.list_win.resize(h, w)
                else:
                    break
                r += 1
                self.list_win.addstr('\n\t')

            if str(i) == 'self' and k == 0:
                color = get_colpair(self.config, 'name')
            else:
                color = get_colpair(self.config, 'token')

            if k == in_arg or i == in_arg:
                color |= curses.A_BOLD

            self.list_win.addstr(str(i), color)
            if kw:
                self.list_win.addstr('=', punctuation_colpair)
                self.list_win.addstr(kw, get_colpair(self.config, 'token'))
            if k != len(args) -1:
                self.list_win.addstr(', ', punctuation_colpair)

        if _args:
            if args:
                self.list_win.addstr(', ', punctuation_colpair)
            self.list_win.addstr('*%s' % (_args, ),
                                 get_colpair(self.config, 'token'))

        if py3 and kwonly:
            if not _args:
                if args:
                    self.list_win.addstr(', ', punctuation_colpair)
                self.list_win.addstr('*', punctuation_colpair)
            marker = object()
            for arg in kwonly:
                self.list_win.addstr(', ', punctuation_colpair)
                color = get_colpair(self.config, 'token')
                if arg == in_arg:
                    color |= curses.A_BOLD
                self.list_win.addstr(arg, color)
                default = kwonly_defaults.get(arg, marker)
                if default is not marker:
                    self.list_win.addstr('=', punctuation_colpair)
                    self.list_win.addstr(default,
                                         get_colpair(self.config, 'token'))

        if _kwargs:
            if args or _args or (py3 and kwonly):
                self.list_win.addstr(', ', punctuation_colpair)
            self.list_win.addstr('**%s' % (_kwargs, ),
                                 get_colpair(self.config, 'token'))
        self.list_win.addstr(')', punctuation_colpair)

        return r

    def mvc(self, i, refresh=True):
        """This method moves the cursor relatively from the current
        position, where:
            0 == (right) end of current line
            length of current line len(self.s) == beginning of current line
        and:
            current cursor position + i
            for positive values of i the cursor will move towards the beginning
            of the line, negative values the opposite."""
        y, x = self.scr.getyx()

        if self.cpos == 0 and i < 0:
            return False

        if x == self.ix and y == self.iy and i >= 1:
            return False

        h, w = gethw()
        if x - i < 0:
            y -= 1
            x = w

        if x - i >= w:
            y += 1
            x = 0 + i

        self.cpos += i
        self.scr.move(y, x - i)
        if refresh:
            self.scr.refresh()

        return True

    def p_key(self, key):
        """Process a keypress"""

        if key is None:
            return ''

        config = self.config

        if key == chr(8):  # C-Backspace (on my computer anyway!)
            self.clrtobol()
            key = '\n'
            # Don't return; let it get handled
        if key == chr(27):
            return ''

        if key in (chr(127), 'KEY_BACKSPACE'):
            self.bs()
            self.complete()
            return ''

        elif key in key_dispatch[config.delete_key] and not self.s:
            # Delete on empty line exits
            self.do_exit = True
            return None

        elif key in ('KEY_DC', ) + key_dispatch[config.delete_key]:
            self.delete()
            self.complete()
            # Redraw (as there might have been highlighted parens)
            self.print_line(self.s)
            return ''

        elif key in key_dispatch[config.undo_key]:  # C-r
            self.undo()
            return ''

        elif key in ('KEY_UP', ) + key_dispatch[config.up_one_line_key]:
            # Cursor Up/C-p
            self.back()
            return ''

        elif key in ('KEY_DOWN', ) + key_dispatch[config.down_one_line_key]:
            # Cursor Down/C-n
            self.fwd()
            return ''

        elif key in ("KEY_LEFT",' ^B', chr(2)):  # Cursor Left or ^B
            self.mvc(1)
            # Redraw (as there might have been highlighted parens)
            self.print_line(self.s)

        elif key in ("KEY_RIGHT", '^F', chr(6)):  # Cursor Right or ^F
            self.mvc(-1)
            # Redraw (as there might have been highlighted parens)
            self.print_line(self.s)

        elif key in ("KEY_HOME", '^A', chr(1)):  # home or ^A
            self.home()
            # Redraw (as there might have been highlighted parens)
            self.print_line(self.s)

        elif key in ("KEY_END", '^E', chr(5)):  # end or ^E
            self.end()
            # Redraw (as there might have been highlighted parens)
            self.print_line(self.s)

        elif key in ("KEY_NPAGE", '\T'): # page_down or \T
            self.hend()
            self.print_line(self.s)

        elif key in ("KEY_PPAGE", '\S'): # page_up or \S
            self.hbegin()
            self.print_line(self.s)

        elif key in key_dispatch[config.cut_to_buffer_key]:  # cut to buffer
            self.cut_to_buffer()
            return ''

        elif key in key_dispatch[config.yank_from_buffer_key]:
            # yank from buffer
            self.yank_from_buffer()
            return ''

        elif key in key_dispatch[config.clear_word_key]:
            self.bs_word()
            self.complete()
            return ''

        elif key in key_dispatch[config.clear_line_key]:
            self.clrtobol()
            return ''

        elif key in key_dispatch[config.clear_screen_key]:
            self.s_hist = [self.s_hist[-1]]
            self.highlighted_paren = None
            self.redraw()
            return ''

        elif key in key_dispatch[config.exit_key]:
            if not self.s:
                self.do_exit = True
                return None
            else:
                return ''

        elif key in key_dispatch[config.save_key]:
            self.write2file()
            return ''

        elif key in key_dispatch[config.pastebin_key]:
            self.pastebin()
            return ''

        elif key in key_dispatch[config.last_output_key]:
            page(self.stdout_hist[self.prev_block_finished:-4])
            return ''

        elif key in key_dispatch[config.show_source_key]:
            source = self.get_source_of_current_name()
            if source is not None:
                if config.highlight_show_source:
                    source = format(PythonLexer().get_tokens(source),
                                    TerminalFormatter())
                page(source)
            else:
                self.statusbar.message('Cannot show source.')
            return ''

        elif key == '\n':
            self.lf()
            return None

        elif key == '\t':
            return self.tab()

        elif key == 'KEY_BTAB':
            return self.tab(back=True)

        elif key in key_dispatch[config.suspend_key]:
            self.suspend()
            return ''

        elif len(key) == 1 and not unicodedata.category(key) == 'Cc':
            self.addstr(key)
            self.print_line(self.s)

        else:
            return ''

        return True

    def print_line(self, s, clr=False, newline=False):
        """Chuck a line of text through the highlighter, move the cursor
        to the beginning of the line and output it to the screen."""

        if not s:
            clr = True

        if self.highlighted_paren is not None:
            # Clear previous highlighted paren
            self.reprint_line(*self.highlighted_paren)
            self.highlighted_paren = None

        if self.config.syntax and (not self.paste_mode or newline):
            o = format(self.tokenize(s, newline), self.formatter)
        else:
            o = s

        self.f_string = o
        self.scr.move(self.iy, self.ix)

        if clr:
            self.scr.clrtoeol()

        if clr and not s:
            self.scr.refresh()

        if o:
            for t in o.split('\x04'):
                self.echo(t.rstrip('\n'))

        if self.cpos:
            t = self.cpos
            for _ in range(self.cpos):
                self.mvc(1)
            self.cpos = t

    def prompt(self, more):
        """Show the appropriate Python prompt"""
        if not more:
            self.echo("\x01%s\x03>>> " % (self.config.color_scheme['prompt'],))
            self.stdout_hist += '>>> '
            self.s_hist.append('\x01%s\x03>>> \x04' %
                               (self.config.color_scheme['prompt'],))
        else:
            prompt_more_color = self.config.color_scheme['prompt_more']
            self.echo("\x01%s\x03... " % (prompt_more_color, ))
            self.stdout_hist += '... '
            self.s_hist.append('\x01%s\x03... \x04' % (prompt_more_color, ))

    def push(self, s, insert_into_history=True):
        # curses.raw(True) prevents C-c from causing a SIGINT
        curses.raw(False)
        try:
            return repl.Repl.push(self, s, insert_into_history)
        except SystemExit:
            # Avoid a traceback on e.g. quit()
            self.do_exit = True
            return False
        finally:
            curses.raw(True)

    def redraw(self):
        """Redraw the screen."""
        self.scr.erase()
        for k, s in enumerate(self.s_hist):
            if not s:
                continue
            self.iy, self.ix = self.scr.getyx()
            for i in s.split('\x04'):
                self.echo(i, redraw=False)
            if k < len(self.s_hist) -1:
                self.scr.addstr('\n')
        self.iy, self.ix = self.scr.getyx()
        self.print_line(self.s)
        self.scr.refresh()
        self.statusbar.refresh()

    def repl(self):
        """Initialise the repl and jump into the loop. This method also has to
        keep a stack of lines entered for the horrible "undo" feature. It also
        tracks everything that would normally go to stdout in the normal Python
        interpreter so it can quickly write it to stdout on exit after
        curses.endwin(), as well as a history of lines entered for using
        up/down to go back and forth (which has to be separate to the
        evaluation history, which will be truncated when undoing."""

# Use our own helper function because Python's will use real stdin and
# stdout instead of our wrapped
        self.push('from bpython._internal import _help as help\n', False)

        self.iy, self.ix = self.scr.getyx()
        more = False
        while not self.do_exit:
            self.f_string = ''
            self.prompt(more)
            try:
                inp = self.get_line()
            except KeyboardInterrupt:
                self.statusbar.message('KeyboardInterrupt')
                self.scr.addstr('\n')
                self.scr.touchwin()
                self.scr.refresh()
                continue

            self.scr.redrawwin()
            if self.do_exit:
                return

            self.history.append(inp)
            self.s_hist[-1] += self.f_string
            if py3:
                self.stdout_hist += inp + '\n'
            else:
                self.stdout_hist += inp.encode(getpreferredencoding()) + '\n'
            stdout_position = len(self.stdout_hist)
            more = self.push(inp)
            if not more:
                self.prev_block_finished = stdout_position
                self.s = ''

    def reprint_line(self, lineno, tokens):
        """Helper function for paren highlighting: Reprint line at offset
        `lineno` in current input buffer."""
        if not self.buffer or lineno == len(self.buffer):
            return

        real_lineno = self.iy
        height, width = self.scr.getmaxyx()
        for i in xrange(lineno, len(self.buffer)):
            string = self.buffer[i]
            # 4 = length of prompt
            length = len(string.encode(getpreferredencoding())) + 4
            real_lineno -= int(math.ceil(length / width))
        if real_lineno < 0:
            return

        self.scr.move(real_lineno, 4)
        line = format(tokens, BPythonFormatter(self.config.color_scheme))
        for string in line.split('\x04'):
            self.echo(string)

    def resize(self):
        """This method exists simply to keep it straight forward when
        initialising a window and resizing it."""
        self.size()
        self.scr.erase()
        self.scr.resize(self.h, self.w)
        self.scr.mvwin(self.y, self.x)
        self.statusbar.resize(refresh=False)
        self.redraw()


    def getstdout(self):
        """This method returns the 'spoofed' stdout buffer, for writing to a
        file or sending to a pastebin or whatever."""

        return self.stdout_hist + '\n'


    def reevaluate(self):
        """Clear the buffer, redraw the screen and re-evaluate the history"""

        self.evaluating = True
        self.stdout_hist = ''
        self.f_string = ''
        self.buffer = []
        self.scr.erase()
        self.s_hist = []
        # Set cursor position to -1 to prevent paren matching
        self.cpos = -1

        self.prompt(False)

        self.iy, self.ix = self.scr.getyx()
        for line in self.history:
            if py3:
                self.stdout_hist += line + '\n'
            else:
                self.stdout_hist += line.encode(getpreferredencoding()) + '\n'
            self.print_line(line)
            self.s_hist[-1] += self.f_string
# I decided it was easier to just do this manually
# than to make the print_line and history stuff more flexible.
            self.scr.addstr('\n')
            more = self.push(line)
            self.prompt(more)
            self.iy, self.ix = self.scr.getyx()

        self.cpos = 0
        indent = repl.next_indentation(self.s, self.config.tab_length)
        self.s = ''
        self.scr.refresh()

        if self.buffer:
            for _ in xrange(indent):
                self.tab()

        self.evaluating = False
        #map(self.push, self.history)
        #^-- That's how simple this method was at first :(

    def write(self, s):
        """For overriding stdout defaults"""
        if '\x04' in s:
            for block in s.split('\x04'):
                self.write(block)
            return
        if s.rstrip() and '\x03' in s:
            t = s.split('\x03')[1]
        else:
            t = s

        if not py3 and isinstance(t, unicode):
            t = t.encode(getpreferredencoding())

        if not self.stdout_hist:
            self.stdout_hist = t
        else:
            self.stdout_hist += t

        self.echo(s)
        self.s_hist.append(s.rstrip())


    def show_list(self, items, topline=None, current_item=None):
        shared = Struct()
        shared.cols = 0
        shared.rows = 0
        shared.wl = 0
        y, x = self.scr.getyx()
        h, w = self.scr.getmaxyx()
        down = (y < h // 2)
        if down:
            max_h = h - y
        else:
            max_h = y + 1
        max_w = int(w * 0.8)
        self.list_win.erase()
        if items:
            sep = '.'
            if os.path.sep in items[0]:
                # Filename completion
                sep = os.path.sep
            if sep in items[0]:
                items = [x.rstrip(sep).rsplit(sep)[-1] for x in items]
                if current_item:
                    current_item = current_item.rstrip(sep).rsplit(sep)[-1]

        if topline:
            height_offset = self.mkargspec(topline, down) + 1
        else:
            height_offset = 0

        def lsize():
            wl = max(len(i) for i in v_items) + 1
            if not wl:
                wl = 1
            cols = ((max_w - 2) // wl) or 1
            rows = len(v_items) // cols

            if cols * rows < len(v_items):
                rows += 1

            if rows + 2 >= max_h:
                rows = max_h - 2
                return False

            shared.rows = rows
            shared.cols = cols
            shared.wl = wl
            return True

        if items:
# visible items (we'll append until we can't fit any more in)
            v_items = [items[0][:max_w - 3]]
            lsize()
        else:
            v_items = []

        for i in items[1:]:
            v_items.append(i[:max_w - 3])
            if not lsize():
                del v_items[-1]
                v_items[-1] = '...'
                break

        rows = shared.rows
        if rows + height_offset < max_h:
            rows += height_offset
            display_rows = rows
        else:
            display_rows = rows + height_offset

        cols = shared.cols
        wl = shared.wl

        if topline and not v_items:
            w = max_w
        elif wl + 3 > max_w:
            w = max_w
        else:
            t = (cols + 1) * wl + 3
            if t > max_w:
                t = max_w
            w = t

        if height_offset and display_rows + 5 >= max_h:
            del v_items[-(cols * (height_offset)):]

        if self.docstring is None:
            self.list_win.resize(rows + 2, w)
        else:
            docstring = self.format_docstring(self.docstring, max_w - 2,
                max_h - height_offset)
            docstring_string = ''.join(docstring)
            rows += len(docstring)
            self.list_win.resize(rows, max_w)

        if down:
            self.list_win.mvwin(y + 1, 0)
        else:
            self.list_win.mvwin(y - rows - 2, 0)

        if v_items:
            self.list_win.addstr('\n ')

        if not py3:
            encoding = getpreferredencoding()
        for ix, i in enumerate(v_items):
            padding = (wl - len(i)) * ' '
            if i == current_item:
                color = get_colpair(self.config, 'operator')
            else:
                color = get_colpair(self.config, 'main')
            if not py3:
                i = i.encode(encoding)
            self.list_win.addstr(i + padding, color)
            if ((cols == 1 or (ix and not (ix + 1) % cols))
                    and ix + 1 < len(v_items)):
                self.list_win.addstr('\n ')

        if self.docstring is not None:
            if not py3:
                docstring_string = docstring_string.encode(encoding, 'ignore')
            self.list_win.addstr('\n' + docstring_string,
                                 get_colpair(self.config, 'comment'))
# XXX: After all the trouble I had with sizing the list box (I'm not very good
# at that type of thing) I decided to do this bit of tidying up here just to
# make sure there's no unnececessary blank lines, it makes things look nicer.

        y = self.list_win.getyx()[0]
        self.list_win.resize(y + 2, w)

        self.statusbar.win.touchwin()
        self.statusbar.win.noutrefresh()
        self.list_win.attron(get_colpair(self.config, 'main'))
        self.list_win.border()
        self.scr.touchwin()
        self.scr.cursyncup()
        self.scr.noutrefresh()

# This looks a little odd, but I can't figure a better way to stick the cursor
# back where it belongs (refreshing the window hides the list_win)

        self.scr.move(*self.scr.getyx())
        self.list_win.refresh()

    def size(self):
        """Set instance attributes for x and y top left corner coordinates
        and width and heigth for the window."""
        h, w = stdscr.getmaxyx()
        self.y = 0
        self.w = w
        self.h = h - 1
        self.x = 0

    def suspend(self):
        """Suspend the current process for shell job control."""
        curses.endwin()
        os.kill(os.getpid(), signal.SIGSTOP)

    def tab(self, back=False):
        """Process the tab key being hit. If there's only whitespace
        in the line or the line is blank then process a normal tab,
        otherwise attempt to autocomplete to the best match of possible
        choices in the match list.
        If `back` is True, walk backwards through the list of suggestions
        and don't indent if there are only whitespace in the line."""

        if self.atbol() and not back:
            x_pos = len(self.s) - self.cpos
            num_spaces = x_pos % self.config.tab_length
            if not num_spaces:
                num_spaces = self.config.tab_length

            self.addstr(' ' * num_spaces)
            self.print_line(self.s)
            return True

        if not self.matches_iter:
            self.complete(tab=True)
            if not self.config.auto_display_list and not self.list_win_visible:
                return True

            cw = self.current_string() or self.cw()
            if not cw:
                return True
        else:
            cw = self.matches_iter.current_word

        b = os.path.commonprefix(self.matches)
        if b:
            self.s += b[len(cw):]
            expanded = bool(b[len(cw):])
            self.print_line(self.s)
            if len(self.matches) == 1 and self.config.auto_display_list:
                self.scr.touchwin()
            if expanded:
                self.matches_iter.update(b, self.matches)
        else:
            expanded = False

        if not expanded and self.matches:
            if self.matches_iter:
                self.s = self.s[:-len(self.matches_iter.current())] + cw
            if back:
                current_match = self.matches_iter.previous()
            else:
                current_match = self.matches_iter.next()
            if current_match:
                try:
                    self.show_list(self.matches, self.argspec, current_match)
                except curses.error:
                    # XXX: This is a massive hack, it will go away when I get
                    # cusswords into a good enough state that we can start
                    # using it.
                    self.list_win.border()
                    self.list_win.refresh()
                self.s += current_match[len(cw):]
                self.print_line(self.s, True)
        return True

    def undo(self, n=1):
        repl.Repl.undo(self, n)

        # This will unhighlight highlighted parens
        self.print_line(self.s)

    def writetb(self, lines):
        for line in lines:
            self.write('\x01%s\x03%s' % (self.config.color_scheme['error'],
                                         line))

    def yank_from_buffer(self):
        """Paste the text from the cut buffer at the current cursor location"""
        self.addstr(self.cut_buffer)
        self.print_line(self.s, clr=True)


class Statusbar(object):
    """This class provides the status bar at the bottom of the screen.
    It has message() and prompt() methods for user interactivity, as
    well as settext() and clear() methods for changing its appearance.

    The check() method needs to be called repeatedly if the statusbar is
    going to be aware of when it should update its display after a message()
    has been called (it'll display for a couple of seconds and then disappear).

    It should be called as:
        foo = Statusbar(stdscr, scr, 'Initial text to display')
    or, for a blank statusbar:
        foo = Statusbar(stdscr, scr)

    It can also receive the argument 'c' which will be an integer referring
    to a curses colour pair, e.g.:
        foo = Statusbar(stdscr, 'Hello', c=4)

    stdscr should be a curses window object in which to put the status bar.
    pwin should be the parent window. To be honest, this is only really here
    so the cursor can be returned to the window properly.

    """

    def __init__(self, scr, pwin, background, config, s=None, c=None):
        """Initialise the statusbar and display the initial text (if any)"""
        self.size()
        self.win = newwin(background, self.h, self.w, self.y, self.x)

        self.config = config

        self.s = s or ''
        self._s = self.s
        self.c = c
        self.timer = 0
        self.pwin = pwin
        self.settext(s, c)

    def size(self):
        """Set instance attributes for x and y top left corner coordinates
        and width and heigth for the window."""
        h, w = gethw()
        self.y = h - 1
        self.w = w
        self.h = 1
        self.x = 0

    def resize(self, refresh=True):
        """This method exists simply to keep it straight forward when
        initialising a window and resizing it."""
        self.size()
        self.win.mvwin(self.y, self.x)
        self.win.resize(self.h, self.w)
        if refresh:
            self.refresh()

    def refresh(self):
        """This is here to make sure the status bar text is redraw properly
        after a resize."""
        self.settext(self._s)

    def check(self):
        """This is the method that should be called every half second or so
        to see if the status bar needs updating."""
        if not self.timer:
            return

        if time.time() < self.timer:
            return

        self.settext(self._s)

    def message(self, s, n=3):
        """Display a message for a short n seconds on the statusbar and return
        it to its original state."""
        self.timer = time.time() + n
        self.settext(s)

    def prompt(self, s=''):
        """Prompt the user for some input (with the optional prompt 's') and
        return the input text, then restore the statusbar to its original
        value."""

        self.settext(s or '? ', p=True)
        iy, ix = self.win.getyx()

        def bs(s):
            y, x = self.win.getyx()
            if x == ix:
                return s
            s = s[:-1]
            self.win.delch(y, x - 1)
            self.win.move(y, x - 1)
            return s

        o = ''
        while True:
            c = self.win.getch()

            # '\b'
            if c == 127:
                o = bs(o)
            # '\n'
            elif c == 10:
                break
            # ESC
            elif c == 27:
                curses.flushinp()
                raise ValueError
            # literal
            elif 0 <= c < 127:
                c = chr(c)
                self.win.addstr(c, get_colpair(self.config, 'prompt'))
                o += c

        self.settext(self._s)
        return o

    def settext(self, s, c=None, p=False):
        """Set the text on the status bar to a new permanent value; this is the
        value that will be set after a prompt or message. c is the optional
        curses colour pair to use (if not specified the last specified colour
        pair will be used).  p is True if the cursor is expected to stay in the
        status window (e.g. when prompting)."""

        self.win.erase()
        if len(s) >= self.w:
            s = s[:self.w - 1]

        self.s = s
        if c:
            self.c = c

        if s:
            if self.c:
                self.win.addstr(s, self.c)
            else:
                self.win.addstr(s)

        if not p:
            self.win.noutrefresh()
            self.pwin.refresh()
        else:
            self.win.refresh()

    def clear(self):
        """Clear the status bar."""
        self.win.clear()


def init_wins(scr, colors, config):
    """Initialise the two windows (the main repl interface and the little
    status bar at the bottom with some stuff in it)"""
#TODO: Document better what stuff is on the status bar.

    background = get_colpair(config, 'background')
    h, w = gethw()

    main_win = newwin(background, h - 1, w, 0, 0)
    main_win.scrollok(True)
    main_win.keypad(1)
# Thanks to Angus Gibson for pointing out this missing line which was causing
# problems that needed dirty hackery to fix. :)

    statusbar = Statusbar(scr, main_win, background, config,
        " <%s> Rewind  <%s> Save  <%s> Pastebin  <%s> Pager  <%s> Show Source " %
            (config.undo_key, config.save_key,
             config.pastebin_key, config.last_output_key,
             config.show_source_key),
            get_colpair(config, 'main'))

    return main_win, statusbar


def sigwinch(unused_scr):
    global DO_RESIZE
    DO_RESIZE = True

def sigcont(unused_scr):
    sigwinch(unused_scr)
    # Forces the redraw
    curses.ungetch('')

def gethw():
    """I found this code on a usenet post, and snipped out the bit I needed,
    so thanks to whoever wrote that, sorry I forgot your name, I'm sure you're
    a great guy.

    It's unfortunately necessary (unless someone has any better ideas) in order
    to allow curses and readline to work together. I looked at the code for
    libreadline and noticed this comment:

        /* This is the stuff that is hard for me.  I never seem to write good
           display routines in C.  Let's see how I do this time. */

    So I'm not going to ask any questions.

    """
    h, w = struct.unpack(
        "hhhh",
        fcntl.ioctl(sys.__stdout__, termios.TIOCGWINSZ, "\000" * 8))[0:2]
    return h, w


def idle(caller):
    """This is called once every iteration through the getkey()
    loop (currently in the Repl class, see the get_line() method).
    The statusbar check needs to go here to take care of timed
    messages and the resize handlers need to be here to make
    sure it happens conveniently."""

    if importcompletion.find_coroutine() or caller.paste_mode:
        caller.scr.nodelay(True)
        key = caller.scr.getch()
        caller.scr.nodelay(False)
        curses.ungetch(key)
    caller.statusbar.check()
    caller.check()

    if DO_RESIZE:
        do_resize(caller)


def do_resize(caller):
    """This needs to hack around readline and curses not playing
    nicely together. See also gethw() above."""
    global DO_RESIZE
    h, w = gethw()
    if not h:
# Hopefully this shouldn't happen. :)
        return

    curses.endwin()
    os.environ["LINES"] = str(h)
    os.environ["COLUMNS"] = str(w)
    curses.doupdate()
    DO_RESIZE = False

    caller.resize()
# The list win resizes itself every time it appears so no need to do it here.


class FakeDict(object):
    """Very simple dict-alike that returns a constant value for any key -
    used as a hacky solution to using a colours dict containing colour codes if
    colour initialisation fails."""

    def __init__(self, val):
        self._val = val

    def __getitem__(self, k):
        return self._val


def newwin(background, *args):
    """Wrapper for curses.newwin to automatically set background colour on any
    newly created window."""
    win = curses.newwin(*args)
    win.bkgd(' ', background)
    return win


def curses_wrapper(func, *args, **kwargs):
    """Like curses.wrapper(), but reuses stdscr when called again."""
    global stdscr
    if stdscr is None:
        stdscr = curses.initscr()
    try:
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(1)

        try:
            curses.start_color()
        except curses.error:
            pass

        return func(stdscr, *args, **kwargs)
    finally:
        stdscr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()


def main_curses(scr, args, config, interactive=True, locals_=None,
                banner=None):
    """main function for the curses convenience wrapper

    Initialise the two main objects: the interpreter
    and the repl. The repl does what a repl does and lots
    of other cool stuff like syntax highlighting and stuff.
    I've tried to keep it well factored but it needs some
    tidying up, especially in separating the curses stuff
    from the rest of the repl.
    """
    global stdscr
    global DO_RESIZE
    global colors
    global repl
    DO_RESIZE = False

    old_sigwinch_handler = signal.signal(signal.SIGWINCH,
                                         lambda *_: sigwinch(scr))
    # redraw window after being suspended
    old_sigcont_handler = signal.signal(signal.SIGCONT, lambda *_: sigcont(scr))

    stdscr = scr
    try:
        curses.start_color()
        curses.use_default_colors()
        cols = make_colors(config)
    except curses.error:
        cols = FakeDict(-1)

    # FIXME: Gargh, bad design results in using globals without a refactor :(
    colors = cols

    scr.timeout(300)

    curses.raw(True)
    main_win, statusbar = init_wins(scr, cols, config)

    if locals_ is None:
        sys.modules['__main__'] = ModuleType('__main__')
        locals_ = sys.modules['__main__'].__dict__
    interpreter = repl.Interpreter(locals_, getpreferredencoding())

    clirepl = CLIRepl(main_win, interpreter, statusbar, config, idle)
    clirepl._C = cols

    sys.stdin = FakeStdin(clirepl)
    sys.stdout = clirepl
    sys.stderr = clirepl

    if args:
        bpython.args.exec_code(interpreter, args)
        if not interactive:
            curses.raw(False)
            return clirepl.getstdout()
    else:
        sys.path.insert(0, '')
        clirepl.startup()

    if banner is not None:
        clirepl.write(banner)
        clirepl.write('\n')
    clirepl.repl()
    if config.hist_length:
        histfilename = os.path.expanduser(config.hist_file)
        clirepl.rl_history.save(histfilename, getpreferredencoding())

    main_win.erase()
    main_win.refresh()
    statusbar.win.clear()
    statusbar.win.refresh()
    curses.raw(False)

    # Restore signal handlers
    signal.signal(signal.SIGWINCH, old_sigwinch_handler)
    signal.signal(signal.SIGCONT, old_sigcont_handler)

    return clirepl.getstdout()


def main(args=None, locals_=None, banner=None):
    global stdscr

    setlocale(LC_ALL, '')

    config, options, exec_args = bpython.args.parse(args)

    # Save stdin, stdout and stderr for later restoration
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr

    try:
        o = curses_wrapper(main_curses, exec_args, config,
                           options.interactive, locals_,
                           banner=banner)
    finally:
        sys.stdin = orig_stdin
        sys.stderr = orig_stderr
        sys.stdout = orig_stdout

# Fake stdout data so everything's still visible after exiting
    if config.flush_output and not options.quiet:
        sys.stdout.write(o)
    sys.stdout.flush()


if __name__ == '__main__':
    from bpython.cli import main
    main()

# vim: sw=4 ts=4 sts=4 ai et
