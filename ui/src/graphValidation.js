export function typesValid(output, input) {
  if (input.file_types.indexOf(output.file_type) >= 0) {
    return true;
  }
  if (input.file_types.indexOf('file') >= 0) {
    return true;
  }
  return false;
}
