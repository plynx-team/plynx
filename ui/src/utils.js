export function storeToClipboard(text) {
  localStorage.setItem('clipboard', JSON.stringify(text));
}

export function loadFromClipboard() {
  return JSON.parse(localStorage.getItem('clipboard'));
}
