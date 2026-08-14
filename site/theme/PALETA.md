# Paleta del tema

Esta es **la** paleta del template. Cualquier color nuevo —un gráfico, un bloque, un badge— sale de
acá o de una mezcla de estos colores con el fondo. Nada de colores sueltos: es lo que mantiene la
coherencia entre el HTML, los gráficos de matplotlib y los dos temas.

Es una escala **divergente**: cálida en un extremo, fría en el otro, y crema en el medio.

| # | Hex | Tono |
|---|---|---|
| 1 | `#4D0507` | rojo casi negro |
| 2 | `#6D2312` | marrón rojizo |
| 3 | `#913D1A` | óxido oscuro |
| 4 | `#B45B23` | óxido |
| 5 | `#D77B30` | naranja tierra |
| 6 | `#F3A452` | naranja claro |
| 7 | `#FDD08E` | arena |
| 8 | `#FFFFDE` | crema |
| 9 | `#B3E0CC` | menta |
| 10 | `#6CBFB6` | verde agua |
| 11 | `#389E9C` | turquesa |
| 12 | `#20767C` | petróleo claro |
| 13 | `#0E5C5E` | petróleo |
| 14 | `#064042` | petróleo oscuro |
| 15 | `#042728` | casi negro verdoso |

## Cómo se reparten los roles

La lógica es la misma en los dos temas, invertida: **el extremo frío es fondo en oscuro y tinta en
claro**, y el extremo cálido es siempre el acento.

| Rol | Oscuro (por defecto) | Claro |
|---|---|---|
| Fondo de página | `#042728` | `#FFFFDE` |
| Fondo alterno (zebra, chips) | mezcla `#08383A` | mezcla `#FEF3CA` |
| Tarjetas y salidas de celda | `#064042` | crema aclarado `#FFFFF0` |
| Bordes | `#0E5C5E` | mezcla `#D2E4CA` |
| Tinta principal | `#FFFFDE` | `#042728` |
| Párrafos | mezcla menta `#CDE7DA` | `#0E5C5E` |
| Metadatos | `#6CBFB6` | `#20767C` |
| Acento de marca (h1, h3, índice activo) | `#F3A452` | `#913D1A` |
| Enlaces e info (`.note`) | `#6CBFB6` | `#20767C` |
| Advertencia | `#FDD08E` | `#B45B23` |
| Error (`.pitfall`) | `#F3A452` sobre `#301314` | `#4D0507` sobre `#F5D9C4` |
| Correcto (`.good`) | `#B3E0CC` sobre `#2A504C` | `#20767C` sobre `#DDF1D6` |
| Banner del título | `#02191A` | `#042728` |
| Cabecera de tabla | `#0E5C5E` | `#0E5C5E` |
| Bloques de código | `#02191A` | `#042728` |

Los fondos tenues de `.note`, `.pitfall` y `.good` **no** son colores de la paleta: son mezclas de un
color de la paleta con el fondo base, porque la paleta no tiene tintes tan suaves. Cada uno está
anotado en el SCSS con el color del que sale.

## Cómo cambiar la paleta

1. Reemplazar los quince colores por los nuevos, respetando el orden cálido → frío.
2. Actualizar las variables de los dos archivos de paleta (`tema-oscuro.scss` y `tema-claro.scss`).
   Los nombres de variable no cambian: solo los valores.
3. Actualizar el diccionario `PALETTE` y las escalas `SEQUENTIAL` / `DIVERGING` de `utils.py`, que es
   el espejo de la paleta para los gráficos.
4. Actualizar esta tabla.

`_base.scss` no se toca: no define ni un color, solo usa las variables. Por eso un cambio de
estructura se hace una vez y vale para los dos temas, y un cambio de color se hace en los dos archivos
de paleta.

## Dónde vive cada cosa

```
theme/
├── _base.scss         estructura y componentes · NO define ni un color
├── tema-oscuro.scss   paleta oscura → tema por defecto
└── tema-claro.scss    paleta clara  → alternativa del botón
utils.py               PALETTE, SEQUENTIAL y DIVERGING para matplotlib
```

## Por qué los gráficos tienen fondo crema en los dos temas

Una figura de matplotlib es una imagen: se genera una sola vez y no cambia cuando el lector alterna
entre tema claro y oscuro. Por eso todas se generan con fondo `#FFFFDE`, que en el tema claro se
integra con la página y en el oscuro queda enmarcada como una lámina —el CSS del tema oscuro les
agrega el marco y el padding. Es la única forma de que la misma imagen funcione en los dos.
