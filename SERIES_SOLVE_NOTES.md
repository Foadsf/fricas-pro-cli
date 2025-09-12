# Notes on `seriesSolve` in FriCAS

This document captures practical lessons learned while using `seriesSolve` to obtain
power-series (Taylor) solutions to ODEs in FriCAS.

---

## Quick facts

- **Purpose**: compute **power-series solutions** (usually Taylor) for ODEs and
  systems of first-order ODEs.
- **Scope**: expects **differential** equations. It is *not* a general solver for
  pure algebraic equations.
- **Output**: `UnivariateTaylorSeries(...)` (single ODE) or a list thereof (systems).
- **Term count**: control with `)set streams calculate N`.

```fricas
)clear all
)set streams calculate 8
````

---

## Syntax essentials

### 1) Single ODE (order `n`)

* Use **nested `D`** for higher derivatives (portable across builds).
* ICs are given as a **list of values**: `[y(0), y'(0), …, y^(n-1)(0)]`.

```fricas
y := operator 'y
t := 't  -- (not strictly required; shown to emphasize the independent variable)

-- y'' + w^2*y = sin(t), around t=0 with y(0)=0, y'(0)=1
eq := D(D(y(t), t), t) + w^2 * y(t) = sin(t)

seriesSolve(eq, y, t = 0, [0, 1])
```

### 2) First-order system

* Provide **lists** for equations and unknown functions.
* ICs are supplied as **equations** at the expansion point (e.g., `x(0)=…`).

```fricas
x := operator 'x
y := operator 'y
eq1 := D(x(t), t) = 1 + x(t)^2
eq2 := D(y(t), t) = x(t) * y(t)

seriesSolve([eq1, eq2], [x, y], t = 0, [x(0) = 0, y(0) = 1])
```

---

## Gotchas & fixes

1. **Exponentiation**: FriCAS uses `^`, **not** `**`.

   ```fricas
   x(t)^2   -- correct
   ```

2. **Higher derivatives**: Prefer **nested `D`**:

   ```fricas
   D(D(D(y(t), t), t), t)     -- portable
   ```

3. **IC format differences**:

   * For **single n-th order ODE**: ICs as **values** `[y(0), y'(0), …]`.
   * For **systems**: ICs as **equations** like `[x(0)=..., y(0)=...]`.

4. **Name clashes**: Don’t reuse a name as both an **operator** and an
   independent variable. If `x := operator 'x` exists, use `t` or `u` as the
   independent variable in later examples.

5. **Series length**: If output is too short/long, tune:

   ```fricas
   )set streams calculate 6  -- fewer terms
   )set streams calculate 12 -- more terms
   ```

6. **Limitations & behavior**:

   * Designed for **differential** equations; will complain for algebraic-only input.
   * May stop early (“partial solutions”) on harder problems.
   * Post-processing of the returned series works in the usual ways, but if the
     series variable appears *inside coefficients*, some manipulations may be restricted.

---

## Minimal working patterns

**Second-order with parameters**

```fricas
)clear all
)set streams calculate 10
y := operator 'y
t := 't
eq := D(D(y(t), t), t) + w^2 * y(t) = sin(t)
seriesSolve(eq, y, t = 0, [0, 1])
```

**Coupled first-order system**

```fricas
)clear all
)set streams calculate 8
x := operator 'x
y := operator 'y
eq1 := D(x(t), t) = 1 + x(t)^2
eq2 := D(y(t), t) = x(t) * y(t)
seriesSolve([eq1, eq2], [x, y], t = 0, [x(0) = 0, y(0) = 1])
```

---

## Troubleshooting

* If parsing errors mention **`D`**: ensure nested form and that the second
  argument to `D(…, •)` is the **independent variable** (a symbol, not an operator).
* If you see **`elt`** errors in ICs: for single-ODE problems, supply ICs as a
  **value list** `[y(0), y'(0), …]`.
* Use your wrapper’s `--verbose` to inspect the RAW REPL block and adjust syntax.