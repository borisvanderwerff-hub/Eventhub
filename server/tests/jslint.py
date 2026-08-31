"""Structuurcontrole voor de scripts van de browserassistent.

Er is in deze omgeving geen JavaScript-parser beschikbaar: node ontbreekt en de
QJSEngine van PySide6 kent geen moderne syntaxis. Regex over de hele tekst
werkt hier niet: commentaar eerst verwijderen breekt de dubbele schuine streep
in http://, en strings eerst verwijderen breekt een apostrof in Nederlands
commentaar.

Daarom een scanner die de tekst een keer van links naar rechts doorloopt en
per teken bijhoudt waar hij is. Dat is precies genoeg om de fout te vangen die
bij handmatig bewerken het vaakst optreedt: haakjes die niet sluiten.
"""
from __future__ import annotations

PAIRS = {")": "(", "]": "[", "}": "{"}
# Na deze tekens begint een schuine streep een reguliere expressie en geen
# deling; dat onderscheid is nodig om /pad/ in een regex niet als deling te
# lezen.
REGEX_ALLOWED_AFTER = set("=(,:[!&|?{};+-*%<>~^\n")


def _scan(source: str):
    """Loop de bron door en geef de haakjes buiten strings en commentaar."""
    index = 0
    line = 1
    length = len(source)
    previous_meaningful = "\n"
    template_depth = []

    while index < length:
        char = source[index]
        nxt = source[index + 1] if index + 1 < length else ""

        if char == "\n":
            line += 1
            index += 1
            continue

        if char == "/" and nxt == "/":
            while index < length and source[index] != "\n":
                index += 1
            continue

        if char == "/" and nxt == "*":
            index += 2
            while index < length and not (source[index] == "*" and source[index + 1:index + 2] == "/"):
                if source[index] == "\n":
                    line += 1
                index += 1
            index += 2
            continue

        if char in "\"'":
            quote = char
            index += 1
            while index < length and source[index] != quote:
                if source[index] == "\\":
                    index += 1
                elif source[index] == "\n":
                    line += 1
                index += 1
            index += 1
            previous_meaningful = quote
            continue

        if char == "`":
            index += 1
            while index < length:
                if source[index] == "\\":
                    index += 2
                    continue
                if source[index] == "`":
                    break
                # ${ ... } binnen een template bevat gewone code.
                if source[index] == "$" and source[index + 1:index + 2] == "{":
                    depth = 1
                    index += 2
                    while index < length and depth:
                        if source[index] == "{":
                            depth += 1
                        elif source[index] == "}":
                            depth -= 1
                        elif source[index] == "\n":
                            line += 1
                        index += 1
                    continue
                if source[index] == "\n":
                    line += 1
                index += 1
            index += 1
            previous_meaningful = "`"
            continue

        if char == "/" and previous_meaningful in REGEX_ALLOWED_AFTER:
            index += 1
            in_class = False
            while index < length:
                if source[index] == "\\":
                    index += 2
                    continue
                if source[index] == "[":
                    in_class = True
                elif source[index] == "]":
                    in_class = False
                elif source[index] == "/" and not in_class:
                    break
                elif source[index] == "\n":
                    break
                index += 1
            index += 1
            while index < length and source[index] in "gimsuyd":
                index += 1
            previous_meaningful = "/"
            continue

        if char in "([{)]}":
            yield char, line

        if not char.isspace():
            previous_meaningful = char
        index += 1


def check_brackets(source: str) -> str | None:
    """Geef een omschrijving van het eerste probleem, of None."""
    stack = []
    for char, line in _scan(source):
        if char in "([{":
            stack.append((char, line))
        elif not stack or stack.pop()[0] != PAIRS[char]:
            return f"onverwachte {char} op regel {line}"
    if stack:
        char, line = stack[-1]
        return f"{char} van regel {line} wordt niet gesloten"
    return None
