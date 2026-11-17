# Proyecto 3 – Simulador de Máquinas de Turing (1 cinta)

Integrantes: Angel Armas (24714), José Ovando (24701) |  Video:

## Requisitos y ejecución

```bash
pip install pyyaml
python mt_simulator.py machines/anbncn.yaml     # MT reconocedora
python mt_simulator.py machines/reverse.yaml    # MT alteradora
python mt_simulator.py <archivo.yaml> --max-steps 5000   # (opcional) límite de pasos
```

## Formato del YAML

Es el de la especificación: `q_states` (`q_list`, `initial`, `final`), `alphabet`, `tape_alphabet`
(el blank es `null`), `delta` (`params`/`output` con `mem_cache_value`) y `simulation_strings`.
Notas: `null`/vacío = blank o caché vacía; cada símbolo es **un carácter**; la MT debe ser determinista;
`final` puede ser un estado o una lista.

## Arquitectura (`mt_simulator.py`)

| Parte | Qué hace |
| --- | --- |
| `load_machine()` | **Parsing**: lee el YAML y valida (estados existentes, símbolos en el alfabeto, L/R/S, transiciones duplicadas, cadenas válidas) |
| `Transition`, `TuringMachine` | Estructuras de datos. `delta` es un **diccionario** `(estado, caché, símbolo) -> Transition`, así buscar la transición es O(1) |
| `Tape` | Cinta como lista que crece a izquierda/derecha cuando el cabezal se sale; genera las IDs |
| `simulate()` | Bucle: si el estado es final → **acepta**; si no hay transición → **rechaza**; si no, escribe, mueve, cambia estado/caché y guarda la ID. Tiene límite de pasos contra ciclos infinitos |
| `print_result()` | Imprime la lista completa de IDs y ACEPTADA/RECHAZADA |

**Formato de ID:** `izquierda[estado,caché]símbolo_bajo_cabezal derecha`. Ejemplo: `XaY[q2,B]bcc` =
estado q2, caché vacía (`B`), cabezal sobre la `b`. `B` representa el blank.

## MT 1 – Reconocedora: `{ aⁿbⁿcⁿ | n ≥ 1 }` (`machines/anbncn.yaml`)

Cada ronda marca una `a`→`X`, la primera `b`→`Y`, la primera `c`→`Z`, y regresa a la `X` más a la derecha.
Cuando ya no hay `a`, verifica que solo queden `Y`/`Z` y llega a `qf`.

- Aceptadas: `aabbcc`, `aaabbbccc`
- Rechazadas: `aabbbcc`, `aaabbbcc`, `abcabc`

## MT 2 – Alteradora: invertir cadena sobre {a,b} (`machines/reverse.yaml`)

Usa `mem_cache_value` para **intercambiar los extremos**: guarda el símbolo de la izquierda en la caché,
va al extremo derecho, escribe el símbolo guardado y carga el que leyó, regresa y lo escribe en el hueco.
Los símbolos ya intercambiados se marcan en mayúscula (`A`,`B`) y `x` marca el hueco; al final una
pasada los vuelve a minúscula. Funciona para longitud par e impar.

- Entradas: `abbab → babba`, `aaabb → bbaaa`, `ababababa → ababababa`, `abbbaaab → baaabbba`

- Cadena vacía (todo blank) → rechazada.
