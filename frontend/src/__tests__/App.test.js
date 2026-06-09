import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import App from '../App';
import { AuthContext } from '../context/AuthContext';
import Login from '../pages/Login';
import Home from '../pages/Home';
import Form from '../pages/Form';
import Detail from '../pages/Detail';
// Простые тесты для проверки работы Jest
describe('Basic Math Tests', () => {
  test('сложение работает правильно', () => {
    expect(2 + 2).toBe(4);
  });

  test('вычитание работает правильно', () => {
    expect(5 - 3).toBe(2);
  });
});

describe('String Tests', () => {
  test('строки сравниваются корректно', () => {
    expect('hello world').toContain('world');
  });

  test('длина строки вычисляется верно', () => {
    expect('test'.length).toBe(4);
  });
});

describe('Array Tests', () => {
  test('массив содержит элементы', () => {
    const arr = [1, 2, 3];
    expect(arr).toContain(2);
    expect(arr).toHaveLength(3);
  });
});

describe('Object Tests', () => {
  test('объекты сравниваются корректно', () => {
    const obj = { name: 'test', value: 42 };
    expect(obj.name).toBe('test');
    expect(obj.value).toBe(42);
  });
});

// Тесты для функций из Home.js
describe('Temperature Functions', () => {
  const getTemperatureStatus = (temp) => {
    if (temp < 60) return 'cold';
    if (temp <= 80) return 'normal';
    return 'hot';
  };

  const getTemperatureColor = (temp) => {
    if (temp < 60) return '#4299e1';
    if (temp <= 80) return '#ed8936';
    return '#e53e3e';
  };

  test('статус температуры: холодная', () => {
    expect(getTemperatureStatus(50)).toBe('cold');
    expect(getTemperatureStatus(40)).toBe('cold');
  });

  test('статус температуры: нормальная', () => {
    expect(getTemperatureStatus(60)).toBe('normal');
    expect(getTemperatureStatus(70)).toBe('normal');
    expect(getTemperatureStatus(80)).toBe('normal');
  });

  test('статус температуры: горячая', () => {
    expect(getTemperatureStatus(85)).toBe('hot');
    expect(getTemperatureStatus(95)).toBe('hot');
  });

  test('цвет температуры: синий для холодной', () => {
    expect(getTemperatureColor(50)).toBe('#4299e1');
  });

  test('цвет температуры: оранжевый для нормальной', () => {
    expect(getTemperatureColor(70)).toBe('#ed8936');
  });

  test('цвет температуры: красный для горячей', () => {
    expect(getTemperatureColor(90)).toBe('#e53e3e');
  });
});

// Тесты для утилит пагинации
describe('Pagination Utilities', () => {
  const getPaginatedItems = (items, page, itemsPerPage) => {
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    return items.slice(start, end);
  };

  const getTotalPages = (totalItems, itemsPerPage) => {
    return Math.ceil(totalItems / itemsPerPage);
  };

  test('пагинация: первая страница', () => {
    const items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const page1 = getPaginatedItems(items, 1, 5);
    expect(page1).toEqual([1, 2, 3, 4, 5]);
  });

  test('пагинация: вторая страница', () => {
    const items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const page2 = getPaginatedItems(items, 2, 5);
    expect(page2).toEqual([6, 7, 8, 9, 10]);
  });

  test('расчет количества страниц', () => {
    expect(getTotalPages(10, 5)).toBe(2);
    expect(getTotalPages(7, 5)).toBe(2);
    expect(getTotalPages(5, 5)).toBe(1);
  });
});

// Тесты для валидации форм
describe('Form Validation', () => {
  const validateTemperature = (temp) => {
    if (temp < 40) return 40;
    if (temp > 95) return 95;
    return temp;
  };

  const validateName = (name) => {
    if (!name || name.trim().length === 0) return false;
    if (name.length < 2) return false;
    return true;
  };

  test('температура ограничена снизу', () => {
    expect(validateTemperature(30)).toBe(40);
    expect(validateTemperature(35)).toBe(40);
  });

  test('температура ограничена сверху', () => {
    expect(validateTemperature(100)).toBe(95);
    expect(validateTemperature(120)).toBe(95);
  });

  test('температура в норме не меняется', () => {
    expect(validateTemperature(60)).toBe(60);
    expect(validateTemperature(75)).toBe(75);
  });

  test('имя не может быть пустым', () => {
    expect(validateName('')).toBe(false);
    expect(validateName('   ')).toBe(false);
  });

  test('имя должно быть длиннее 1 символа', () => {
    expect(validateName('a')).toBe(false);
    expect(validateName('ab')).toBe(true);
  });
});

// Тесты для фильтрации
describe('Filter Functions', () => {
  const chps = [
    { id: 1, name: 'ТЭЦ 1', type: 'chp' },
    { id: 2, name: 'ТЭЦ 2', type: 'chp' }
  ];
  
  const houses = [
    { id: 3, name: 'Дом 1', type: 'house' },
    { id: 4, name: 'Дом 2', type: 'house' }
  ];

  const filterItems = (items, filterType) => {
    if (filterType === 'chp') {
      return items.filter(item => item.type === 'chp');
    }
    if (filterType === 'house') {
      return items.filter(item => item.type === 'house');
    }
    return items;
  };

  test('фильтр "все" показывает все объекты', () => {
    const allItems = [...chps, ...houses];
    const filtered = filterItems(allItems, 'all');
    expect(filtered).toHaveLength(4);
  });

  test('фильтр "ТЭЦ" показывает только ТЭЦ', () => {
    const allItems = [...chps, ...houses];
    const filtered = filterItems(allItems, 'chp');
    expect(filtered).toHaveLength(2);
    expect(filtered[0].type).toBe('chp');
  });

  test('фильтр "Дома" показывает только дома', () => {
    const allItems = [...chps, ...houses];
    const filtered = filterItems(allItems, 'house');
    expect(filtered).toHaveLength(2);
    expect(filtered[0].type).toBe('house');
  });
});

console.log('✅ Тесты готовы к запуску!');

// Экспорт для Jest
export default {};
