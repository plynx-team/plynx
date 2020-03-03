export function typesValid(output, input) {
  if (input.file_type === output.file_type) {
    return true;
  }
  if (input === 'file') {
    return true;
  }
  return false;
}
