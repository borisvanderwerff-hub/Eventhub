"""Testpakket voor de EventHub-server.

Deze module draait voordat er ook maar een test wordt geimporteerd, en zet de
gegevensmap van de server op een tijdelijke plek. Zonder dat schrijft elke
testronde echte sessiemappen in de map van de gebruiker: XDG_DATA_HOME werkt
alleen op Linux, dus op Windows kwam alles gewoon in %LOCALAPPDATA% terecht.
"""
import os
import tempfile
from pathlib import Path

_TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix="eventhub_server_tests_"))
os.environ["EVENTHUB_SERVER_DATA"] = str(_TEST_DATA_ROOT)
os.environ.setdefault("XDG_DATA_HOME", str(_TEST_DATA_ROOT))
