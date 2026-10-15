"""Decide how PDF line wraps inside answer choices should be shown.

The exam PDFs wrap lines at a fixed width, often in the middle of a word ("측정\\n한다").
The extracted text keeps these wraps, but not whether a space stood at the wrap. For each
wrap inside a choice this module picks 'j' (join without space), 's' (join with a space)
or 'k' (keep the line break, for lines that look like table rows or list items), using how
often the joined word and the spaced pair occur elsewhere in the question bank.
Only the on-screen rendering uses the result; data/questions.json is never changed.
"""
import re
from collections import Counter

CHOICE = re.compile(r'^\s*[①②③④]')
STRUCTURAL = re.compile(r'^\s*([ㄱ-ㅎ][.)]|[<(]|\d+[.)]|[-•·※]|[A-Za-z][.)])')
TABLE = re.compile(r'\S\s{2,}\S|\t')  # column gaps in table-like lines
PARTICLES = {'은', '는', '이', '가', '을', '를', '에', '의', '로', '와', '과', '도', '만', '에서', '으로', '에게',
             '이다', '이며', '이고', '으로서', '로서', '에는', '에도', '까지', '부터', '보다'}
HANGUL = re.compile(r'^[가-힣]+$')
ONE_SYLLABLE_WORDS = set('및수등각두그이저것중때후전외내측별약총데뿐')
WORD_FINAL = ('으로', '로', '을', '를', '은', '는', '의', '에', '며', '고', '서', '한', '할', '된', '인', '와', '과', '도', '면', '나')
PUNCT = '.,·:;!?()[]{}"\'“”‘’「」『』%'


def key(token):
    return token.strip(PUNCT)


def corpus_counts(texts):
    words, pairs = Counter(), Counter()
    for text in texts:
        for line in text.split('\n'):
            tokens = [key(t) for t in line.split()]
            tokens = [t for t in tokens if t]
            # The first and last token of a wrapped line may be word fragments; count only
            # interior tokens as words so fragments do not look like real words.
            words.update(tokens[1:-1])
            pairs.update(zip(tokens, tokens[1:]))
    return words, pairs


def decide(prev_line, next_line, words, pairs):
    if STRUCTURAL.match(next_line) or TABLE.search(prev_line.strip()) or TABLE.search(next_line.strip()):
        return 'k'
    prev_tokens, next_tokens = prev_line.split(), next_line.split()
    if not prev_tokens or not next_tokens:
        return 'k'
    a, b = key(prev_tokens[-1]), key(next_tokens[0])
    if not a or not b:
        return 's'
    if HANGUL.match(a) and HANGUL.match(b):
        if b in PARTICLES or (len(b) == 1 and b not in ONE_SYLLABLE_WORDS):
            return 'j'
    joined, spaced = words[a + b], pairs[(a, b)]
    if joined != spaced:
        return 'j' if joined > spaced else 's'
    if len(a) >= 2 and a.endswith(WORD_FINAL):
        return 's'
    return 'j' if words[a] == 0 or words[b] == 0 else 's'


def choice_breaks(text, words, pairs):
    """Return one decision character per line break that continues an answer choice."""
    out, in_choice, lines = [], False, text.split('\n')
    for prev, nxt in zip(lines, lines[1:]):
        in_choice = in_choice or bool(CHOICE.match(prev))
        if in_choice and not CHOICE.match(nxt):
            out.append(decide(prev, nxt, words, pairs))
    return ''.join(out)


def _width(line):
    return sum(2 if '\uac00' <= c <= '\ud7a3' else 1 for c in line)


def stem_breaks(text, words, pairs):
    """One decision per line break in the question stem (before the first choice).

    Stems mix wrapped prose with data lines and tables, so a break is only joined when the
    previous line is nearly full width (a PDF wrap), does not end a sentence or clause, and
    neither line looks like a table row or list item; otherwise it is kept ('k').
    """
    lines = text.split('\n')
    widest = max((_width(l) for l in lines), default=0)
    out = []
    for prev, nxt in zip(lines, lines[1:]):
        if CHOICE.match(nxt) or CHOICE.match(prev):
            break
        full = widest and _width(prev) >= 0.8 * widest
        ends = not prev.strip() or prev.rstrip()[-1] in '.?:)다'
        if not full or ends or STRUCTURAL.match(nxt) or TABLE.search(prev.strip()) or TABLE.search(nxt.strip()):
            out.append('k')
        else:
            out.append(decide(prev, nxt, words, pairs))
    return ''.join(out)
