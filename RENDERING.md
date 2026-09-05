# Rendering Instrument

**Type:** Operative instrument. Read when building or changing a page or a figure, not at session open.
**Applies to:** Every page file, `shared.css`, every figure and every component on sinclairdynamics.co.
**Replaces:** Section 8 of the visual language reference, *Implementation faults that render perfectly*.

**Why this exists.** On this site the dangerous errors are silent. Every fault below produced a page that looked entirely correct and behaved wrongly, and every one cost real time.

---

## The standing rule

**A pre-handover review checks wiring, not only syntax.** Before claiming a behaviour works, verify that its selectors have targets in the tree, the same way column names are verified before writing SQL.

**Reading a stylesheet means reading what it does to elements, not only what classes it offers.** A stylesheet in hand is not a stylesheet read.

---

## Selectors and structure

- **A sibling combinator needs its targets to still be siblings.** Wrapping a group breaks `~` silently: the page renders and the interaction does not exist.
- **No page may use a second `nav`, `header` or `footer` element** while `shared.css` carries bare element rules on them. A second instance inherits everything the class rules did not override, and a partly working element is harder to diagnose than a broken one, because the parts that work argue the applied rules are the whole story.
- **A component with no background of its own is not portable between grounds.** Before using one, read whether it declares a fill. If it does not, its colour is supplied by the section it sits in, and moving it changes its meaning rather than its position.

## Geometry and layout

- **No painted coordinate may leave the viewBox.** Layout sizes to the painted extent, not to the drawing.
- **Compute the constraint and the drawing from the same numbers.** Where a figure is designed in one coordinate frame and rendered in another, the check runs in the frame that is rendered. A separate design frame is a second source of truth.
- **Where the same computation exists twice, compare the outputs mechanically, at every state, before deployment.** Reading both and agreeing they look right is not a test.
- **A clip that can invert must test for inversion and report it, not clamp quietly.** Where a constraint is enforced by a minimum or a maximum, ask what happens when the bound crosses the value it is bounding. An inverted rectangle paints nothing and still hit-tests.
- **Anything sized against vertical space is decided by vertical space.** `svh` for a height that must fit the screen, `max-height` on a viewport unit, and a media query on `max-height` where one is needed. A width breakpoint standing in for a vertical question renders perfectly and hides the thing it was meant to protect.
- **Inside a component there is no viewport unit that means anything**, because the component's height is set by its container. Measure, and measure before resizing: resizing changes the quantity being measured, so a reading taken afterwards describes a state that lasted one instant.

## Drawing

- **Do not use `stroke-linecap: round` on abutting semi-transparent segments.** Two caps composite at every junction into a visible bead, invisible at mockup scale and obvious at full size. Fade with a stroke gradient instead.
- **A dash gap must comfortably exceed the path length**, and the offset runs from the dash length to minus the gap.
- **`slice` must not be used on a figure that may not be cropped.** It fails invisibly on one monitor and obviously on another.

## Claims about what a figure does

- **A property of a figure is measured, not read off a picture.** A hairline in a diagnostic image was 15 percent of the silhouette at one stop and 21 at another.
- **A rule that holds only on its originating case is fitted to that case rather than to the constraint.** Where an accommodation works on exactly one of the surfaces measured, and it is the one it was written for, that is the tell.

---

## Where the history is

Every case, with the diagnosis and the session it cost, is in `sd-reference-visual-language-v0_16.md` section 8. Nothing above requires it to be read.

---

*Sinclair Dynamics Website*
*Created Session 60, 3 September 2026*
*Version 1.0*
