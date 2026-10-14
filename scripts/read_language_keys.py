"""Reads the language keys (TextAttributesKey) of IntelliJ IDEA and its plugins into fallback_keys.tsv.

Every key a language creates with a fallback key goes into fallback_keys.tsv, which generate_theme.py marks as
inherited, so that the key follows the language defaults (see there). The keys come straight from the compiled
classes: javap (from a JDK) prints each createTextAttributesKey("NAME", FALLBACK) call.

    python3 scripts/read_language_keys.py ["/Applications/IntelliJ IDEA.app"] [plugin folder or zip...]

Reads the IDE with its bundled plugins, the plugins installed in it, and any plugin given (a folder, or a zip
downloaded from JetBrains Marketplace, which does not need to be installed). Keys already in fallback_keys.tsv are
kept, so plugins read once stay covered. Afterwards it lists the keys that a plugin colours for Darcula, have no
known fallback and no role in language_keys.tsv yet: the scheme would show the plugin's Darcula colours for them, so
give them a role there.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FALLBACK_KEYS = ROOT / "scripts/fallback_keys.tsv"
LANGUAGE_KEYS = ROOT / "scripts/language_keys.tsv"
SCHEME = ROOT / "src/main/resources/themes/Powder.xml"

HEADER = """\
# Language keys that have a fallback key, and that fallback (its external name, or Class.FIELD where it could not be
# resolved; the IDE only reads it as "use the fallback"). Read from IntelliJ IDEA and language plugins by
# read_language_keys.py. generate_theme.py marks every one of these the scheme does not colour itself as inherited,
# so that the IDE does not fill it in from Darcula (or a plugin's colours for Darcula, such as PHP's) and the key
# follows the language defaults. Format: key<TAB>fallback.
"""

KEY_TYPE = "Lcom/intellij/openapi/editor/colors/TextAttributesKey;"
CREATE = re.compile(r"invokestatic .*TextAttributesKey\.createTextAttributesKey:\(Ljava/lang/String;(" + KEY_TYPE + r")?\)")
STRING = re.compile(r"ldc(?:_w)?\s+#\d+\s+// String (.+)$")
FIELD = re.compile(r"(getstatic|putstatic)\s+#\d+\s+// Field (?:([\w/$]+)\.)?(\w+):" + KEY_TYPE)
GETTER = re.compile(r"invoke\w+\s+#\d+\s+// \w*Method ([\w/$]+)\.get(\w+):\(\)" + KEY_TYPE)
CLASS = re.compile(r"^(?:[\w ]+ )?(?:class|interface|enum) ([\w.$]+)")


def jars(root):
    return sorted(root.rglob("*.jar")) if root.is_dir() else []


def classes_with_keys(jar):
    try:
        with zipfile.ZipFile(jar) as z:
            return [n[:-6].replace("/", ".") for n in z.namelist()
                    if n.endswith(".class") and b"createTextAttributesKey" in z.read(n)]
    except (zipfile.BadZipFile, OSError):
        return []


def read_jar(jar, keys, fields):
    """Adds {key: fallback field} to keys and {class/field: key} to fields."""
    classes = classes_with_keys(jar)
    for i in range(0, len(classes), 50):
        out = subprocess.run(["javap", "-c", "-p", "-cp", str(jar), *classes[i:i + 50]],
                             capture_output=True, text=True).stdout
        owner = name = fallback = created = None
        for line in out.splitlines():
            if m := CLASS.match(line):
                owner = m.group(1).replace(".", "/")
                name = fallback = created = None
            elif m := STRING.search(line):
                name, fallback, created = m.group(1), None, None
            elif m := FIELD.search(line):
                field = f"{m.group(2) or owner}.{m.group(3)}"  # no class: a field of this class
                if m.group(1) == "getstatic":
                    if name:
                        fallback = field
                elif created:
                    fields.setdefault(field, created)
                    created = None
            elif (m := GETTER.search(line)) and name:
                fallback = f"{m.group(1)}.{m.group(2)}"
            elif name and CREATE.search(line):
                if re.fullmatch(r"[\w .:/$-]+", name):
                    if keys.get(name) is None:
                        keys[name] = fallback
                    created = name
                name = fallback = None


def plugin_roots(paths, tmp_dirs):
    """Plugin folders; zips are unpacked into temporary folders (added to tmp_dirs)."""
    for path in paths:
        if path.suffix == ".zip":
            tmp = Path(tempfile.mkdtemp(prefix="powder-keys-"))
            tmp_dirs.append(tmp)
            with zipfile.ZipFile(path) as z:
                if any(n.endswith(".jar") for n in z.namelist()):
                    z.extractall(tmp)
                else:  # a plugin that is a single jar
                    (tmp / path.with_suffix(".jar").name).write_bytes(path.read_bytes())
            yield tmp
        else:
            yield path


def darcula_keys(roots):
    """Keys that plugins colour for Darcula (additionalTextAttributes); the scheme inherits these colours."""
    keys = set()
    for root in roots:
        plugin_jars = jars(root)
        files = set()
        for jar in plugin_jars:
            try:
                with zipfile.ZipFile(jar) as z:
                    for n in z.namelist():
                        if n.endswith(".xml") and n.count("/") <= 2:
                            text = z.read(n).decode("utf-8", "ignore")
                            for m in re.finditer(r"<additionalTextAttributes\b[^>]*>", text):
                                if 'scheme="Darcula"' in m.group(0) and (f := re.search(r'file="/?([^"]+)"', m.group(0))):
                                    files.add(f.group(1))
            except (zipfile.BadZipFile, OSError):
                pass
        for jar in plugin_jars:
            try:
                with zipfile.ZipFile(jar) as z:
                    for f in files & set(z.namelist()):
                        keys.update(re.findall(r'<option\s[^>]*name="([^"]+)"[^>]*>\s*<value', z.read(f).decode("utf-8", "ignore")))
                        keys.update(re.findall(r'<option\s+baseAttributes="[^"]+"\s+name="([^"]+)"', z.read(f).decode("utf-8", "ignore")))
            except (zipfile.BadZipFile, OSError):
                pass
    return keys


def resolve(fallback, fields):
    """External name of a fallback key, from its class.field."""
    if fallback in fields:
        return fields[fallback]
    # Kotlin getters capitalise the property (getKeyword() for KEYWORD) and may live in a companion object.
    owner, field = fallback.rsplit(".", 1)
    for name, key in fields.items():
        other, other_field = name.rsplit(".", 1)
        if other.split("$")[0] == owner.split("$")[0] and other_field.replace("_", "").lower() == field.lower():
            return key
    return f"{owner.rsplit('/', 1)[-1]}.{field}"


def main():
    args = [Path(a) for a in sys.argv[1:]]
    ide = args.pop(0) if args and args[0].suffix == ".app" else Path("/Applications/IntelliJ IDEA.app")
    installed = sorted(Path.home().glob("Library/Application Support/JetBrains/IntelliJIdea*/plugins"))
    tmp_dirs = []
    try:
        roots = [ide / "Contents/lib", ide / "Contents/plugins", *installed[-1:], *plugin_roots(args, tmp_dirs)]
        keys, fields = {}, {}
        for root in roots:
            for jar in jars(root):
                read_jar(jar, keys, fields)
        darcula = darcula_keys(roots)
    finally:
        for tmp in tmp_dirs:
            shutil.rmtree(tmp, ignore_errors=True)

    known = dict(line.split("\t") for line in FALLBACK_KEYS.read_text().splitlines()
                 if line and not line.startswith("#")) if FALLBACK_KEYS.exists() else {}
    found = {key: resolve(fb, fields) for key, fb in keys.items() if fb}
    merged = {**known, **found}
    FALLBACK_KEYS.write_text(HEADER + "".join(f"{k}\t{merged[k]}\n" for k in sorted(merged)))
    print(f"{FALLBACK_KEYS.relative_to(ROOT)}: {len(merged)} keys ({len(set(found) - set(known))} new)")

    roles = {line.split("\t")[0] for line in LANGUAGE_KEYS.read_text().splitlines()
             if line and not line.startswith("#")}
    # Keys the scheme already colours (editor keys from Darcula, the theme's own) are fine as they are.
    scheme = set(re.findall(r'<option\b[^>]*\bname="([^"]+)"', SCHEME.read_text())) if SCHEME.exists() else set()
    missing = sorted(darcula - set(merged) - roles - scheme)
    if missing:
        print(f"{len(missing)} keys a plugin colours for Darcula, without a known fallback; they would show those colours,")
        print("so give them a role in language_keys.tsv:")
        for key in missing:
            print("  " + key)

if __name__ == "__main__":
    main()
