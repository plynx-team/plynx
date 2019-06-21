/* not bound to style, should be computed */

const X_SHIFT = 182;
const Y_SHIFT = 58;
const Y_STEP = 21;

export function computeInOffsetByIndex(x, y, index) {
  const outx = x + 0;
  const outy = y + Y_SHIFT + (index * Y_STEP);

  return {x: outx, y: outy};
}

export function computeOutOffsetByIndex(x, y, index) {
  const outx = x + X_SHIFT;
  const outy = y + Y_SHIFT + (index * Y_STEP);

  return {x: outx, y: outy};
}
