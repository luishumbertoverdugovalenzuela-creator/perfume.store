# Estado del proyecto — Perfume Store

- Tienda: 7eew11-ei.myshopify.com (nombre visible actual en el panel: "Mi tienda")
- Carpeta del proyecto: /home/user/perfume.store (repo git, rama claude/tienda-shopify-v2-5vnc08)
- Tema base: Dawn (vía zip oficial de GitHub)
- Tema de trabajo en Shopify: **"Perfume Store (Claude)"**, id `159068913896` (gid://shopify/OnlineStoreTheme/159068913896), sin publicar
- Conexión: Admin API vía app personalizada "Asistente tienda" (token propio, sin depender del login por navegador — bloqueado en este entorno)
- Producto: la tienda tiene 12 perfumes de diseñador activos (YSL, Jean Paul Gaultier, Versace, Giorgio Armani, Carolina Herrera, Bharara, Armaf, Dolce & Gabbana) con fotos propias — no se crearon productos nuevos, solo se diseñó el escaparate. La marca ("vendor") de cada uno se corrigió a la marca real (antes decía "Mi tienda" en los 12).
- Ajustes hechos tras el primer vistazo del usuario: texto oscuro invisible en héroe (corregido, color forzado en secciones oscuras), fondo blanco del frasco de portada (recortado, ahora flota con resplandor dorado), fondo crema→blanco→negro en tarjetas (según feedback), fotos de producto recortadas de forma inconsistente (cambiado a "contain"), catálogo completo (`/collections/all`) no cargaba nuestro CSS/JS (bug real: solo se cargaba dentro de nuestras propias secciones; ahora se carga globalmente desde `layout/theme.liquid`), negro cálido → negro neutro (`#121212`) por sentirse "amarillento".
- **Fondos recortados en las 12 fotos de catálogo**: se generó una versión sin fondo blanco (recorte automático por umbral de color, sin IA de pago) para la foto principal de cada uno de los 12 productos y se subió a Shopify como nueva imagen destacada (las fotos originales quedan como imágenes secundarias en la galería, no se borraron). Script usado: ver `cutout_photos.py` / `upload_cutouts.py` de la sesión (usa `stagedUploadsCreate` + `productCreateMedia` + `productReorderMedia`).

## Fases completadas
- [x] 0 Entorno
- [x] 1 Conexión (vía Admin API token, no OAuth CLI — ver nota técnica abajo)
- [x] 2 Proyecto (Dawn descargado y copiado al repo)
- [x] 3 Brief (estilo negro/dorado sobre crema, confirmado por el usuario)
- [x] 4 Construcción de secciones propias
- [x] 5 Página de producto + header/footer
- [x] 6 Publicación del tema de trabajo (sin publicar aún como definitivo)

## Decisiones de diseño
- Prefijo propio: `ps-` (Perfume Store)
- Paleta: fondo crema `#F7F2E9` / negro grafito `#16130F` / dorado `#B28A4D`
- Tipografía: Playfair Display (títulos) + Work Sans (texto)
- Nombre de marca usado en textos: "Perfume Store" (el nombre del panel sigue siendo "Mi tienda" — cambiarlo es un ajuste aparte en Configuración → General si el usuario quiere)

## Secciones creadas (prefijo ps-)
- `sections/ps-hero.liquid` — portada, título + CTA + frasco destacado
- `sections/ps-trust.liquid` — franja de confianza (4 iconos editables)
- `sections/ps-catalogo.liquid` — grid de catálogo (reutiliza `card-product` de Dawn)
- `sections/ps-historia.liquid` — sección narrativa "sobre nosotros" con cifras
- `sections/ps-resenas.liquid` — carrusel de reseñas (marquee)
- `sections/ps-faq.liquid` — acordeón de preguntas frecuentes
- `sections/ps-producto.liquid` — página de producto completa (galería, variantes, confianza, descripción)
- `sections/header-group.json` / `footer-group.json` — editados (colores oscuros de marca, anuncio, footer con marca + navegación)
- `templates/index.json` — portada montada con las secciones de arriba
- `templates/product.mt.json` — plantilla de producto (sufijo `mt`)
- `assets/ps-styles.css`, `assets/ps-scripts.js` — estilos y JS compartidos
- `assets/ps-favicon.png`, `ps-hero-bottle.png`, `ps-historia-bottle.png` — imágenes propias

## Plantilla de producto
- **Asignada automáticamente a los 11 productos activos** vía Admin API (`templateSuffix: "mt"`). Todos usan ya la página de producto nueva.

## Verificación realizada
- Portada: HTTP 200, tema y pageType correctos en server-timing, sin "Liquid error", assets propios (css/js/imágenes) responden 200.
- Página de producto (YSL Myslf): HTTP 200, tema/pageType correctos, botón "Añadir al carrito" presente, sin errores Liquid.
- No se pudo tomar captura visual con navegador automatizado por una limitación de red de este entorno (el proxy de este espacio de trabajo corta las conexiones de Chromium) — verificado por HTML/HTTP en su lugar. Recomendado: el usuario revise visualmente el enlace de previsualización.

## Enlace de previsualización
https://7eew11-ei.myshopify.com/?preview_theme_id=159068913896

## Pendiente / para el usuario
- [ ] Confirmar el estilo visual viendo el enlace de arriba
- [ ] Páginas legales (privacidad, términos, devoluciones, envíos): rellenar en Configuración → Políticas con las plantillas de Shopify
- [ ] Aviso legal y cookies: aún no redactados (pendiente, próxima tanda)
- [ ] Nombre de la tienda en el panel sigue siendo "Mi tienda" — cambiar en Configuración → General si se quiere que diga "Perfume Store"
- [ ] Publicar el tema como definitivo — SOLO con confirmación explícita del usuario (`shopify theme publish` o Admin API `themePublish`)

## Fotos de producto — mejora de calidad (22 productos, sept. 2026)
- Se reprocesaron las fotos de los 22 productos activos con `tools/enhance_product_photos.py` (gratis, sin IA de pago): nitidez suave, contraste/color más ricos, recorte de fondo transparente y una sombra elíptica de apoyo bajo el frasco para look de foto de estudio.
- **Cuidado**: valores de nitidez altos (`UnsharpMask` con `percent` alto o upscaling previo) generan halos/bandas blancas sobre los detalles facetados de los frascos — usar los valores conservadores ya calibrados en el script (`radius=1.4, percent=55, threshold=4`).
- El script sustituye la imagen `-cutout.png` anterior de cada producto (la sube nueva, reordena a posición 0, borra la anterior) — no toca la foto original de fábrica, que sigue en la galería como imagen secundaria.
- Pendiente/ofrecido al usuario: fondos generados con Leonardo AI (cuenta propia del usuario) para componer el frasco real recortado encima — aún no entregó ninguna imagen de fondo.

## Nota técnica (para continuidad de la sesión)
- El login por navegador de Shopify CLI (`shopify theme list/push` y `store auth`) está bloqueado en este entorno (Shopify rechaza con 403 el `device_authorization` del CLI). Por eso toda la conexión se hizo con una **app personalizada** (Client ID `cc2ef9889f099a66809457e62cad0977`) y un **token de acceso Admin API** (`shpat_...`, guardado solo en variables de entorno de la sesión, no en el repo).
- La subida de archivos del tema se hace con la mutación GraphQL `themeFilesUpsert` (no con `shopify theme push`, que también falla por el mismo bloqueo de login). Script de referencia: ver historial de la sesión / recrear según `references/09-admin-api.md` + introspección de `OnlineStoreThemeFilesUpsertFileInput`.
- Theme GID: `gid://shopify/OnlineStoreTheme/159068913896`
