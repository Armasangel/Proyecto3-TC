#!/usr/bin/env python3
"""
Simulador de Máquinas de Turing de una cinta (con "caché" de estado: [q, mem]).
Uso:  python mt_simulator.py machines/anbncn.yaml [--max-steps N]

Arquitectura (ver README):
  1. Parsing    -> load_machine()      : YAML -> TuringMachine (valida todo)
  2. Datos      -> Transition, TuringMachine, Tape
  3. Simulación -> simulate()          : produce lista de IDs + veredicto
  4. Salida     -> print_result()      : imprime IDs y ACEPTADA / RECHAZADA
"""
import argparse
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

BLANK = None            # En YAML el blank es null / vacío
BLANK_STR = "B"         # Cómo se dibuja el blank en pantalla
MOVES = {"L": -1, "R": 1, "S": 0}


def show(sym) -> str:
    return BLANK_STR if sym is BLANK else str(sym)


def norm(value):
    """Normaliza un valor leído de YAML: None se queda None, lo demás a str."""
    return None if value is None else str(value)


# ----------------------------------------------------------------------------
# 2. Estructuras de datos
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Transition:
    new_state: str
    new_cache: Optional[str]
    write: Optional[str]
    move: str


@dataclass
class TuringMachine:
    states: List[str]
    initial: str
    finals: set
    alphabet: set
    tape_alphabet: set
    # delta[(estado, caché, símbolo_leído)] = Transition
    delta: Dict[Tuple[str, Optional[str], Optional[str]], Transition] = field(default_factory=dict)
    strings: List[str] = field(default_factory=list)


class Tape:
    """Cinta infinita en ambos sentidos (lista que crece bajo demanda)."""

    def __init__(self, content: str):
        self.cells: List[Optional[str]] = list(content) if content else [BLANK]
        self.head = 0

    def read(self):
        return self.cells[self.head]

    def write(self, sym):
        self.cells[self.head] = sym

    def move(self, d: str):
        self.head += MOVES[d]
        if self.head < 0:
            self.cells.insert(0, BLANK)
            self.head = 0
        elif self.head >= len(self.cells):
            self.cells.append(BLANK)

    def content(self) -> str:
        """Contenido de la cinta sin blanks de los extremos."""
        idx = [i for i, c in enumerate(self.cells) if c is not BLANK]
        if not idx:
            return ""
        return "".join(show(c) if c is not BLANK else BLANK_STR
                       for c in self.cells[idx[0]:idx[-1] + 1])

    def is_all_blank(self) -> bool:
        return all(c is BLANK for c in self.cells)

    def instantaneous_description(self, state: str, cache) -> str:
        """ID:  <izquierda>[estado,caché]<símbolo bajo cabezal><derecha>"""
        idx = [i for i, c in enumerate(self.cells) if c is not BLANK]
        lo = min(idx[0], self.head) if idx else self.head
        hi = max(idx[-1], self.head) if idx else self.head
        left = "".join(show(c) for c in self.cells[lo:self.head])
        right = "".join(show(c) for c in self.cells[self.head:hi + 1])
        return f"{left}[{state},{show(cache)}]{right}"


# ----------------------------------------------------------------------------
# 1. Parsing y validación del YAML
# ----------------------------------------------------------------------------
class MTConfigError(Exception):
    pass


def load_machine(path: str) -> TuringMachine:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    try:
        q = cfg["q_states"]
        states = [str(s) for s in q["q_list"]]
        initial = str(q["initial"])
        finals_raw = q["final"]
        finals = {str(x) for x in (finals_raw if isinstance(finals_raw, list) else [finals_raw])}
        alphabet = {norm(s) for s in cfg["alphabet"] if s is not None}
        tape_alphabet = {norm(s) for s in cfg["tape_alphabet"]}   # incluye None (blank)
        delta_raw = cfg["delta"]
    except (KeyError, TypeError) as e:
        raise MTConfigError(f"Falta o es inválida una sección del YAML: {e}")

    tape_alphabet |= alphabet          # la cinta siempre contiene al alfabeto de entrada
    tape_alphabet.add(BLANK)

    if initial not in states:
        raise MTConfigError(f"Estado inicial '{initial}' no está en q_list")
    for fs in finals:
        if fs not in states:
            raise MTConfigError(f"Estado final '{fs}' no está en q_list")

    m = TuringMachine(states, initial, finals, alphabet, tape_alphabet)

    for i, item in enumerate(delta_raw):
        try:
            p, o = item["params"], item["output"]
            key = (str(p["initial_state"]), norm(p.get("mem_cache_value")), norm(p.get("tape_input")))
            tr = Transition(str(o["final_state"]), norm(o.get("mem_cache_value")),
                            norm(o.get("tape_output")), str(o["tape_displacement"]).upper())
        except (KeyError, TypeError) as e:
            raise MTConfigError(f"delta[{i}] mal formada: falta {e}")
        if key[0] not in states or tr.new_state not in states:
            raise MTConfigError(f"delta[{i}]: estado inexistente en {key[0]}->{tr.new_state}")
        if key[2] not in tape_alphabet or tr.write not in tape_alphabet:
            raise MTConfigError(f"delta[{i}]: símbolo fuera del alfabeto de cinta")
        if key[1] not in tape_alphabet or tr.new_cache not in tape_alphabet:
            raise MTConfigError(f"delta[{i}]: valor de caché fuera del alfabeto de cinta")
        if tr.move not in MOVES:
            raise MTConfigError(f"delta[{i}]: desplazamiento '{tr.move}' inválido (use L, R o S)")
        if key in m.delta:
            raise MTConfigError(f"delta[{i}]: transición duplicada para {key} (la MT debe ser determinista)")
        m.delta[key] = tr

    m.strings = [str(s) for s in (cfg.get("simulation_strings") or [])]
    for s in m.strings:
        bad = [c for c in s if c not in tape_alphabet]
        if bad:
            raise MTConfigError(f"La cadena '{s}' tiene símbolos fuera del alfabeto: {sorted(set(bad))}")
    return m


# ----------------------------------------------------------------------------
# 3. Simulación
# ----------------------------------------------------------------------------
@dataclass
class Result:
    ids: List[str]
    accepted: bool
    reason: str
    final_tape: str
    steps: int


def simulate(m: TuringMachine, string: str, max_steps: int = 10000) -> Result:
    tape = Tape(string)
    state, cache = m.initial, None
    ids = [tape.instantaneous_description(state, cache)]
    steps = 0

    while True:
        if state in m.finals:
            return Result(ids, True, f"se alcanzó el estado final '{state}'", tape.content(), steps)
        if steps >= max_steps:
            return Result(ids, False, f"se superó el límite de {max_steps} pasos (posible ciclo infinito)",
                          tape.content(), steps)
        tr = m.delta.get((state, cache, tape.read()))
        if tr is None:
            return Result(ids, False,
                          f"no hay transición para ([{state},{show(cache)}], {show(tape.read())})",
                          tape.content(), steps)
        tape.write(tr.write)
        tape.move(tr.move)
        state, cache = tr.new_state, tr.new_cache
        steps += 1
        ids.append(tape.instantaneous_description(state, cache))


# ----------------------------------------------------------------------------
# 4. Salida
# ----------------------------------------------------------------------------
def print_result(string: str, r: Result):
    print("=" * 70)
    print(f"Cadena de entrada: {string}")
    print("-" * 70)
    w = len(str(len(r.ids) - 1))
    for i, d in enumerate(r.ids):
        print(f"  {i:>{w}}  {'' if i == 0 else '⊢ '}{d}")
    print("-" * 70)
    print(f"Pasos: {r.steps}   |   Cinta final: {r.final_tape or '(vacía)'}")
    print(f"Resultado: {'ACEPTADA ✔' if r.accepted else 'RECHAZADA ✘'}  ({r.reason})")
    print()


def main():
    ap = argparse.ArgumentParser(description="Simulador de Máquinas de Turing de una cinta")
    ap.add_argument("yaml_file")
    ap.add_argument("--max-steps", type=int, default=10000, help="límite de pasos por cadena")
    args = ap.parse_args()
    try:
        m = load_machine(args.yaml_file)
    except (MTConfigError, OSError, yaml.YAMLError) as e:
        sys.exit(f"Error al cargar la MT: {e}")
    print(f"MT cargada: {len(m.states)} estados, {len(m.delta)} transiciones, "
          f"{len(m.strings)} cadenas a simular.\n")
    for s in m.strings:
        print_result(s, simulate(m, s, args.max_steps))


if __name__ == "__main__":
    main()
