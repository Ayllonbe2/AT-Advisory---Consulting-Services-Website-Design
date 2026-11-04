#!/usr/bin/env python3
"""Genera las páginas estáticas de atadvisory.es a partir de _src/.

    python _src/build.py           # escribe las páginas y sitemap.xml
    python _src/build.py --check   # solo comprueba que lo publicado está al día

Lee _src/config.json, _src/layout.html, _src/pages/*.html y _src/i18n/*.json.
Escribe index.html (español), en/index.html, fr/index.html, las páginas que se
añadan en config.json y sitemap.xml. Solo usa la biblioteca estándar de Python 3.
"""
from __future__ import annotations

import html
import json
import posixpath
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
GENERATED = ("<!-- Generado por _src/build.py. No edites este archivo: "
             "cambia _src/ y vuelve a ejecutar «python _src/build.py». -->")
WEB3FORMS = "https://api.web3forms.com/submit"

TOKEN = re.compile(r"<!--.*?-->|<[^>]+>|[^<]+", re.S)
TAG = re.compile(r"<\s*(/)?\s*([a-zA-Z][\w-]*)")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
I18N_ATTR = re.compile(r'\sdata-i18n="([^"]+)"')
PLACEHOLDER = re.compile(r"\{\{([^{}]+)\}\}")


class BuildError(Exception):
    pass


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def no_widow(text: str) -> str:
    """Join the last two words with a non-breaking space, so a paragraph never ends on a lone word."""
    words = text.strip().split()
    if len(words) < 4 or len(words[-1]) > 12:
        return text
    return re.sub(r"\s+(\S+)\s*$", " \\1", text)


def esc_text(text: str) -> str:
    return html.escape(text, quote=False).replace(" ", "&nbsp;")


def esc_attr(text: str) -> str:
    return html.escape(text, quote=True)


def rel(from_dir: str, to_dir: str) -> str:
    """Relative URL between two page directories ('' is the site root, 'en/' a sub-directory)."""
    r = posixpath.relpath(to_dir.rstrip("/") or ".", from_dir.rstrip("/") or ".")
    return "./" if r == "." else r + "/"


# ----------------------------------------------------------------- HTML i18n
def is_element(tok: str) -> bool:
    return tok.startswith("<") and not tok.startswith("<!--") and TAG.match(tok) is not None


def opens(tok: str) -> bool:
    m = TAG.match(tok)
    return not m.group(1) and m.group(2).lower() not in VOID and not tok.rstrip().endswith("/>")


def i18n_elements(tokens: list[str]):
    """(start, end, key) for every element that carries data-i18n."""
    found, stack = [], []
    for i, tok in enumerate(tokens):
        if not is_element(tok):
            continue
        m = TAG.match(tok)
        name = m.group(2).lower()
        if m.group(1):
            while stack:
                n, start, key = stack.pop()
                if n == name:
                    if key:
                        found.append((start, i, key))
                    break
            continue
        key = I18N_ATTR.search(tok)
        if not opens(tok):
            if key:
                raise BuildError(f"data-i18n en un elemento vacío: {tok[:80]}")
            continue
        stack.append((name, i, key.group(1) if key else None))
    return found


def text_content(tokens: list[str], start: int, end: int) -> str:
    return html.unescape("".join(t for t in tokens[start + 1:end] if not t.startswith("<")))


def direct_text(tokens: list[str], start: int, end: int) -> list[int]:
    depth, slots = 0, []
    for i in range(start + 1, end):
        tok = tokens[i]
        if is_element(tok):
            if TAG.match(tok).group(1):
                depth -= 1
            elif opens(tok):
                depth += 1
        elif not tok.startswith("<") and depth == 0 and tok.strip():
            slots.append(i)
    return slots


def base_texts(markup: str) -> dict[str, str]:
    tokens = TOKEN.findall(markup)
    return {key: text_content(tokens, s, e) for s, e, key in i18n_elements(tokens)}


def translate(markup: str, lookup) -> str:
    """Put each data-i18n element's text in place (as the old client-side script did) and drop the attribute."""
    tokens = TOKEN.findall(markup)
    for start, end, key in i18n_elements(tokens):
        text = esc_text(no_widow(lookup(key, text_content(tokens, start, end))))
        if any(is_element(t) for t in tokens[start + 1:end]):
            slots = direct_text(tokens, start, end)
            if slots:
                tokens[slots[-1]] = text
            else:
                tokens[end] = text + tokens[end]
        else:
            for i in range(start + 1, end):
                tokens[i] = ""
            tokens[end] = text + tokens[end]
        tokens[start] = I18N_ATTR.sub("", tokens[start], count=1)
    return "".join(tokens)


def fill(markup: str, values: dict[str, str], t) -> str:
    def repl(m):
        name = m.group(1).strip()
        if name.startswith("t:"):
            return esc_attr(t(name[2:]))
        if name not in values:
            raise BuildError(f"marcador desconocido {{{{{name}}}}}")
        return values[name]
    return PLACEHOLDER.sub(repl, markup)


# ----------------------------------------------------------------- site model
class Site:
    def __init__(self):
        self.config = json.loads(read(SRC / "config.json"))
        self.url = self.config["siteUrl"].rstrip("/")
        self.email = self.config["email"]
        self.key = self.config.get("web3formsKey", "").strip()
        self.langs = self.config["languages"]
        self.default = self.langs[0]["code"]
        self.layout = read(SRC / "layout.html")
        self.strings = {l["code"]: json.loads(read(SRC / "i18n" / f"{l['code']}.json")) for l in self.langs}
        self.missing: dict[str, set[str]] = {}
        self.used: dict[str, set[str]] = {l["code"]: set() for l in self.langs}

    def page_dir(self, page: dict, lang: dict) -> str:
        path = page.get("path", "")
        if isinstance(path, dict):
            path = path[lang["code"]]
        path = path.strip("/")
        return lang["dir"] + (path + "/" if path else "")

    def page_url(self, page: dict, lang: dict) -> str:
        return f"{self.url}/{self.page_dir(page, lang)}"

    def lookup(self, code: str, base: dict[str, str]):
        strings = self.strings[code]

        def get(key: str, fallback: str | None = None):
            self.used[code].add(key)
            if key in strings:
                value = strings[key]
            elif code == self.default and (fallback is not None or key in base):
                value = fallback if fallback is not None else base[key]
            else:
                self.missing.setdefault(code, set()).add(key)
                return f"[{key}]"
            return value.replace("{email}", self.email) if isinstance(value, str) else value
        return get

    def jsonld(self, page: dict, lang: dict, t, title: str) -> dict:
        biz = self.config["business"]
        services, i = [], 1
        while True:
            name = t(f"svc{i}Title", None) if self.has(lang, f"svc{i}Title") else None
            if not name:
                break
            services.append({"@type": "Offer", "itemOffered": {
                "@type": "Service", "name": name, "description": t(f"svc{i}Text")}})
            i += 1
        area = t("ld.areaServed")
        business = {
            "@type": "ProfessionalService",
            "@id": f"{self.url}/#business",
            "name": biz["name"],
            "alternateName": biz["alternateName"],
            "url": f"{self.url}/",
            "logo": f"{self.url}/logo-mark.svg",
            "description": t("ld.description"),
            "email": self.email,
            "address": {"@type": "PostalAddress", "addressLocality": biz["locality"], "addressCountry": biz["country"]},
            "areaServed": [{"@type": "Country", "name": area[0]}, {"@type": "Place", "name": area[1]}],
            "knowsLanguage": [l["code"] for l in self.langs],
            "knowsAbout": t("ld.knowsAbout"),
            "founder": {"@type": "Person", **biz["founder"], "jobTitle": t("ld.jobTitle")},
            "hasOfferCatalog": {"@type": "OfferCatalog", "name": t("ld.catalog"), "itemListElement": services},
        }
        webpage = {
            "@type": "WebPage",
            "@id": self.page_url(page, lang) + "#webpage",
            "url": self.page_url(page, lang),
            "name": title,
            "inLanguage": lang["code"],
            "about": {"@id": f"{self.url}/#business"},
        }
        return {"@context": "https://schema.org", "@graph": [business, webpage]}

    def has(self, lang: dict, key: str) -> bool:
        return key in self.strings[lang["code"]] or key in self._base

    def head(self, page: dict, lang: dict, t) -> str:
        pid = page["id"]
        title = t(f"meta.{pid}.title")
        desc = t(f"meta.{pid}.description")
        og_title = t(f"meta.{pid}.ogTitle") if f"meta.{pid}.ogTitle" in self.strings[lang["code"]] else title
        url = self.page_url(page, lang)
        lines = [
            f"<title>{esc_text(title)}</title>",
            f'<meta name="description" content="{esc_attr(desc)}">',
            f'<link rel="canonical" href="{url}">',
        ]
        lines += [f'<link rel="alternate" hreflang="{l["code"]}" href="{self.page_url(page, l)}">' for l in self.langs]
        lines += [
            f'<link rel="alternate" hreflang="x-default" href="{self.page_url(page, self.langs[0])}">',
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="AT Advisory">',
            f'<meta property="og:url" content="{url}">',
            f'<meta property="og:title" content="{esc_attr(og_title)}">',
            f'<meta property="og:description" content="{esc_attr(desc)}">',
            f'<meta property="og:locale" content="{lang["ogLocale"]}">',
        ]
        lines += [f'<meta property="og:locale:alternate" content="{l["ogLocale"]}">' for l in self.langs if l is not lang]
        if page.get("jsonld"):
            data = json.dumps(self.jsonld(page, lang, t, title), ensure_ascii=False, indent=2)
            lines.append(f'<script type="application/ld+json">\n{data}\n</script>')
        return "\n".join(lines)

    def form(self) -> dict[str, str]:
        if not self.key:
            return {"form_action": f"mailto:{esc_attr(self.email)}", "form_enctype": ' enctype="text/plain"',
                    "form_key": "", "form_hidden": "", "fnote_key": "fNote"}
        hidden = (
            f'        <input type="hidden" name="access_key" value="{esc_attr(self.key)}">\n'
            '        <input type="hidden" name="subject" value="Nueva consulta desde atadvisory.es">\n'
            '        <input type="hidden" name="from_name" value="Web atadvisory.es">\n'
            '        <input type="checkbox" name="botcheck" class="form-trap" tabindex="-1" autocomplete="off" aria-hidden="true">\n'
        )
        return {"form_action": WEB3FORMS, "form_enctype": "", "form_key": esc_attr(self.key),
                "form_hidden": hidden, "fnote_key": "fNoteSend"}

    def render(self, page: dict, lang: dict) -> str:
        content = read(SRC / page["template"])
        markup = self.layout.replace("{{content}}", content)
        self._base = base_texts(markup)
        t = self.lookup(lang["code"], self._base)
        self.used[lang["code"]].update({"fNote", "fNoteSend"})  # only one of the two notes shows, depending on the form setup
        here = self.page_dir(page, lang)
        home_dir = lang["dir"]
        is_home = page["id"] == "home"
        values = {
            "generated": GENERATED,
            "lang": lang["code"],
            "root": "../" * here.count("/"),
            "home": "" if is_home else rel(here, home_dir),
            "home_top": "#" if is_home else rel(here, home_dir),
            "flag": lang["flag"],
            "langName": lang["name"],
            "email": esc_attr(self.email),
            **self.form(),
        }
        for other in self.langs:
            values[f"alt:{other['code']}"] = rel(here, self.page_dir(page, other))
            values[f"cur:{other['code']}"] = ' aria-current="page"' if other is lang else ""
        values["head"] = self.head(page, lang, t)
        out = translate(fill(markup, values, t), t)
        if "{{" in out.replace(values["head"], "") or "data-i18n" in out:
            raise BuildError(f"{here or '/'}: quedan marcadores sin resolver")
        return out

    def sitemap(self) -> str:
        rows = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
        for page in self.config["pages"]:
            for lang in self.langs:
                rows.append("  <url>")
                rows.append(f"    <loc>{self.page_url(page, lang)}</loc>")
                for other in self.langs:
                    rows.append(f'    <xhtml:link rel="alternate" hreflang="{other["code"]}" href="{self.page_url(page, other)}"/>')
                rows.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{self.page_url(page, self.langs[0])}"/>')
                rows.append("  </url>")
        rows.append("</urlset>")
        return "\n".join(rows) + "\n"

    def outputs(self) -> dict[Path, str]:
        files = {}
        for page in self.config["pages"]:
            for lang in self.langs:
                files[ROOT / self.page_dir(page, lang) / "index.html"] = self.render(page, lang)
        files[ROOT / "sitemap.xml"] = self.sitemap()
        if self.missing:
            detail = "; ".join(f"{code}: {', '.join(sorted(keys))}" for code, keys in self.missing.items())
            raise BuildError(f"faltan traducciones ({detail})")
        return files

    def unused(self) -> dict[str, list[str]]:
        return {code: sorted(set(strings) - self.used[code]) for code, strings in self.strings.items()
                if set(strings) - self.used[code]}


def main() -> int:
    check = "--check" in sys.argv[1:]
    try:
        site = Site()
        files = site.outputs()
    except BuildError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    stale = []
    for path, text in files.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    for code, keys in site.unused().items():
        print(f"Aviso: textos de {code}.json que no usa ninguna página: {', '.join(keys)}")
    if check:
        if stale:
            print("Desactualizado:", ", ".join(str(p.relative_to(ROOT)) for p in stale))
            return 1
        print("Todo al día.")
        return 0
    print("Generado:", ", ".join(str(p.relative_to(ROOT)).replace("\\", "/") for p in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
