ARCHIVE_NAME = "Growa_DENUE_Sinaloa_Historico_2010_2026.zip"
ARCHIVE_SHA256 = "182c22a2a96189e47d4e0d6b5dfd2a34a09307cfa3af57b1503664cdecc1bff3"
ARCHIVE_SIZE = 14_147_652
ARCHIVE_BRANCH = "data/denue-historico"
ARCHIVE_URL = (
    "https://raw.githubusercontent.com/Murua-Alvaro/urban/"
    f"{ARCHIVE_BRANCH}/data/denue/raw/{ARCHIVE_NAME}"
)
EXPECTED_FIELDS = ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"]
