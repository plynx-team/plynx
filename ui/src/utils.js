const dateFormat = require('dateformat');

export function storeToClipboard(text) {
  localStorage.setItem('clipboard', JSON.stringify(text));
}

export function loadFromClipboard() {
  return JSON.parse(localStorage.getItem('clipboard'));
}

export function utcTimeToLocal(text, outputFormat = "yyyy-mm-dd HH:MM:ss") {
  // const date = new Date(text + 'Z');  // Make date it UTC
  // return date.toString().replace(/GMT.*/g, '');  // RM GMT... //Fri May 29 2020 23:05:45
  const date = Date.parse(text + "GMT");
  return dateFormat(date, outputFormat).toString();
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
