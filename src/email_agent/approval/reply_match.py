import string
from enum import StrEnum

YES_WORDS = frozenset({"yes", "approve", "approved"})
NO_WORDS = frozenset({"no", "reject", "rejected"})


class Answer(StrEnum):
    YES = "yes"
    NO = "no"
    NO_MATCH = "no match"


def read_first_word(text: str) -> str:
    """
    @example
    read_first_word("  REJECTED. Not now") == "rejected"
    """
    words = text.split()
    return words[0].casefold().rstrip(string.punctuation) if words else ""


def match_reply(text: str) -> Answer:
    """
    @example
    match_reply("Yes, enjoy") is Answer.YES
    match_reply("Who is Jane?") is Answer.NO_MATCH
    """
    first_word = read_first_word(text)
    if first_word in YES_WORDS:
        return Answer.YES
    if first_word in NO_WORDS:
        return Answer.NO
    return Answer.NO_MATCH
