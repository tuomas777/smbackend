import re


def clean_text(text):
    if not isinstance(text, str):
        return text
    # remove consecutive whitespaces
    text = re.sub(r'\s\s+', ' ', text, re.U)
    # remove nil bytes
    text = text.replace('\u0000', ' ')
    text = text.replace("\r", "\n")
    text = text.replace('\\r', "\n")
    text = text.strip()
    if len(text) == 0:
        return None
    return text
