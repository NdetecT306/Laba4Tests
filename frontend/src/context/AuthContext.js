// backend/frontend/src/context/AuthContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();
const API_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  let isRefreshing = false;
  let failedQueue = [];
  let redirecting = false;

  const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve(token);
      }
    });
    failedQueue = [];
  };

  const logout = async () => {
    try {
      await api.post('/logout');
    } catch (error) {
      console.error('Ошибка при выходе:', error);
    } finally {
      setUser(null);
      // Очищаем cookies
      document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
      document.cookie = 'refresh_token=; path=/api/refresh; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
      
      // Редирект только если не на странице логина и ещё не редиректим
      if (!redirecting && window.location.pathname !== '/login') {
        redirecting = true;
        window.location.href = '/login';
      }
    }
  };

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        
        // Если на странице логина или уже редиректим - не обрабатываем
        if (window.location.pathname === '/login' || redirecting) {
          return Promise.reject(error);
        }
        
        // Если 401
        if (error.response?.status === 401 && !originalRequest._retry) {
          // Не пытаемся обновить токен для запросов на /refresh, /login, /register
          const isAuthEndpoint = originalRequest.url === '/refresh' || 
                                 originalRequest.url === '/login' || 
                                 originalRequest.url === '/register';
          
          if (isAuthEndpoint) {
            // Для auth эндпоинтов сразу редирект
            await logout();
            return Promise.reject(error);
          }
          
          if (isRefreshing) {
            // Если уже обновляем токен, ждём
            return new Promise((resolve, reject) => {
              failedQueue.push({ resolve, reject });
            })
              .then(token => {
                originalRequest.headers.Authorization = `Bearer ${token}`;
                return api(originalRequest);
              })
              .catch(err => Promise.reject(err));
          }
          
          originalRequest._retry = true;
          isRefreshing = true;
          
          try {
            await api.post('/refresh');
            isRefreshing = false;
            processQueue(null);
            return api(originalRequest);
          } catch (refreshError) {
            isRefreshing = false;
            processQueue(refreshError, null);
            await logout();
            return Promise.reject(refreshError);
          }
        }
        
        return Promise.reject(error);
      }
    );
    
    return () => {
      api.interceptors.response.eject(interceptor);
    };
  }, []);

  useEffect(() => {
    const checkAuth = async () => {
      if (window.location.pathname === '/login') {
        setLoading(false);
        return;
      }
      
      try {
        const response = await api.get('/me');
        if (response.data) {
          setUser({
            id: response.data.ID,
            username: response.data.Логин
          });
        }
      } catch (error) {
        console.log('Не авторизован');
        setUser(null);
        if (!redirecting && window.location.pathname !== '/login') {
          redirecting = true;
          window.location.href = '/login';
        }
      } finally {
        setLoading(false);
      }
    };
    
    checkAuth();
  }, []);

  const register = async (username, password, confirmPassword) => {
    try {
      const response = await api.post('/register', {
        Логин: username,
        Пароль: password,
        Подтверждение_пароля: confirmPassword
      });
      
      if (response.data) {
        await login(username, password);
        return response.data;
      }
    } catch (error) {
      if (error.response) {
        throw error.response.data?.detail || 'Ошибка регистрации';
      }
      throw 'Ошибка соединения с сервером';
    }
  };

  const login = async (username, password) => {
    try {
      const response = await api.post('/login', {
        Логин: username,
        Пароль: password
      });
      
      if (response.data) {
        const meResponse = await api.get('/me');
        if (meResponse.data) {
          setUser({
            id: meResponse.data.ID,
            username: meResponse.data.Логин
          });
        }
        return response.data;
      }
    } catch (error) {
      if (error.response) {
        throw error.response.data?.detail || 'Ошибка входа';
      }
      throw 'Ошибка соединения с сервером';
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, api }}>
      {children}
    </AuthContext.Provider>
  );
};