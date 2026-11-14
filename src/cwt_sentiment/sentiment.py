"""Transparent baseline sentiment utilities; replace/validate for production use.

Method (documented, not hidden):
- Latin terms match whole words; CJK/Korean terms match substrings, longest
  term first, so a compound (上涨) is counted once and not also as its parts (涨).
- A negation marker near a matched term flips that term's polarity:
  English "not/no/never/n't ..." within 3 words before (2 after) the term;
  Chinese/Cantonese 不/没/未/非/唔/冇 within 4 characters before it;
  Korean negation usually follows the verb (상승하지 않다), so 않다/안/못
  are checked 4 characters before and 6 after the term.
- Score is (positive hits - negative hits) / total hits, in [-1, 1].
  A text with no recognised directional term scores 0 (Neutral).

Known limits: sarcasm and irony ("yeah right, total scam" is only caught
because "scam" is now a negative term, not because the sarcasm is understood);
"no" as a plain word can flip a term; single-character CJK terms can match
inside unrelated words. This is a keyword baseline, not a finance-trained
or validated multilingual model. See tests/test_sentiment_labelled.py for the
hand-labelled accuracy check against real collected posts: 100 posts,
24% overall (English 53%, Korean 9%, Chinese 33% on n=3). The Korean
shortfall is structural — forum slang, conditionals and news quotes carry
the sentiment, not keywords — so the sentiment feature in the pipeline
stays exploratory-only.
"""

from __future__ import annotations

import re

POSITIVE = {
    # English
    "bullish", "buy", "buying", "bought", "strong", "surge", "rally", "gain", "gains", "breakout",
    "undervalued", "soar", "soaring", "skyrocket", "moon", "rebound", "uptrend",
    "recover", "recovery", "bull", "bulls",
    # Chinese (simplified + traditional)
    "看多", "看好", "利好", "利多", "上涨", "上漲", "升", "買入", "买入", "強勢", "强势",
    "大涨", "大漲", "涨停", "漲停", "冲高", "衝高", "走强", "反弹", "反彈", "新高",
    "创新高", "創新高", "强劲", "強勁", "回升", "挾",
    # Korean
    "매수", "호재", "상승", "강세", "돌파", "떡상", "급등", "반등", "신고가",
    "폭등", "상한가", "저평가", "수주", "흑자", "회복", "성장", "호실적",
    "서프라이즈", "매수세", "배당", "대박", "상승세",
    "반등세", "강세장",
}
NEGATIVE = {
    # English
    "bearish", "sell", "sold", "short", "shorted", "weak", "drop", "fall", "crash", "loss", "losses", "overvalued",
    "scam", "fraud", "dump", "plunge", "tank", "tanking", "selloff", "sell-off",
    "rug", "rugpull", "bankrupt", "downgrade", "panic", "fear", "downtrend",
    # Chinese (simplified + traditional)
    "看空", "利淡", "利空", "下跌", "跌", "沽出", "賣出", "卖出", "弱勢", "弱势",
    "套牢", "套牢", "出货", "出貨", "跌停", "割肉", "蟹货", "蟹貨", "散水",
    "洗仓", "洗倉", "大跌", "大跌", "暴跌", "跳水", "阴跌", "陰跌", "破位",
    "破发", "破發", "退市", "暴雷", "踩雷", "唔掂", "冇運行",
    # Korean
    "매도", "악재", "하락", "약세", "급락", "떡락", "사기", "폭락", "손절", "물렸다",
    "빠지", "떨어지", "내리", "하락세", "추락", "붕괴", "망하", "사퇴", "불매",
    "하한가", "탈출", "손실", "적자", "조정", "고평가", "공매도", "투매", "잡주",
    "나락", "매도세", "하락장", "폭락장",
}

# Negation markers. English: checked as whole tokens. CJK: checked as substrings
# in a character window around the matched term (Korean negation usually
# follows the verb stem, so it is checked on both sides).
NEGATIONS_EN = {
    "not", "no", "never", "none", "nobody", "nothing", "neither", "nor",
    "without", "hardly", "barely", "lack", "lacks", "lacking",
    "dont", "doesnt", "didnt", "isnt", "arent", "wasnt", "werent",
    "cant", "wont", "couldnt", "shouldnt", "wouldnt", "hasnt", "havent", "hadnt",
}
NEGATIONS_CJK_BEFORE = ("不", "没", "未", "非", "唔", "冇", "無", "无", "別", "别", "안", "못")
NEGATIONS_CJK_AFTER = ("않다", "않", "안", "못", "아니다", "아니", "없다", "없어", "不", "没")

_LATIN_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


def _is_negated_latin(matches: list[re.Match], value: str, index: int) -> bool:
    """True if a negation token sits within 3 tokens before or 2 after.

    The backward scan stops at the previous sentiment term, so one negation
    cannot flip two different terms ("never sell, strong buy" flips "sell"
    only, not "buy"). A "no" that is really a list number ("No. 5, buy") is
    not a negation: it is skipped when a full stop follows it in the raw text.
    """
    tokens = [m.group() for m in matches]
    latin_terms = {t for t in POSITIVE if t.isascii()} | {t for t in NEGATIVE if t.isascii()}
    for j in range(index - 1, max(-1, index - 4), -1):
        token = tokens[j]
        if token in latin_terms:
            break
        if token == "no" and value[matches[j].end():matches[j].end() + 1] == ".":
            continue
        if token in NEGATIONS_EN or token.endswith("n't"):
            return True
    for j in range(index + 1, min(len(tokens), index + 3)):
        if tokens[j] in ("not", "no", "never"):
            return True
    return False


def _cjk_spans(value: str, terms: set[str]) -> list[tuple[int, int, str]]:
    """Longest-match-first, non-overlapping occurrences of terms in value."""
    spans: list[tuple[int, int, str]] = []
    for term in sorted(terms, key=len, reverse=True):
        start = 0
        while True:
            found = value.find(term, start)
            if found < 0:
                break
            end = found + len(term)
            if not any(s < end and found < e for s, e, _ in spans):
                spans.append((found, end, term))
            start = found + 1
    return spans


def _is_negated_cjk(value: str, start: int, end: int) -> bool:
    before = value[max(0, start - 4):start]
    after = value[end:end + 6]
    if any(marker in before for marker in NEGATIONS_CJK_BEFORE):
        return True
    if any(marker in after for marker in NEGATIONS_CJK_AFTER):
        return True
    return False


def score_sentiment(text: object) -> float:
    """Return a simple bounded keyword score in [-1, 1]. Neutral/no-hit text scores 0.

    Negation flips the polarity of the term it modifies; see the module
    docstring for the exact rules and known limits.
    """
    if text is None:
        return 0.0
    value = str(text).lower()
    positive_hits = 0
    negative_hits = 0

    # CJK/Korean: span-based, longest match first.
    cjk_positive = {t for t in POSITIVE if not t.isascii()}
    cjk_negative = {t for t in NEGATIVE if not t.isascii()}
    for start, end, _term in _cjk_spans(value, cjk_positive):
        if _is_negated_cjk(value, start, end):
            negative_hits += 1
        else:
            positive_hits += 1
    for start, end, _term in _cjk_spans(value, cjk_negative):
        if _is_negated_cjk(value, start, end):
            positive_hits += 1
        else:
            negative_hits += 1

    # Latin: whole-word tokens, negation-aware.
    matches = list(_LATIN_WORD_RE.finditer(value))
    tokens = [m.group() for m in matches]
    latin_positive = {t for t in POSITIVE if t.isascii()}
    latin_negative = {t for t in NEGATIVE if t.isascii()}
    for index, token in enumerate(tokens):
        if token in latin_positive:
            if _is_negated_latin(matches, value, index):
                negative_hits += 1
            else:
                positive_hits += 1
        elif token in latin_negative:
            if _is_negated_latin(matches, value, index):
                positive_hits += 1
            else:
                negative_hits += 1

    total = positive_hits + negative_hits
    return 0.0 if total == 0 else float((positive_hits - negative_hits) / total)


def direction_from_score(score: float, threshold: float = 0.1) -> str:
    if score >= threshold:
        return "Bullish"
    if score <= -threshold:
        return "Bearish"
    return "Neutral"
