export function validatePassword(password?: string): boolean {
  if (!password) {
    return false;
  }
  const regex = [
    '[A-Z]', // For Uppercase Alphabet
    '[a-z]', // For Lowercase Alphabet
    '[0-9]', // For Numeric Digits
  ];

  let passed = 0;

  for (let i = 0; i < regex.length; i++) {
    if (new RegExp(regex[i]).test(password)) {
      passed++;
    }
  }

  return passed === regex.length && password.length >= 8;
}
