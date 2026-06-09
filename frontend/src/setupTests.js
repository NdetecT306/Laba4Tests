import '@testing-library/jest-dom';

// Мок для window.confirm
window.confirm = jest.fn(() => true);

// Мок для console.error (чтобы уменьшить шум в тестах)
const originalError = console.error;
beforeAll(() => {
  console.error = jest.fn();
});

afterAll(() => {
  console.error = originalError;
});

// Мок для localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;
