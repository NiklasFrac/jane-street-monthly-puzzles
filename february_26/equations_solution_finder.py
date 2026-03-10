from __future__ import annotations

from fractions import Fraction
from itertools import product
from math import isqrt
from typing import Callable, Iterable, List, Tuple, Union, Dict


# ---------------------------
# 1) Parameterraum definieren
# ---------------------------
# Disjunkte Intervalle: Liste von (lo, hi) inklusiv.
# lo/hi dürfen int, float, str ("0.25") oder Fraction sein.
A_INTERVALS = [(-10, 10)]
B_INTERVALS = [(-10, 8)]
C_INTERVALS = [(-10, 10)]

# "Knopf" für die Schrittgröße (Accuracy).
# Empfehlung: als STRING setzen, um Rundungsartefakte zu vermeiden (z.B. "0.25", "0.125", "2").
ACCURACY: Union[str, int, float, Fraction] = "0.25"


def to_fraction(x: Union[str, int, float, Fraction]) -> Fraction:
    """Robuste Konvertierung nach Fraction (float/str werden als Dezimaldarstellung interpretiert)."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x, 1)
    return Fraction(str(x))


def expand_intervals(
    intervals: List[Tuple[Union[str, int, float, Fraction], Union[str, int, float, Fraction]]],
    step: Union[str, int, float, Fraction],
) -> List[Fraction]:
    """
    Union (disjunkter oder überlappender) inklusiver Intervalle mit Schrittweite `step`.
    Gibt sortierte Fractions zurück.
    """
    h = to_fraction(step)
    if h <= 0:
        raise ValueError("ACCURACY/step muss > 0 sein.")

    vals = set()
    for lo_raw, hi_raw in intervals:
        lo = to_fraction(lo_raw)
        hi = to_fraction(hi_raw)

        if lo <= hi:
            x = lo
            while x <= hi:
                vals.add(x)
                x += h
        else:
            x = lo
            while x >= hi:
                vals.add(x)
                x -= h

    return sorted(vals)


A_VALUES = expand_intervals(A_INTERVALS, ACCURACY)
B_VALUES = expand_intervals(B_INTERVALS, ACCURACY)
C_VALUES = expand_intervals(C_INTERVALS, ACCURACY)


# ---------------------------------------
# 2) Hilfsfunktionen: exakte Arithmetik
# ---------------------------------------
def pow_int_as_fraction(base: Fraction, exp: Fraction) -> Fraction:
    """
    Exakte Potenz für GANZZAHLIGE Exponenten (exp muss Integer sein), als Fraction.
    - exp >= 0: base**exp
    - exp < 0 : 1/(base**(-exp))  (sofern base != 0)
    """
    if exp.denominator != 1:
        raise ValueError("Exponent muss ganzzahlig sein (b muss Integer sein).")

    e = exp.numerator  # int
    if e >= 0:
        return base ** e
    if base == 0:
        raise ZeroDivisionError("0 kann nicht negativ potenziert werden.")
    return Fraction(1, 1) / (base ** (-e))


def sqrt_fraction_exact(x: Fraction) -> Fraction:
    """
    Exakte Wurzel für rationale Zahlen:
    sqrt(p/q) ist rational genau dann, wenn p und q perfekte Quadrate sind.
    """
    if x <= 0:
        raise ValueError("Argument unter der Wurzel muss > 0 sein.")
    p = x.numerator
    q = x.denominator
    rp = isqrt(p)
    rq = isqrt(q)
    if rp * rp != p or rq * rq != q:
        raise ValueError("Kein perfektes Quadrat (rational).")
    return Fraction(rp, rq)


def icbrt_nonneg(n: int) -> int:
    """Ganzzahliger floor-Kubikwurzel für n >= 0 per Binärsuche (exakt)."""
    if n < 0:
        raise ValueError("icbrt_nonneg erwartet n >= 0.")
    if n < 2:
        return n
    hi = 1
    while hi * hi * hi <= n:
        hi *= 2
    lo = hi // 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        m3 = mid * mid * mid
        if m3 <= n:
            lo = mid
        else:
            hi = mid
    return lo


def cbrt_fraction_exact(x: Fraction) -> Fraction:
    """
    Exakte Kubikwurzel für rationale Zahlen:
    cbrt(p/q) ist rational genau dann, wenn p und q perfekte Kuben sind (bis auf Vorzeichen bei p).
    """
    if x == 0:
        return Fraction(0, 1)

    p = x.numerator
    q = x.denominator  # > 0

    sign = -1 if p < 0 else 1
    ap = abs(p)

    rp = icbrt_nonneg(ap)
    rq = icbrt_nonneg(q)

    if rp * rp * rp != ap or rq * rq * rq != q:
        raise ValueError("Kein perfekter Kubus (rational).")

    return Fraction(sign * rp, rq)


def log_base_exact(a: Fraction, c: Fraction, kmax: int = 200) -> Fraction:
    """
    Exakter Logarithmus log_c(a) als positive ganze Zahl k, falls a = c^k exakt gilt.
    Nur für reelle Logs: a > 0, c > 0, c != 1.
    Gibt Fraction(k,1) zurück, sonst ValueError (damit sofort verworfen wird).
    """
    if a <= 0 or c <= 0 or c == 1:
        raise ValueError("log_c(a) erfordert a>0, c>0 und c!=1.")

    val = c
    for k in range(1, kmax + 1):
        if val == a:
            return Fraction(k, 1)
        val *= c

        if c > 1 and val > a:
            break
        if 0 < c < 1 and val < a:
            break

    raise ValueError("a ist keine exakte positive Potenz von c.")


def is_natural_positive(x: Fraction | int) -> bool:
    """Natürliche Zahl im Sinne von {1,2,3,...}."""
    if isinstance(x, int):
        return x > 0
    return x.denominator == 1 and x.numerator > 0


def fmt_fraction(x: Fraction) -> str:
    """Schöne Ausgabe: 3 statt 3/1, sonst p/q."""
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


# ---------------------------------------
# 3) Gleichungen (exakt), in Prüf-Reihenfolge
# ---------------------------------------
def eq_b_over_a_minus_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return b / (a - c)

def eq_6c_minus_4b(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return 6 * c - 4 * b

def eq_8_minus_b(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return 8 - b

def eq_a_pow_b_minus4_over_6c_plus1(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (pow_int_as_fraction(a, b) - 4) / (6 * c + 1)

def eq_b_plus_c_over_c_minus1(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b + c) / (c - 1)

def eq_b2_minus_b_over_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return b * b - (b / c)

def eq_sqrt_30_plus_a_over_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return sqrt_fraction_exact(30 + a) / c

def eq_a_plus_b_over_c_minus_3a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (a + b) / (c - 3 * a)

def eq_b_minus_3a_over_a_minus_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b - 3 * a) / (a - c)

def eq_8a_minus_2b(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return 8 * a - 2 * b

def eq_b_plus_9_over_sqrt_c_minus_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b + 9) / sqrt_fraction_exact(c - a)

def eq_18_over_ac_plus_1(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return Fraction(18, 1) / (a * c + 1)

def eq_c_pow_b(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return pow_int_as_fraction(c, b)

def eq_3_plus_b2_over_sqrt_3_plus_2c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (3 + b * b) / sqrt_fraction_exact(3 + 2 * c)

def eq_b_over_a2_minus_c2(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return b / (a * a - c * c)

def eq_sqrt_a_plus_2_over_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return sqrt_fraction_exact(a + 2) / a

def eq_a_pow_b_minus_12_over_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return pow_int_as_fraction(a, b) - (Fraction(12, 1) / a)

def eq_2c_plus_c_over_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return 2 * c + (c / a)

def eq_4a_minus_5b(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return 4 * a - 5 * b

def eq_c_plus_2a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return c + 2 * a

def eq_b_over_9a_minus_5c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return b / (9 * a - 5 * c)

def eq_b3_plus_2c_over_b_plus_2c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b * b * b + 2 * c) / (b + 2 * c)

def eq_b_over_a_minus_1(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return b / (a - 1)

def eq_c_minus_b_over_2a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (c - b) / (2 * a)

def eq_b_plus_c_over_a_minus_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b + c) / (a - c)

def eq_log_c_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return log_base_exact(a, c)

def eq_c2_minus_b_over_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (c * c - b) / a

def eq_b_minus_1_sq(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b - 1) * (b - 1)

def eq_cbrt_43_minus_ac_over_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return cbrt_fraction_exact(43 - a * c) / a

def eq_b_minus_a_over_a_minus_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b - a) / (a - c)

def eq_11_minus_b(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return 11 - b

def eq_b_minus_2a_over_a_minus_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (b - 2 * a) / (a - c)

def eq_c_plus_3_over_a(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (c + 3) / a

def eq_8c_minus_b_over_c(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return 8 * c - (b / c)

def eq_b2(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return b * b

def eq_2_pow_b_plus_1_over_ac(a: Fraction, b: Fraction, c: Fraction) -> Fraction:
    return (pow_int_as_fraction(Fraction(2, 1), b) + 1) / (a * c)


EQUATIONS: List[Tuple[str, Callable[[Fraction, Fraction, Fraction], Fraction]]] = [
    ("b/(a-c)  [Start]", eq_b_over_a_minus_c),
    ("6c-4b", eq_6c_minus_4b),
    ("8-b", eq_8_minus_b),
    ("(a^b-4)/(6c+1)", eq_a_pow_b_minus4_over_6c_plus1),
    ("(b+c)/(c-1)", eq_b_plus_c_over_c_minus1),
    ("b^2 - b/c", eq_b2_minus_b_over_c),
    ("sqrt(30+a)/c", eq_sqrt_30_plus_a_over_c),
    ("(a+b)/(c-3a)", eq_a_plus_b_over_c_minus_3a),
    ("(b-3a)/(a-c)", eq_b_minus_3a_over_a_minus_c),
    ("8a-2b", eq_8a_minus_2b),
    ("(b+9)/sqrt(c-a)", eq_b_plus_9_over_sqrt_c_minus_a),
    ("18/(ac+1)", eq_18_over_ac_plus_1),
    ("c^b", eq_c_pow_b),
    ("(3+b^2)/sqrt(3+2c)", eq_3_plus_b2_over_sqrt_3_plus_2c),
    ("b/(a^2-c^2)", eq_b_over_a2_minus_c2),
    ("sqrt(a+2)/a", eq_sqrt_a_plus_2_over_a),
    ("a^b - 12/a", eq_a_pow_b_minus_12_over_a),
    ("2c + c/a", eq_2c_plus_c_over_a),
    ("4a-5b", eq_4a_minus_5b),
    ("c+2a", eq_c_plus_2a),
    ("b/(9a-5c)", eq_b_over_9a_minus_5c),
    ("(b^3+2c)/(b+2c)", eq_b3_plus_2c_over_b_plus_2c),
    ("b/(a-1)", eq_b_over_a_minus_1),
    ("(c-b)/(2a)", eq_c_minus_b_over_2a),
    ("b/(a-c)  (zweites Vorkommen)", eq_b_over_a_minus_c),
    ("(b+c)/(a-c)", eq_b_plus_c_over_a_minus_c),
    ("log_c a", eq_log_c_a),
    ("(c^2-b)/a", eq_c2_minus_b_over_a),
    ("(b-1)^2", eq_b_minus_1_sq),
    ("cuberoot(43-ac)/a", eq_cbrt_43_minus_ac_over_a),
    ("(b-a)/(a-c)", eq_b_minus_a_over_a_minus_c),
    ("11-b", eq_11_minus_b),
    ("(b-2a)/(a-c)", eq_b_minus_2a_over_a_minus_c),
    ("(c+3)/a", eq_c_plus_3_over_a),
    ("8c - b/c", eq_8c_minus_b_over_c),
    ("b^2", eq_b2),
    ("(2^b+1)/(ac)", eq_2_pow_b_plus_1_over_ac),
]


# ---------------------------------------
# 4) Gridsearch
# ---------------------------------------
def gridsearch_solutions(
    a_values: Iterable[Fraction],
    b_values: Iterable[Fraction],
    c_values: Iterable[Fraction],
    keep_outputs: bool = False,
) -> List[Tuple[Fraction, Fraction, Fraction] | Tuple[Fraction, Fraction, Fraction, List[Tuple[str, int]]]]:
    solutions = []
    for a, b, c in product(a_values, b_values, c_values):
        outputs_named: List[Tuple[str, int]] = []
        valid = True

        for name, fn in EQUATIONS:
            try:
                val = fn(a, b, c)
            except (ZeroDivisionError, ValueError, OverflowError):
                valid = False
                break

            if not is_natural_positive(val):
                valid = False
                break

            outputs_named.append((name, int(val)))

        if valid:
            if keep_outputs:
                solutions.append((a, b, c, outputs_named))
            else:
                solutions.append((a, b, c))
    return solutions


def print_solution_with_grouped_outputs(a: Fraction, b: Fraction, c: Fraction, outputs_named: List[Tuple[str, int]]) -> None:
    """
    Gruppiert alle Gleichungen nach ihrem integer Output und druckt:
    'Diese Equations haben als Lösungswert X:'
    gefolgt von den ausgeschriebenen Gleichungen.
    """
    groups: Dict[int, List[str]] = {}
    for eq_name, value in outputs_named:
        groups.setdefault(value, []).append(eq_name)

    print(f"a={fmt_fraction(a)}, b={fmt_fraction(b)}, c={fmt_fraction(c)}")
    for value in sorted(groups.keys()):
        print(f"Diese Equations haben als Lösungswert {value}:")
        for eq_name in groups[value]:
            print(f"  {eq_name}")
    print("-" * 60)


if __name__ == "__main__":
    sols = gridsearch_solutions(A_VALUES, B_VALUES, C_VALUES, keep_outputs=True)

    print(f"Gefundene Lösungen: {len(sols)}")
    for a, b, c, outputs_named in sols:
        print_solution_with_grouped_outputs(a, b, c, outputs_named)