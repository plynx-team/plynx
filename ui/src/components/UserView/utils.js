export function validatePassword(password) {
  const regex = [
    "[A-Z]", // For Uppercase Alphabet
    "[a-z]", // For Lowercase Alphabet
    "[0-9]", // For Numeric Digits
  ];

  let passed = 0;

    // Validation for each Regular Expression
  for (let i = 0; i < regex.length; i++) {
    if ((new RegExp(regex[i])).test(password)) {
      passed++;
    }
  }

    // Validation for Length of Password
  if (passed === regex.length && password.length >= 8) {
    return true;
  }
  return false;
}
