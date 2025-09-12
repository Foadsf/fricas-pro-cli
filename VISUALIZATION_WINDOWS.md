# FriCAS Visualization on Windows — Lessons Learned

> Practical notes for plotting with FriCAS under Windows (console mode), distilled from trial & error using our `fricas_pro_cli.py` wrapper.

## TL;DR

* **Interactive windows** (`draw(...)`) may not appear reliably on Windows when running FriCAS in console/script mode.
* **Reliable path:** use the **`GnuDraw`** package to generate **gnuplot scripts** (`*.plt`) and render images (PNG/SVG) with **gnuplot** yourself.
* Put `gnuplot.exe` on **PATH** or call it via an **absolute path** (e.g., from Maxima’s bundled gnuplot).

---

## Two ways to plot

### 1) Native `draw(...)` (viewports)

* Works interactively when FriCAS can open graphics windows.
* In script mode on Windows, you may see messages like:

  ```
  TwoDimensionalViewport: "x*cos(x)"
  ThreeDimensionalViewport: "sin(x*y)"
  ```

  …but no window appears. If that happens, switch to `GnuDraw`.

### 2) `GnuDraw` → write `.plt` → render with gnuplot

* Deterministic in console mode and CI.
* **Signatures** (`)show GnuDraw`):

  * `gnuDraw(Expression(Float), SegmentBinding(Float), String)` → 2D function → `.plt`
  * `gnuDraw(Expression(Float), SegmentBinding(Float), SegmentBinding(Float), String)` → 3D surface → `.plt`
  * `gnuDraw(List(DoubleFloat), List(DoubleFloat), String)` → 2D point lists → `.plt` (handy for parametric)

---

## What worked (recipes)

### A. Generate `.plt` scripts from FriCAS

**2D explicit function**

```fricas
)clear all
gnuDraw(x*cos(x), x = 0..30, "xcosx.plt")
```

**3D surface**

```fricas
)clear all
gnuDraw(sin(x*y), x = -4..4, y = -4..4, "sinxy.plt")
```

**Parametric curve (workaround: points)**

```fricas
)clear all
-- sample a Lissajous curve x=sin(3t), y=sin(4t)
ptsx := [ sin(3.0*t::DoubleFloat) for t in 0.0..(2.0*%pi) by 0.01 ]
ptsy := [ sin(4.0*t::DoubleFloat) for t in 0.0..(2.0*%pi) by 0.01 ]
gnuDraw(ptsx, ptsy, "lissajous_points.plt")
```

> Tip: you can run our prepared examples:
>
> * `examples\023_plot_gnudraw_file_output.input`
> * `examples\024_plot_options_and_export.input`
> * `examples\026_plot_gnudraw_with_options.input` (plain `.plt` generation)

### B. Render images with gnuplot

**One-liners (PNG)**

```bat
gnuplot -e "set term pngcairo size 1280,720; set title 'y = x*cos(x)'; set samples 400; set output 'xcosx.png'; load 'xcosx.plt'"
gnuplot -e "set term pngcairo size 1280,720; set title 'z = sin(x*y)'; set isosamples 60,60; set output 'sinxy.png'; load 'sinxy.plt'"
gnuplot -e "set term pngcairo size 1280,720; set title 'Lissajous'; set samples 800; set output 'lissajous.png'; load 'lissajous_points.plt'"
```

**If gnuplot isn’t on PATH**, call it explicitly:

```bat
"C:\maxima-5.48.1\gnuplot\bin\gnuplot.exe" -e "set term pngcairo size 1280,720; set output 'xcosx.png'; load 'xcosx.plt'"
```

---

## Things that *didn’t* work (and fixes)

### 1) No windows from `draw(...)`

* **Symptom:** FriCAS prints `TwoDimensionalViewport: ...`, but no window shows.
* **Fix:** Use `GnuDraw` to emit `.plt` and render with gnuplot.

### 2) Using `**` for powers

* **Symptom:** `There are no library operations named **`
* **Fix:** In FriCAS use caret `^`: `x^2`, not `x**2`.

### 3) Wrong `GnuDraw` signature for parametric curves

* **Symptom:**

  ```
  Cannot find a definition ... named gnuDraw with argument type(s)
    ParametricPlaneCurve(...)
  ```
* **Why:** `GnuDraw` doesn’t accept parametric curves directly.
* **Fix:** Sample **point lists** and call the `gnuDraw(List DF, List DF, String)` overload (see parametric recipe above).

### 4) Draw options passed incorrectly

* **We tried:** `gnuDraw(..., "file.plt", [title=="...", var1Steps==400])`
* **Problem:** Each keyword like `title==...` returns a **List(DrawOption)**; putting several inside `[...]` creates a **nested** list (type mismatch).
* **Simple workaround:** Skip options in FriCAS and set **samples/title** in gnuplot (`set samples`, `set title`).
  (Advanced: if you really want options in FriCAS, build a flat `List(DrawOption)` using `concat` to flatten, but this is brittle across builds.)

### 5) Mixed integer vs float ranges

* **Symptom:** Type mismatches with the 4-arg overload (`Expression(Float), SegmentBinding(Float), ..., List(DrawOption)`).
* **Fix:** Use **float** ranges like `0.0..30.0` and/or coerce the expression to float (e.g., `1.0*(...)`) *if* you stick to that overload.
  Or sidestep: use the **3-arg** form without options and set styling in gnuplot.

### 6) Learning the right signatures late

* **Best practice:** Ask FriCAS directly:

  ```fricas
  )display op gnuDraw
  )display op draw
  )show GnuDraw
  ```

  From the wrapper:

  ```bat
  python fricas_pro_cli.py eval ")display op gnuDraw"
  python fricas_pro_cli.py eval ")display op draw"
  python fricas_pro_cli.py eval ")show GnuDraw"
  ```

---

## Suggested workflow on Windows (console / scripts)

1. Write FriCAS input to compute/define the plot and emit a `.plt` via `GnuDraw`.
2. Render PNG/SVG using gnuplot (manually or via a small `.bat`).
3. Commit only scripts and sources; **ignore generated images**.

**Example batch** (save as `examples\027_gnuplot_render_examples.bat`):

```bat
@echo off
setlocal
set "GP=gnuplot"  REM or set "GP=C:\maxima-5.48.1\gnuplot\bin\gnuplot.exe"

%GP% -e "set term pngcairo size 1280,720; set title 'y = x*cos(x)'; set samples 400; set output 'xcosx.png'; load 'xcosx.plt'"
%GP% -e "set term pngcairo size 1280,720; set title 'z = sin(x*y)'; set isosamples 60,60; set output 'sinxy.png'; load 'sinxy.plt'"
%GP% -e "set term pngcairo size 1280,720; set title 'Lissajous'; set samples 800; set output 'lissajous.png'; load 'lissajous_points.plt'"

echo Done.
endlocal
```

---

## Handy snippets

* **List points from parametric t**:

  ```fricas
  DF ==> DoubleFloat
  xs := [ f(t::DF) for t in t0::DF..t1::DF by dt::DF ]
  ys := [ g(t::DF) for t in t0::DF..t1::DF by dt::DF ]
  gnuDraw(xs, ys, "curve.plt")
  ```
* **Where am I writing files?**
  Use FriCAS `)pwd` and `)cd` to inspect/change the working directory.

---

## Git hygiene

Add generated artifacts to `.gitignore`:

```
# gnuplot outputs & scripts
*.png
*.svg
*.plt
*.ps
```

---

## Troubleshooting checklist

* `gnuplot` not found → add to PATH or call full path.
* `.plt` renders but looks blocky → increase `set samples` (2D) or `set isosamples` (3D).
* Parametric plot needed → generate **point lists** and use the list-based `gnuDraw`.
* “TwoDimensionalViewport” printed but nothing shows → prefer the `GnuDraw` route on Windows.
