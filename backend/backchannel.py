"""Turn-taking classifier for short acknowledgements during audible assistant speech.

This decides only whether a completed utterance yields the floor back to the
assistant. It is not a semantic judgment of the request, never inspects assistant
text and is applied only while assistant audio is audible. "yes", "no", "wait" and
"stop" are deliberately excluded: they can answer a question or redirect work.
"""
import re

ACK_TOKENS = frozenset({
    "mm", "mhm", "mmhm", "mmm", "hm", "hmm", "uh-huh", "uhhuh", "ok", "okay", "alright",
    "right", "yeah", "yep", "yup", "cool", "nice", "interesting",
})
ACK_PHRASES = frozenset({("mm", "hm"), ("uh", "huh"), ("got", "it"), ("i", "see"), ("ok", "ok"),
                         ("okay", "okay"), ("right", "right"), ("all", "right")})
MAX_TOKENS = 3


def tokens(text):
    return re.findall(r"[a-z]+(?:-[a-z]+)?", (text or "").lower())


def is_backchannel(text):
    words = tokens(text)
    if not words or len(words) > MAX_TOKENS:
        return False
    if all(word in ACK_TOKENS for word in words):
        return True
    split = [part for word in words for part in word.split("-")]
    if tuple(split) in ACK_PHRASES:
        return True
    return len(words) == 3 and tuple(words[:2]) in ACK_PHRASES and words[2] in ACK_TOKENS
