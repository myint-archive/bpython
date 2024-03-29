Changelog
=========

Since v0.11
___________

* Added a new pastebin_helper config option to name an executable that should
  perform pastebin upload on bpython's behalf. If set, this overrides
  pastebin_url. Data is supplied to the helper via STDIN, and it is expected
  to return a pastebin URL as the first word of its output.
* Fixed a bug causing pastebin upload to fail after a previous attempt was
  unsuccessful. A duplicate pastebin error would be displayed in this case,
  despite the original upload having failed.

v0.11
-----

A bugfix/cleanup release .The fixed bugs are:

* #204: "import math" not autocompleting on python 3.2

Otherwise lots of small additions to the to be replacement for our ncurses
frontend, the urwid frontend.

I'd like to specifically thank Amjith Ramanujam for his work on history search
which was further implemented and is in working order right now.

v0.10.1
-------

A bugfix release. The fixed bugs are:

* #197: find_modules crashes on non-readable directories
* #198: Source tarball lacks .po files

v0.10
-----
As a highlight of the release, Michele Orrù added i18n support to bpython.

Some issues have been resolved as well:

* Config files are now located according to the XDG Base Directory
  Specification. The support for the old bpythonrc files has been
  dropped and ~/.bpython.ini as config file location is no longer supported.
  See issue #91.
* Fixed some issues with tuple unpacking in argspec. See issues #133 and #138.
* Fixed a crash with non-ascii filenames in import completion. See issue #139.
* Fixed a crash caused by inspect.findsource() raising an IndexError
  which happens in some situations. See issue #94.
* Non-ascii input should work now under Python 3.
* Issue #165: C-a and C-e do the right thing now in urwid.
* The short command-line option "-c config" was dropped as it conflicts with
  vanilla Python's "-c command" option. See issue #186.

v0.9.7.1
--------

A bugfix release. The fixed bugs are:

* #128: bpython-gtk is broken
* #134: crash when using pastebin and no active internet connection

v0.9.7
------

Well guys. It's been some time since the latest release, six months have passed
We have added a whole slew of new features, and closed a number of bugs as well.

We also have a new frontend for bpython. Marien Zwart contributed a urwid
frontend as an alternative for the curses frontend. Be aware that there still
is a lot to fix for this urwid frontend (a lot of the keyboard shortcuts do not
yet work for example) but please give it a good spin. Urwid also optionally
integrates with a Twisted reactor and through that with things like the GTK
event loop.

At the same time we have done a lot of work on the GTK frontend. The GTK
frontend is now 'usable'. Please give that a spin as well by running python-gtk
on you system.

We also welcome a new contributor in the name of Michele Orrù who we hope will
help us fix even more bugs and improve functionality.

As always, please submit any bugs you might find to our bugtracker.

* Pastebin confirmation added; we were getting a lot of people accidentally pastebinning sensitive information so I think this is a good idea.
* Don't read PYTHONSTARTUP when executed with -i.
* BPDB was merged in. BPDB is an extension to PDB which allows you to press B in a PDB session which will let you be dropped into a bpython sessions with the current PDB locals(). For usage, see the documentation.
* The clear word shortcut (default: C-w) now deletes to the buffer.
* More tests have been added to bpython.
* The pastebin now checks for a previous paste (during the session) with the exact same content to guard against twitchy fingers pastebinning multiple times.
* Let import completion return "import " instead of "import".

* GTK now has pastebin, both for full log as well as the current selection.
* GTK now has write2file.
* GTK now has a menu.
* GTK now has a statusbar.
* GTK now has show source functionality.
* GTK saves the pastebin url to the clipboard.
* GTK now has it's own configuration section.
* Set focus to the GTK text widget to allow for easier embedding in PIDA and others which fixes issues #121.

* #87: Add a closed attribute to Repl to fix mercurial.ui.ui expecting stderr to have this attribute.
* #108: Unicode characters in docsrting crash bpython
* #118: Load_theme is not defined.
* #99: Configurable font now documented.
* #123: <F8> Pastebin can't handle 'ESC' key
* #124: Unwanted input when using <arrow>/<FXX> keys in the statusbar prompt

v0.9.6.2
--------
Unfortunately another bugfix release as I (Bob) broke py3 support.

* #84: bpython doesn't work with Python 3
       Thanks very much to Henry Prêcheur for both the bug report and the
       patch.

v0.9.6.1
--------
A quick bugfix release (this should not become a habit).

* #82: Crash on saving file.

v0.9.6
------
A bugfix/feature release (and a start at gtk). Happy Christmas everyone!

* #67: Make pastebin URL really configurable.
* #68: Set a__main__ module and set interpreter's namespace to that module.
* #70: Implement backward completion on backward tab.
* #62: Hide matches starting with a _ unless explicitly typed.
* #72: Auto dedentation
* #78: Theme without a certain value raises exception

- add the possibility for a banner to be shown on bpython startup (when embedded or in code) written by Caio Ramao.
- add a hack to add a write() method to our fake stdin object
- Don't use curses interface when stdout is not attached to a terminal.
- PEP-8 conformance.
- Only restore indentation when inside a block.
- Do not decrease the lineno in tracebacks for Py3
- Do not add internal code to history.
- Make paren highlighting more accurate.
- Catch SyntaxError in import completion.
- Remove globals for configuration.
- rl_history now stays the same, also after undo.

v0.9.5.2
--------

A bugfix release. Fixed issues:

* #60: Filename expansion: Cycling completions and deleting
* #61: Filename expansion: Directory names with '.'s get mangled

Other fixes without opened issues:

* Encode items in the suggestion list properly
* Expand usernames in file completion correctly
* future imports in startup scripts can influence interpreter's behaviour now
* Show the correct docstring for types without a own __init__ method

v0.9.5.1
--------

Added missing data files to the tarball.


v0.9.5
------
Fixed issues:

* #25 Problems with DEL, Backspace and C-u over multiple lines
* #49 Sending last output to $PAGER
* #51 Ability to embed bpython shell into an existing script
* #52 FakeStdin.readlines() is broken
* #53 Error on printing null character
* #54 Parsing/introspection ncurses viewer neglects parenthesis

bpython has added a view source shortcut to show the source of the current
function.

The history file is now really configurable. This issue was reported
in Debian's bugtracker.

bpython has now some basic support for Python 3 (requires Pygments >=1.1.1).
As a result, setuptools is now optional.

The pastebin URL is now configurable and the default pastebin is now
bpaste.net

Argument names are now shown as completion suggestions and one can
tab through the completion list.

v0.9.4
------
Bugfix release (mostly)

* when typing a float literal bpython autocompletes int methods (#36)
* Autocompletion for file names (#40)
* Indenting doesn't reset (#27)
* bpython configuration has moved from ~/.bpython.ini to ~/.bpython/config (currently still supporting fallback)
* leftovers of statusbar when exiting bpython cleaned up
* bpython now does not crash when a 'popup' goes out of window bounds
* numerous fixes and improvements to parentheses highlighting
* made *all* keys configurable (except for arrow keys/pgup/pgdown)

v0.9.3
------
This release was a true whopper!

* Full unicode support
* Configurable hotkey support
* Theming support
* Pastemode, disables syntax highlighting during a paste for faster pasting, highlights when done
* Parentheses matching
* Argument highlighting

v0.9.2
------
* help() now uses an external pager if available.
* Fix for highlighting prefixed strings.
* Fix to reset string highlighting after a SyntaxError.
* bpython now uses optparse for option parsing and it supports --version now.
* Configuration files are no longer passed by the first command line argument but by the -c command line switch.
* Fix for problem related to editing lines in the history: http://bitbucket.org/bobf/bpython/issue/10/odd-behaviour-when-editing-commands-in-the-history

v0.9.1
------
* Fixed a small but annoying bug with sys.argv ini file passing
* Fix for Python 2.6 to monkeypatch they way it detects callables in rlcompleter
* Config file conversion fix

v0.9.0
------
* Module import completion added.
* Changed to paste.pocoo.org due to rafb.net no longer offering a pastebin service.
* Switched to .ini file format for config file.
* White background-friendly colour scheme added.
* C-l now clears the screen.
* SyntaxError now correctly added to history to prevent it garbling up on a redraw.

Probably some other things, but I hate changelogs. :)

v0.8.0
------

It's been a long while since the last release and there've been numerous little
bugfixes and extras here and there so I'm putting this out as 0.8.0. Check the
hg commit history if you want more info:
http://bitbucket.org/bobf/bpython/

v0.7.2
------
Menno sent me some patches to fix some stuff:

* Socket error handled when submitting to a pastebin.
* Resizing could crash if you resize small enough.

Other stuff:

* 'self' in arg list is now highlighted a different colour.
* flush_output option added to config to control whether output is flushed to stdout or not on exit.
* Piping something to bpython made it lock up as stdin was not the keyboard - bpython just executes stdin and exits instead of trying to do something clever.
* Mark Florisson (eggy) gave me a patch that stops weird breakage when unicode objects get added into the output buffer - they now get encoded into the output encoding.
* Bohdan Vlasyuk sent me a patch that fixes a problem with the above patch from Mark if sys.__stdout__.encoding didn't exist.
* Save to file now outputs executable code (i.e. without the >>> and ... and with "# OUT: " prepended to all output lines). I never used this feature much but someone asked for this behaviour.

v0.7.1
------
* Added support for a history file, defaults to ~/.pythonhist and 100 lines but is configurable from the rc file (see sample-rc).
* Charles Duffy has added a yank/put thing - C-k and C-y. He also ran the code through some PEP-8 checker thing and fixed up a few old habits I manage to break but didn't manage to fix the code to reflect this - thank you!
* Jørgen Tjernø has fixed up the autoindentation issues we encountered when bringing soft tabs in.
* SyntaxError, ValueError and OverflowError are now caught properly (code.InteractiveInterpreter treats these as different to other exceptions as it doesn't print the whole traceback, so a different handler is called). This was discovered as I was trying to stop autoindentation from occurring on a SyntaxError, which has also been fixed.
* '.' now in sys.path on startup.

v0.7.0
------
C-d behaviour changed so it no longer exits if the current line isn't empty.

Extra linebreak added to end of stdout flush.

pygments and pyparsing are now dependencies.

Jørgen Tjernø has done lots of cool things like write a manpage and .desktop
file and improved the way tabbing works and also added home, end and del key
handling as well as C-w for deleting words - thanks a lot!

raw_input() and all its friends now work fine.

PYTHONSTARTUP handled without blowing up on stupid errors (it now parses the
file at once instead of feeding it to the repl line-by-line).

v0.6.4
------
KeyboardInterrupt handler clears the list window properly now.

v0.6.3
------
Forgot to switch rpartition to split for 2.4 compat.

v0.6.2
------
The help() now works (as far as I can see) exactly the same
as the vanilla help() in the regular interpreter. I copied some
code from pydoc.py to make it handle the special cases, e.g.
help('keywords')
help('modules')
etc.

v0.6.1
------
Somehow it escaped my attention that the list window was never
fully using the rightmost column, except for the first row. This
is because me and numbers don't have the best relationship. I think
stability is really improving with the latest spat of bugfixes,
keep me informed of any bugs.

v0.6.0
------
No noticeable changes except that bpython should now work with
Python 2.4. Personally I think it's silly to make a development
tool work with an out of date version of Python but some people
seem to disagree. The only real downside is that I had to do a
horrible version of all() using reduce(), otherwise there's no
real differences in the code.

v0.5.3
------
Now you can configure a ~/.bpythonrc file (or pass a rc file at the
command line (bpython /foo/bar). See README for details.

v0.5.2
------
help() actually displays the full help page, and I fixed up the
ghetto pager a little.

v0.5.1
------
Now you can hit tab to display the autocomplete list, rather than
have it pop up automatically as you type which, apparently, annoys
Brendogg.

v0.5.0
------
A few people have commented that the help() built-in function
doesn't work so well with bpython, since Python will try to output
the help string to PAGER (usually "less") which obviously makes
everything go wrong when curses is involved. With a bit of hackery
I've written my own ghetto pager and injected my own help function
into the interpreter when it initialises in an attempt to rectify this.
As such, it's pretty untested but it seems to be working okay for me.
Suggestions/bug reports/patches are welcome regarding this.

v0.4.2
------
Well, hopefully we're one step closer to making the list sizing
stuff work. I really hate doing code for that kind of thing as I
never get it quite right, but with perseverance it should end up
being completely stable; it's not the hardest thing in the world.

Various cosmetic fixes have been put in at the request of a bunch
of people who were kind enough to send me emails regarding their
experiences.

PYTHONSTARTUP is now dealt with and used properly, as per the vanilla
interpreter.

v0.4.1
------
It looks like the last release was actually pretty bug-free, aside
from one tiny bug that NEVER ACTUALLY HAPPENS but someone was bugging
me about it anyway, oh well.

v0.4.0
------
It's been quite a long time since the last update, due to several
uninteresting and invalid excuses, but I finally reworked the list
drawing procedures so the crashing seems to have been taken care of
to an extent. If it still crashes, the way I've written it will hopefully
allow a much more robust way of fixing it, one that might actually work.

v0.3.2
------
Thanks to Aaron Gallagher for pointing out a case where the hugely
inefficient list generation routines were actually making a significant
issue; they're much more efficient now and should hopefully not cause
any more problems.

v0.3.1
------
Thanks to Klaus Alexander Seis for the expanduser() patch.
Auto indent works on multiple levels now.

v0.3.0
------
Now with auto-indent. Let me know if it's annoying.

v0.2.4
------
Thanks a lot to Angus Gibson for submitting a patch to fix a problem
I was having with initialising the keyboard stuff in curses properly.

Also a big thanks to John Beisley for providing the patch that shows
a class __init__ method's argspec on class instantiation.

I've fixed up the argspec display so it handles really long argspecs
(e.g. subprocess.Popen()) and doesn't crash if something horrible
happens (rather, it avoids letting something horrible happen).

I decided to add a key that will get rid of the autocomplete window,
since it can get in the way. C-l seemed like a good choice, since
it would work well as a side-effect of redrawing the screen (at
least that makes sense to me). In so doing I also cleaned up a lot
of the reevaluating and resizing code so that a lot of the strange
output seen on Rewind/resize seems to be gone.

v0.2.3
------
The fix for the last bug broke the positioning of the autocomplete
box, whoops.

v0.2.2
------
That pesky bug keeps coming up. I think it's finally nailed but
it's just a matter of testing and hoping. I hate numbers.

v0.2.1
------
I'm having a bit of trouble with some integer division that's
causing trouble when a certain set of circumstances arise,
and I think I've taken care of that little bug, since it's
a real pain in the ass and only creeps up when I'm actually
doing something useful, so I'll test it for a bit and release
it as hopefully a bug fixed version.

v0.2.0
------
A little late in the day to start a changelog, but here goes...
This version fixed another annoying little bug that was causing
crashes given certain exact circumstances. I always find it's the
way with curses and sizing of windows and things...

I've also got bpython to try looking into pydoc if no matches
are found for the argspec, which means the builtins have argspecs
too now, hooray.
