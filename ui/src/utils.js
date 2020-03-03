export function storeToClipboard(text) {
  localStorage.setItem('clipboard', JSON.stringify(text));
}

export function loadFromClipboard() {
  return JSON.parse(localStorage.getItem('clipboard'));
}

export function utcTimeToLocal(text) {
  const date = new Date(text + 'Z');  // Make date it UTC
  return date.toString().replace(/GMT.*/g, '');  // RM GMT...
}

export function addStyleToTourSteps(steps) {
  return steps.map(
      (step) => {
        return {
          style: {
            'backgroundColor': '#202020',
            'color': 'white',
            'border': '1px solid #12ccc8'
          },
          ...step,
        };
      }
  );
}
