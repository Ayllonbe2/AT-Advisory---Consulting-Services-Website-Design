# Código fuente de atadvisory.es

La web es HTML estático. Las páginas publicadas (`index.html`, `en/index.html`, `fr/index.html` y `sitemap.xml`) se **generan** a partir de esta carpeta con un script de Python que no necesita instalar nada:

```bash
python _src/build.py           # genera las páginas
python _src/build.py --check   # comprueba que lo publicado está al día con _src/
```

No edites a mano los archivos generados: llevan un aviso al principio y se sobrescriben en cada generación. GitHub Pages no publica esta carpeta, porque Jekyll omite las que empiezan por `_`.

## Qué hay en cada sitio

| Archivo | Para qué sirve |
| --- | --- |
| `config.json` | URL de la web, correo, clave de Web3Forms, idiomas, datos del negocio (JSON-LD) y lista de páginas. |
| `layout.html` | Estructura común de todas las páginas: `<head>`, cabecera con menú y selector de idioma, y pie. |
| `pages/home.html` | Contenido de la portada (todas las secciones de la one-page). |
| `i18n/es.json`, `en.json`, `fr.json` | Textos por idioma. |
| `../assets/site.css` | Estilos propios de la web, cargados después de `styles.css` (el sistema de diseño). |
| `../assets/site.js` | Interacciones: tarjeta de la portada, aparición al hacer scroll, «Copiar correo» y envío del formulario. |

## Cómo funcionan los textos

- **El español está escrito directamente en las plantillas.** Cada texto traducible lleva un `data-i18n="clave"`:
  `<h2 data-i18n="servicesTitle">Tecnología útil…</h2>`.
- **El inglés y el francés están en `i18n/en.json` e `i18n/fr.json`**, con las mismas claves. Si falta una traducción, el script se detiene y dice cuál.
- `i18n/es.json` solo contiene los textos que no están en las plantillas: títulos y descripciones de la página (`meta.*`), datos del JSON-LD (`ld.*`), mensajes del formulario y etiquetas de accesibilidad.
- Al generar, el script une con un espacio de no separación las dos últimas palabras de cada texto, para que ningún párrafo acabe con una palabra sola (igual que hacía antes el navegador).
- En atributos se usa `{{t:clave}}`, por ejemplo `aria-label="{{t:navMenu}}"`.

Para cambiar un texto: edita la plantilla (español) y el JSON de cada idioma, y vuelve a generar.

## Formulario de contacto

Con `"web3formsKey": ""`, el botón «Enviar consulta» abre el programa de correo del visitante con el mensaje ya redactado. El botón «Copiar correo» funciona siempre.

Para que el formulario envíe directamente desde la web:

1. Crea una clave gratuita en <https://web3forms.com> con el correo que debe recibir los mensajes.
2. Pégala en `config.json` → `"web3formsKey"` (es pública por diseño; puede ir en el HTML).
3. Ejecuta `python _src/build.py` y publica.

El formulario mostrará «Enviando…», «¡Gracias!» o un error con el correo de contacto, sin salir de la página. Incluye un campo trampa (`botcheck`) contra bots.

## Idiomas y SEO

Cada idioma tiene su URL: `/` (español), `/en/` y `/fr/`. Cada página lleva su `<html lang>`, `canonical`, enlaces `hreflang` (incluido `x-default`), etiquetas Open Graph y JSON-LD traducido. Las banderas del menú son enlaces normales entre esas URLs. `sitemap.xml` se genera con las alternativas de idioma, y `robots.txt` (en la raíz, escrito a mano) apunta a él.

## Añadir una página (por ejemplo /visibilidad-ia-pymes)

1. Crea `pages/visibilidad-ia.html` solo con el contenido (secciones). La cabecera, el pie y los estilos salen de `layout.html`. Dentro puedes usar `{{root}}` para rutas de imágenes y `{{home}}#contact` para enlazar a secciones de la portada.
2. Añádela a `config.json`:
   ```json
   { "id": "visibilidad-ia", "template": "pages/visibilidad-ia.html",
     "path": { "es": "visibilidad-ia-pymes", "en": "ai-visibility", "fr": "visibilite-ia" } }
   ```
3. Añade en los tres JSON sus `meta.visibilidad-ia.title` y `meta.visibilidad-ia.description` (y `meta.visibilidad-ia.ogTitle` si quieres otro título al compartir), y las traducciones de sus textos.
4. Genera. Saldrán `/visibilidad-ia-pymes/`, `/en/ai-visibility/` y `/fr/visibilite-ia/`, ya con hreflang y en el sitemap. Después, enlázala desde la tarjeta de servicio o proyecto que corresponda.
