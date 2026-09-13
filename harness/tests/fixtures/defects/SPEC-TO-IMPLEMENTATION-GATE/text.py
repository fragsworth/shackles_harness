_CACHE = {}


def shout(text):
    return text.upper()


def whisper(text):
    if text in _CACHE:
        return _CACHE[text]
    _CACHE[text] = text.lower()
    return _CACHE[text]


def yell(text):
    return text.upper() + "!!!"
