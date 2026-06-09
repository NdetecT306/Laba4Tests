// backend/frontend/src/pages/Form.js
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function Form() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { api } = useAuth();
  const [chps, setChps] = useState([]);
  const [houses, setHouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [notification, setNotification] = useState(null);
  const [entityType, setEntityType] = useState('house');
  const [isEditMode, setIsEditMode] = useState(false);
  const [editId, setEditId] = useState(null);
  const [maxHousesPerChp, setMaxHousesPerChp] = useState(5);
  const [formData, setFormData] = useState({
    name: '',
    type: 'apartment',
    chpId: '',
    temperature: 60,
    capacity: 500,
    location: ''
  });

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  useEffect(() => {
    const loadData = async () => {
      try {
        const [chpsRes, housesRes, statusRes] = await Promise.all([
          api.get('/chps'),
          api.get('/houses'),
          api.get('/status')
        ]);
        
        const chpsData = chpsRes.data.map(chp => ({
          id: chp.ID,
          name: chp.Название,
          capacity: chp.Мощность,
          location: chp.Расположение
        }));
        
        const housesData = housesRes.data.map(house => ({
          id: house.ID,
          name: house.Название,
          type: house.Тип,
          chpId: house.ID_ТЭЦ,
          temperature: house.Температура
        }));
        
        setChps(chpsData);
        setHouses(housesData);
        setMaxHousesPerChp(statusRes.data.max_houses_per_chp);

        if (id) {
          const parsedId = parseInt(id);
          const foundChp = chpsData.find(c => c.id === parsedId);
          if (foundChp) {
            setIsEditMode(true);
            setEditId(parsedId);
            setEntityType('chp');
            setFormData({
              name: foundChp.name,
              capacity: foundChp.capacity,
              location: foundChp.location,
              type: 'apartment',
              chpId: chpsData[0]?.id || '',
              temperature: 60
            });
          } else {
            const foundHouse = housesData.find(h => h.id === parsedId);
            if (foundHouse) {
              setIsEditMode(true);
              setEditId(parsedId);
              setEntityType('house');
              setFormData({
                name: foundHouse.name,
                type: foundHouse.type,
                chpId: foundHouse.chpId,
                temperature: foundHouse.temperature,
                capacity: 500,
                location: ''
              });
            } else {
              showNotification('Объект не найден', 'error');
              navigate('/');
            }
          }
        } else if (chpsData.length > 0 && !formData.chpId) {
          setFormData(prev => ({ ...prev, chpId: chpsData[0].id }));
        }
      } catch (err) {
        showNotification('Ошибка загрузки данных', 'error');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [id, api, navigate]);

  const handleTypeChange = (type) => {
    if (isEditMode) return;
    setEntityType(type);
    setFormData({
      name: '',
      type: 'apartment',
      chpId: chps[0]?.id || '',
      temperature: 60,
      capacity: 500,
      location: ''
    });
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    let newValue = (name === 'capacity' || name === 'temperature' || name === 'chpId') ? Number(value) : value;
    if (name === 'temperature') {
      newValue = Math.min(95, Math.max(40, newValue));
    }
    setFormData(prev => ({ ...prev, [name]: newValue }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    
    try {
      if (isEditMode) {
        if (entityType === 'chp') {
          await api.put(`/chps/${editId}`, {
            Название: formData.name,
            Мощность: formData.capacity,
            Расположение: formData.location
          });
          showNotification(`ТЭЦ "${formData.name}" успешно обновлена`);
          navigate('/');
        } else {
          const updateData = {
            Название: formData.name,
            Температура: formData.temperature
          };
          if (formData.chpId) {
            updateData.ID_ТЭЦ = formData.chpId;
          }
          
          await api.put(`/houses/${editId}`, updateData);
          showNotification(`Дом "${formData.name}" успешно обновлён`);
          navigate('/');
        }
      } else {
        if (entityType === 'chp') {
          await api.post('/chps', {
            Название: formData.name,
            Мощность: formData.capacity,
            Расположение: formData.location
          });
          showNotification(`ТЭЦ "${formData.name}" успешно добавлена`);
          navigate('/');
        } else {
          await api.post('/houses', {
            Название: formData.name,
            Тип: formData.type,
            ID_ТЭЦ: formData.chpId,
            Температура: formData.temperature
          });
          showNotification(`Дом "${formData.name}" успешно добавлен`);
          navigate('/');
        }
      }
    } catch (err) {
      if (err.response) {
        const status = err.response.status;
        const detail = err.response.data?.detail || 'Ошибка при сохранении';
        
        if (status === 403) {
          showNotification(`Действие запрещено: ${detail}`, 'error');
        } else if (status === 409) {
          showNotification(`Объект с таким названием уже существует`, 'error');
        } else if (status === 404) {
          showNotification(`Объект не найден`, 'error');
        } else {
          showNotification(`Ошибка: ${detail}`, 'error');
        }
      } else if (err.request) {
        showNotification('Нет ответа от сервера. Проверьте соединение.', 'error');
      } else {
        showNotification(`Ошибка: ${err.message}`, 'error');
      }
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="loading">Загрузка...</div>;

  return (
    <div className="page">
      {notification && <div className={`notification notification-${notification.type}`}>{notification.message}</div>}
      <button className="btn btn-primary" onClick={() => navigate('/')} style={{ marginBottom: '1rem' }}>← Назад</button>
      <div className="card">
        <h2>{isEditMode ? 'Редактирование объекта' : '+ Добавление объекта'}</h2>
        
        {!isEditMode && (
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
            <button className={`btn ${entityType === 'house' ? 'btn-primary' : ''}`} onClick={() => handleTypeChange('house')}>Добавить дом</button>
            <button className={`btn ${entityType === 'chp' ? 'btn-primary' : ''}`} onClick={() => handleTypeChange('chp')}>Добавить ТЭЦ</button>
          </div>
        )}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Название *</label>
            <input type="text" name="name" className="form-input" value={formData.name} onChange={handleChange} required />
          </div>
          
          {entityType === 'chp' ? (
            <>
              <div className="form-group">
                <label className="form-label">Мощность (МВт) *</label>
                <input type="number" name="capacity" className="form-input" value={formData.capacity} onChange={handleChange} min="100" max="1000" required />
              </div>
              <div className="form-group">
                <label className="form-label">Расположение *</label>
                <input type="text" name="location" className="form-input" value={formData.location} onChange={handleChange} required />
              </div>
            </>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">Тип дома</label>
                <select name="type" className="form-select" value={formData.type} onChange={handleChange} disabled={isEditMode}>
                  <option value="apartment">Многоквартирный дом</option>
                  <option value="private">Частный дом</option>
                </select>
                {isEditMode && <small style={{ color: '#718096' }}>Тип дома нельзя изменить после создания</small>}
              </div>
              <div className="form-group">
                <label className="form-label">Подключение к ТЭЦ *</label>
                <select name="chpId" className="form-select" value={formData.chpId} onChange={handleChange} required>
                  {chps.map(chp => {
                    const housesCount = houses.filter(h => h.chpId === chp.id && h.id !== editId).length;
                    const isFull = housesCount >= maxHousesPerChp;
                    return (
                      <option key={chp.id} value={chp.id} disabled={isFull && chp.id !== formData.chpId}>
                        {chp.name} - {housesCount}/5 домов {isFull && chp.id !== formData.chpId && '(ЗАНЯТА)'}
                      </option>
                    );
                  })}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Температура воды (°C) *</label>
                <input type="number" name="temperature" className="form-input" value={formData.temperature} onChange={handleChange} min="40" max="95" step="1" required />
                <small style={{ color: '#718096' }}>Допустимый диапазон: 40°C - 95°C</small>
              </div>
            </>
          )}
          
          <button type="submit" className="btn btn-success" disabled={submitting} style={{ width: '100%', marginTop: '1rem' }}>
            {submitting ? 'Сохранение...' : (isEditMode ? 'Обновить' : 'Сохранить')}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Form;