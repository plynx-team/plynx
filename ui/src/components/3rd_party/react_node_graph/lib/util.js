/* not bound to style, should be computed */

const X_SHIFT = 182;
const Y_SHIFT = 58;
const Y_STEP = 21;

export function computeInOffsetByIndex(x,y,index) {
  let outx = x + 0;
  let outy = y + Y_SHIFT + (index * Y_STEP);

  return {x:outx, y:outy};
}

export function computeOutOffsetByIndex(x,y,index) {

  let outx = x + X_SHIFT;
  let outy = y + Y_SHIFT + (index * Y_STEP);

  return {x:outx, y:outy};

}
