/* not bound to style, should be computed */

export function computeInOffsetByIndex(x,y,index) {
  let outx = x + 0;
  let outy = y + 55 + (index * 20);

  return {x:outx, y:outy};
}

export function computeOutOffsetByIndex(x,y,index) {

  let outx = x + 180;
  let outy = y + 55 + (index * 20);

  return {x:outx, y:outy};

}
